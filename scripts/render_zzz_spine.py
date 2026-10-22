"""Pre-render ZZZ agents' Spine loops into animated WEBPs for animated build cards.

Looks up the agent's Spine files on nanoka, renders the loop with scripts/zzz_spine/render.mjs
(spine-webgl in headless Chrome), crops it to the card and encodes it at the animated card's scale,
uploads it to the image host and records it in hoyo-buddy-assets/assets/zzz-build-card/spine.yaml.

Each entry's framing is the animation's bounds on the static-scale card: their top-left (x, y) and
height, and whether it's mirrored (flip). A new agent's framing is suggested from its static template 1 art; review and adjust it
with `uv run scripts/zzz_card_variants.py spine`. Since the asset is cropped to the card, a changed
framing needs a re-render, which replaces the previous upload. Needs Node and Chrome:
    npm ci --prefix scripts/zzz_spine
    uv run scripts/render_zzz_spine.py 1511 1371
    uv run scripts/render_zzz_spine.py --all
    uv run scripts/render_zzz_spine.py --new  # agents that aren't in spine.yaml yet
    uv run scripts/render_zzz_spine.py 1511 --dry-run  # only writes scripts/output/zzz_spine/1511.webp
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

import aiohttp
import numpy as np
import yaml
from loguru import logger
from PIL import Image
from PIL.Image import Transpose

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import DC_MAX_FILESIZE, ZZZ_ANIMATED_CARD_SCALE
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.utils import upload_image

NANOKA_URL = "https://static.nanoka.cc"
NANOKA_HEADERS = {"User-Agent": "Mozilla/5.0"}  # nanoka rejects aiohttp's default user agent
IMG_HOST_URL = "https://img.seria.moe"
RENDERER = Path(__file__).parent / "zzz_spine/render.mjs"
MANIFEST_PATH = Path("hoyo-buddy-assets/assets/zzz-build-card/spine.yaml")
CARD_DATA_PATH = Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data.yaml")
OUTPUT_DIR = Path("scripts/output/zzz_spine")

CARD_SIZE = (3324, 1286)
REFERENCE_HEIGHT = 1500
"""Height the animation is rendered at to compare it with the static art."""
MIN_REGISTRATION_IOU = 0.5
"""Below it, the animation likely isn't the static art, so its suggested framing needs a look."""
ANIMATION_OVERRIDES = {"UISpineVelina": "loop12+wl10+FK4"}
"""Loops the renderer wouldn't pick (idle, then loop, then the only one), from nanoka's viewer."""
MAX_WEBP_QUALITY = 80
MIN_WEBP_QUALITY = 50
IMG_HOST_MAX_SIZE = 50 * 1024 * 1024
CARD_SIZE_RATIO = 0.6
"""Animated card size relative to its animation's size, measured 0.52-0.55 plus a margin."""
FPS = 30
ATLAS_PAGE_RE = re.compile(r"^[^:]+\.(png|webp|jpg)$", re.IGNORECASE)

_parser = argparse.ArgumentParser(description="Pre-render ZZZ agents' Spine loops")
_parser.add_argument("agent_ids", nargs="*", help="Agent IDs, e.g. 1511")
_parser.add_argument("--all", action="store_true", help="Render every agent nanoka has Spine for")
_parser.add_argument("--new", action="store_true", help="Render agents not in spine.yaml yet")
_parser.add_argument("--jobs", type=int, default=4, help="Number of agents to render at once")
_parser.add_argument("--dry-run", action="store_true", help="Write to scripts/output only")


class SpineAgent(NamedTuple):
    name: str
    spine: str
    """nanoka's name of the agent's Spine files."""
    image: str
    """URL of the default outfit's art, which the animation is of."""


class Framing(NamedTuple):
    x: int
    y: int
    height: int
    flip: bool
    """Whether to mirror the animation, to match how the static art is drawn on the card."""


async def fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url, headers=NANOKA_HEADERS) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_spine_agents(
    session: aiohttp.ClientSession, agent_ids: list[str] | None
) -> dict[str, SpineAgent]:
    """Get the agents that have Spine files on nanoka.

    Args:
        session: The aiohttp session.
        agent_ids: The agent IDs to look up, or None for every agent.
    """
    version = (await fetch_json(session, f"{NANOKA_URL}/manifest.json"))["zzz"]["latest"]
    base = f"{NANOKA_URL}/zzz/{version}"
    agent_ids = agent_ids or list(await fetch_json(session, f"{base}/character.json"))

    details = await asyncio.gather(
        *(fetch_json(session, f"{base}/en/character/{agent_id}.json") for agent_id in agent_ids)
    )
    agents: dict[str, SpineAgent] = {}
    for agent_id, detail in zip(agent_ids, details, strict=True):
        if spine := detail.get("live2_d"):
            image = next(iter(detail["skin"].values()))["image"]
            agents[agent_id] = SpineAgent(
                detail["name"], spine, f"{NANOKA_URL}/assets/zzz/{image}.webp"
            )
        else:
            logger.warning(f"{detail['name']} ({agent_id}) has no Spine files on nanoka")
    return agents


async def download(session: aiohttp.ClientSession, url: str, path: Path) -> None:
    async with session.get(url, headers=NANOKA_HEADERS) as resp:
        resp.raise_for_status()
        path.write_bytes(await resp.read())


async def download_spine(
    session: aiohttp.ClientSession, spine: str, folder: Path
) -> tuple[Path, Path]:
    base = f"{NANOKA_URL}/assets/zzz/live2d"
    skel, atlas = folder / f"{spine}.skel", folder / f"{spine}.atlas"
    await asyncio.gather(
        download(session, f"{base}/{skel.name}", skel),
        download(session, f"{base}/{atlas.name}", atlas),
    )

    pages = [line.strip() for line in atlas.read_text("utf-8").splitlines()]
    pages = [page for page in pages if ATLAS_PAGE_RE.match(page)]
    await asyncio.gather(*(download(session, f"{base}/{page}", folder / page) for page in pages))
    return skel, atlas


async def render_frames(  # ruff:ignore[too-many-arguments]
    skel: Path,
    atlas: Path,
    folder: Path,
    *,
    spine: str,
    height: int,
    frames: int | None = None,
    crop: tuple[int, int, int, int] | None = None,
) -> tuple[dict[str, Any], list[Path]]:
    """Render the animation's frames to PNGs.

    Returns:
        The renderer's info (the animation's full width and height, frame count) and the paths of
        the frames, in order.
    """
    args = [str(skel), str(atlas), str(folder), "--fps", str(FPS), "--height", str(height)]
    if (animation := ANIMATION_OVERRIDES.get(spine)) is not None:
        args.extend(("--anim", animation))
    if frames is not None:
        args.extend(("--frames", str(frames)))
    if crop is not None:
        args.extend(("--crop", ",".join(map(str, crop))))

    proc = await asyncio.create_subprocess_exec(
        "node", str(RENDERER), *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        msg = f"Renderer failed:\n{stderr.decode()}"
        raise RuntimeError(msg)

    return json.loads(stdout), sorted(folder.glob("*.png"))


def load_card_data(agent_id: str) -> dict[str, Any]:
    card_data: dict[str, Any] = yaml.safe_load(CARD_DATA_PATH.read_text("utf-8"))
    if agent_id not in card_data:
        msg = f"{agent_id} has no template 1 card data in {CARD_DATA_PATH}, design it first"
        raise ValueError(msg)
    return card_data[agent_id]


def load_frame(path: Path, *, size: tuple[int, int], flip: bool) -> Image.Image:
    with Image.open(path) as im:
        frame = im.convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    return frame.transpose(Transpose.FLIP_LEFT_RIGHT) if flip else frame


async def render_card_frames(  # ruff:ignore[too-many-arguments]
    skel: Path,
    atlas: Path,
    folder: Path,
    *,
    spine: str,
    framing: Framing,
    frames: int | None = None,
) -> list[Image.Image]:
    """Render the animation's frames as the animated card shows them.

    They're cropped to the card, mirrored if the framing is and scaled by
    ZZZ_ANIMATED_CARD_SCALE. Draw them at (max(x, 0), max(y, 0)) on the static-scale card.

    Args:
        skel: The Spine skeleton file.
        atlas: The Spine atlas file, next to its texture pages.
        folder: Folder to render the PNGs into.
        spine: nanoka's name of the Spine files.
        framing: The animation's position, height and orientation on the static-scale card.
        frames: Render only the first frames, e.g. 1 for a preview.
    """
    info, _ = await render_frames(
        skel, atlas, folder / "info", spine=spine, height=framing.height, frames=0
    )
    left, top = max(0, -framing.x), max(0, -framing.y)
    right = min(info["width"], CARD_SIZE[0] - framing.x)
    bottom = min(info["height"], CARD_SIZE[1] - framing.y)
    if right <= left or bottom <= top:
        msg = f"The animation is off the card at {framing}"
        raise ValueError(msg)
    if framing.flip:  # The crop is of the mirrored animation
        left, right = info["width"] - right, info["width"] - left

    _, paths = await render_frames(
        skel,
        atlas,
        folder / "frames",
        spine=spine,
        height=framing.height,
        frames=frames,
        crop=(left, top, right - left, bottom - top),
    )
    size = (
        round((right - left) * ZZZ_ANIMATED_CARD_SCALE),
        round((bottom - top) * ZZZ_ANIMATED_CARD_SCALE),
    )
    flip = framing.flip
    return await asyncio.to_thread(lambda: [load_frame(p, size=size, flip=flip) for p in paths])


def art_extent(alpha: np.ndarray) -> tuple[int, int, float]:
    """Get the first and last opaque rows of art, and the x of its head and shoulders."""
    rows = np.flatnonzero((alpha > 128).any(axis=1))
    top, bottom = int(rows[0]), int(rows[-1]) + 1
    head = alpha[top : top + int((bottom - top) * 0.3)].astype(float)
    focus_x = float((head.sum(axis=0) * np.arange(alpha.shape[1])).sum() / head.sum())
    return top, bottom, focus_x


def place_static_art(art: Image.Image, card_data: dict[str, Any]) -> Image.Image:
    """Size the static art like ZZZAgentCard does."""
    art = Drawer.resize_crop(art.convert("RGBA"), (card_data["image_w"], card_data["image_h"]))
    return art.transpose(Transpose.FLIP_LEFT_RIGHT) if card_data["flip"] else art


def _opaque_mask(image: Image.Image, downscale: int) -> np.ndarray:
    size = (max(1, image.width // downscale), max(1, image.height // downscale))
    alpha = image.getchannel("A").resize(size, Image.Resampling.BOX)
    return (np.asarray(alpha) > 128).astype(np.float32)


def _best_offset(static: np.ndarray, animation: np.ndarray) -> tuple[float, int, int]:
    """Find where the animation's mask overlaps the static art's mask best, by IoU.

    Returns:
        The IoU and the animation's top-left offset in the static mask.
    """
    shape = (static.shape[0] + animation.shape[0], static.shape[1] + animation.shape[1])
    overlap = np.fft.irfft2(
        np.fft.rfft2(static, shape) * np.conj(np.fft.rfft2(animation, shape)), shape
    )
    iou = overlap / (static.sum() + animation.sum() - overlap + 1e-6)
    dy, dx = (int(v) for v in np.unravel_index(np.argmax(iou), iou.shape))
    # Offsets wrap around, indices past the static mask are negative offsets
    dy = dy - shape[0] if dy > static.shape[0] else dy
    dx = dx - shape[1] if dx > static.shape[1] else dx
    return float(iou.max()), dx, dy


def register_art(
    static: Image.Image, animation: Image.Image, scales: np.ndarray, *, downscale: int
) -> tuple[float, float, int, int]:
    """Find the scale and offset that overlay the animation's art onto the static art.

    Returns:
        The IoU of their opaque masks, the scale, and the scaled animation's top-left in the
        static art.
    """
    static_mask = _opaque_mask(static, downscale)
    best = (-1.0, 1.0, 0, 0)
    for scale in scales:
        size = (round(animation.width * scale), round(animation.height * scale))
        score, dx, dy = _best_offset(static_mask, _opaque_mask(animation.resize(size), downscale))
        if score > best[0]:
            best = (score, float(scale), dx * downscale, dy * downscale)
    return best


async def suggest_framing(  # ruff:ignore[too-many-arguments]
    skel: Path,
    atlas: Path,
    folder: Path,
    *,
    spine: str,
    static_art: Image.Image,
    card_data: dict[str, Any],
) -> Framing:
    """Frame the animation like the static template 1 art, by overlaying its first frame on it.

    The animation is usually the static art rigged, but it may be cropped differently, so they're
    matched by where their shapes overlap best rather than by their sizes.
    """
    _, paths = await render_frames(
        skel, atlas, folder, spine=spine, height=REFERENCE_HEIGHT, frames=1
    )
    with Image.open(paths[0]) as im:
        frame = im.convert("RGBA")
    flip: bool = card_data["flip"]
    if flip:
        frame = frame.transpose(Transpose.FLIP_LEFT_RIGHT)
    static = place_static_art(static_art, card_data)

    coarse = await asyncio.to_thread(
        register_art, static, frame, np.geomspace(0.5, 4, 60), downscale=16
    )
    score, scale, dx, dy = await asyncio.to_thread(
        register_art, static, frame, np.linspace(coarse[1] * 0.96, coarse[1] * 1.04, 9), downscale=4
    )
    if score < MIN_REGISTRATION_IOU:
        logger.warning(f"{spine} overlaps its static art poorly (IoU {score:.2f}), check it")
    return Framing(
        x=card_data["image_x"] + dx,
        y=card_data["image_y"] + dy,
        height=round(REFERENCE_HEIGHT * scale),
        flip=flip,
    )


def save_webp(frames: list[Image.Image], fps: int) -> tuple[bytes, int]:
    """Save frames as an animated WEBP, lowering the quality until it fits the image host.

    Returns:
        The WEBP bytes and the quality used.
    """
    # Round cumulative timestamps so the frame rate doesn't drift from rounded frame durations
    stamps = [round(i * 1000 / fps) for i in range(len(frames) + 1)]
    durations = [b - a for a, b in zip(stamps, stamps[1:], strict=False)]

    quality = MAX_WEBP_QUALITY
    while True:
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            quality=quality,
        )
        if buffer.tell() <= IMG_HOST_MAX_SIZE or quality <= MIN_WEBP_QUALITY:
            return buffer.getvalue(), quality
        quality -= 5


def encode_webp(frames: list[Image.Image]) -> tuple[bytes, int, int]:
    """Encode frames into an animated WEBP, halving the frame rate if the animated card would be
    too big for Discord.

    Returns:
        The WEBP bytes, its frame rate and the quality used.
    """
    fps = FPS
    data, quality = save_webp(frames, fps)
    if len(data) * CARD_SIZE_RATIO > DC_MAX_FILESIZE:
        fps //= 2
        data, quality = save_webp(frames[::2], fps)
    return data, fps, quality


async def delete_image(session: aiohttp.ClientSession, url: str) -> None:
    if not url.startswith(IMG_HOST_URL):
        return

    headers = {"Authorization": f"Bearer {CONFIG.img_upload_api_key}"}
    async with session.delete(url, headers=headers) as resp:
        if resp.status == 404:
            return
        resp.raise_for_status()


async def download_image(session: aiohttp.ClientSession, url: str) -> Image.Image:
    async with session.get(url, headers=NANOKA_HEADERS) as resp:
        resp.raise_for_status()
        return Image.open(io.BytesIO(await resp.read()))


async def render_agent(
    session: aiohttp.ClientSession,
    manifest: dict[str, dict[str, Any]],
    agent_id: str,
    agent: SpineAgent,
    *,
    dry_run: bool,
) -> None:
    card_data = load_card_data(agent_id)
    entry = manifest.get(agent_id, {})

    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        skel, atlas = await download_spine(session, agent.spine, folder)
        if "height" in entry:
            framing = Framing(entry["x"], entry["y"], entry["height"], entry.get("flip", False))
        else:
            framing = await suggest_framing(
                skel,
                atlas,
                folder / "reference",
                spine=agent.spine,
                static_art=await download_image(session, agent.image),
                card_data=card_data,
            )
        frames = await render_card_frames(skel, atlas, folder, spine=agent.spine, framing=framing)
        data, fps, quality = await asyncio.to_thread(encode_webp, frames)

    size_mb = len(data) / 1024 / 1024
    logger.info(f"{agent.name} ({agent_id}): {fps}fps, {size_mb:.1f}MB at q{quality}, {framing}")

    if dry_run:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUTPUT_DIR / f"{agent_id}.webp").write_bytes(data)
        logger.info(f"Wrote {OUTPUT_DIR / f'{agent_id}.webp'}")
        return

    url = await upload_image(session, image=data)
    if old_url := entry.get("url"):
        await delete_image(session, old_url)

    manifest[agent_id] = {"name": agent.name, "url": url, **framing._asdict()}
    MANIFEST_PATH.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    logger.info(f"Uploaded {url}")


async def main() -> None:
    args = _parser.parse_args()
    if not args.agent_ids and not args.all and not args.new:
        _parser.error("pass agent IDs, --all or --new")

    manifest: dict[str, dict[str, Any]] = (
        yaml.safe_load(MANIFEST_PATH.read_text("utf-8")) or {} if MANIFEST_PATH.exists() else {}
    )

    semaphore = asyncio.Semaphore(args.jobs)
    failed: list[str] = []

    async def render(session: aiohttp.ClientSession, agent_id: str, agent: SpineAgent) -> None:
        async with semaphore:
            try:
                await render_agent(session, manifest, agent_id, agent, dry_run=args.dry_run)
            except Exception:
                logger.exception(f"Failed to render {agent.name} ({agent_id})")
                failed.append(agent_id)

    async with aiohttp.ClientSession() as session:
        agents = await fetch_spine_agents(session, args.agent_ids or None)
        if args.new:
            agents = {k: v for k, v in agents.items() if k not in manifest}
        logger.info(f"Rendering {len(agents)} agents")
        await asyncio.gather(*(render(session, k, v) for k, v in agents.items()))

    if failed:
        sys.exit(f"Failed to render {', '.join(failed)}")


if __name__ == "__main__":
    asyncio.run(main())
