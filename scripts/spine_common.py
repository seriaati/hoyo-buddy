"""Shared helpers to pre-render characters' Spine loops into animated WEBPs for animated build cards.

The game scripts (render_zzz_spine.py, render_hsr_spine.py) look up characters' Spine files on
nanoka and suggest their framings. This renders each loop with scripts/spine/render.mjs
(spine-webgl in headless Chrome), crops it to the card's art area and encodes it at
ANIMATED_CARD_SCALE, uploads it to the image host and records it in the art area's spine.yaml.

Each entry's framing is the animation's uncropped top-left (x, y) in the art area and its height,
on the static-scale card, and whether it's mirrored (flip). Since the asset is cropped to the art
area, a changed framing needs a re-render, which replaces the previous upload. Needs Node and
Chrome:
    npm ci --prefix scripts/spine
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
from typing import TYPE_CHECKING, Any, NamedTuple

import aiohttp
import yaml
from loguru import logger
from PIL import Image
from PIL.Image import Transpose

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import ANIMATED_CARD_SCALE, DC_MAX_FILESIZE
from hoyo_buddy.utils import upload_image

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

NANOKA_URL = "https://static.nanoka.cc"
NANOKA_HEADERS = {"User-Agent": "Mozilla/5.0"}  # nanoka rejects aiohttp's default user agent
IMG_HOST_URL = "https://img.seria.moe"
RENDERER = Path(__file__).parent / "spine/render.mjs"
OUTPUT_DIR = Path("scripts/output/spine")

ANIMATION_OVERRIDES = {"UISpineVelina": "loop12+wl10+FK4"}
"""Loops the renderer wouldn't pick (idle, then loop, then all, then the only one) by Spine file
name, from nanoka's viewer."""
MAX_WEBP_QUALITY = 80
MIN_WEBP_QUALITY = 50
IMG_HOST_MAX_SIZE = 50 * 1024 * 1024
FPS = 30
ATLAS_PAGE_RE = re.compile(r"^[^:]+\.(png|webp|jpg)$", re.IGNORECASE)


class SpineCharacter(NamedTuple):
    name: str
    spine: str
    """nanoka's name of the character's Spine files."""
    base_url: str
    """URL of the folder the Spine files are in."""
    image: str | None = None
    """URL of the static art the animation is of, if it is."""


class Framing(NamedTuple):
    x: int
    y: int
    height: int
    flip: bool = False
    """Whether to mirror the animation, to match how the static art is drawn on the card."""


class Target(NamedTuple):
    """An art area to render animations for."""

    name: str
    manifest: Path
    area: tuple[int, int]
    """The art area's size on the static-scale card."""
    card_size_ratio: float
    """Animated card size relative to its animation's size, measured on a few cards."""


class SpineFiles(NamedTuple):
    skel: Path
    atlas: Path
    folder: Path
    """Folder to render into."""


type SuggestFraming = Callable[
    [aiohttp.ClientSession, str, SpineCharacter, Target, SpineFiles], Awaitable[Framing]
]
"""Suggests a framing for a character that isn't in the target's spine.yaml yet."""


def make_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("character_ids", nargs="*", help="Character IDs, e.g. 1310")
    parser.add_argument("--all", action="store_true", help="Render every character with Spine")
    parser.add_argument(
        "--new", action="store_true", help="Render characters not in spine.yaml yet"
    )
    parser.add_argument(
        "--jobs", type=int, default=4, help="Number of characters to render at once"
    )
    parser.add_argument("--dry-run", action="store_true", help="Write to scripts/output only")
    return parser


async def fetch_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url, headers=NANOKA_HEADERS) as resp:
        resp.raise_for_status()
        return await resp.json()


async def download(session: aiohttp.ClientSession, url: str, path: Path) -> None:
    async with session.get(url, headers=NANOKA_HEADERS) as resp:
        resp.raise_for_status()
        path.write_bytes(await resp.read())


async def download_image(session: aiohttp.ClientSession, url: str) -> Image.Image:
    async with session.get(url, headers=NANOKA_HEADERS) as resp:
        resp.raise_for_status()
        return Image.open(io.BytesIO(await resp.read()))


async def _download_page(session: aiohttp.ClientSession, url: str, path: Path) -> None:
    """Download an atlas page, nanoka converted some PNG pages to WEBP without renaming them."""
    try:
        await download(session, url, path)
    except aiohttp.ClientResponseError as e:
        if e.status != 404 or url.endswith(".webp"):
            raise
        await download(session, f"{url.rsplit('.', 1)[0]}.webp", path)


async def download_spine(
    session: aiohttp.ClientSession, base_url: str, spine: str, folder: Path
) -> tuple[Path, Path]:
    skel, atlas = folder / f"{spine}.skel", folder / f"{spine}.atlas"
    await asyncio.gather(
        download(session, f"{base_url}/{skel.name}", skel),
        download(session, f"{base_url}/{atlas.name}", atlas),
    )

    pages = [line.strip() for line in atlas.read_text("utf-8").splitlines()]
    pages = [page for page in pages if ATLAS_PAGE_RE.match(page)]
    await asyncio.gather(
        *(_download_page(session, f"{base_url}/{page}", folder / page) for page in pages)
    )
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
    area: tuple[int, int],
    frames: int | None = None,
) -> list[Image.Image]:
    """Render the animation's frames as the animated card shows them.

    They're cropped to the art area, mirrored if the framing is and scaled by
    ANIMATED_CARD_SCALE. Draw them at (max(x, 0), max(y, 0)) in the static-scale art area.

    Args:
        skel: The Spine skeleton file.
        atlas: The Spine atlas file, next to its texture pages.
        folder: Folder to render the PNGs into.
        spine: nanoka's name of the Spine files.
        framing: The animation's position, height and orientation in the static-scale art area.
        area: The art area's size on the static-scale card.
        frames: Render only the first frames, e.g. 1 for a preview.
    """
    info, _ = await render_frames(
        skel, atlas, folder / "info", spine=spine, height=framing.height, frames=0
    )
    left, top = max(0, -framing.x), max(0, -framing.y)
    right = min(info["width"], area[0] - framing.x)
    bottom = min(info["height"], area[1] - framing.y)
    if right <= left or bottom <= top:
        msg = f"The animation is off the art area at {framing}"
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
        round((right - left) * ANIMATED_CARD_SCALE),
        round((bottom - top) * ANIMATED_CARD_SCALE),
    )
    flip = framing.flip
    return await asyncio.to_thread(lambda: [load_frame(p, size=size, flip=flip) for p in paths])


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


def encode_webp(frames: list[Image.Image], *, card_size_ratio: float) -> tuple[bytes, int, int]:
    """Encode frames into an animated WEBP, halving the frame rate if the animated card would be
    too big for Discord.

    Returns:
        The WEBP bytes, its frame rate and the quality used.
    """
    fps = FPS
    data, quality = save_webp(frames, fps)
    if len(data) * card_size_ratio > DC_MAX_FILESIZE:
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


def load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    return yaml.safe_load(path.read_text("utf-8")) or {} if path.exists() else {}


async def render_target(  # ruff:ignore[too-many-arguments]
    session: aiohttp.ClientSession,
    target: Target,
    manifest: dict[str, dict[str, Any]],
    character_id: str,
    character: SpineCharacter,
    *,
    files: SpineFiles,
    suggest_framing: SuggestFraming,
    dry_run: bool,
) -> None:
    """Render a character's animation for an art area, then upload it and record it."""
    entry = manifest.get(character_id, {})
    if "height" in entry:
        framing = Framing(entry["x"], entry["y"], entry["height"], entry.get("flip", False))
    else:
        suggest_files = files._replace(folder=files.folder / "suggest")
        framing = await suggest_framing(session, character_id, character, target, suggest_files)

    frames = await render_card_frames(
        files.skel,
        files.atlas,
        files.folder,
        spine=character.spine,
        framing=framing,
        area=target.area,
    )
    data, fps, quality = await asyncio.to_thread(
        encode_webp, frames, card_size_ratio=target.card_size_ratio
    )

    size_mb = len(data) / 1024 / 1024
    logger.info(
        f"{character.name} ({character_id}) {target.name}: "
        f"{fps}fps, {size_mb:.1f}MB at q{quality}, {framing}"
    )

    if dry_run:
        path = OUTPUT_DIR / target.name / f"{character_id}.webp"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info(f"Wrote {path}")
        return

    url = await upload_image(session, image=data)
    if old_url := entry.get("url"):
        await delete_image(session, old_url)

    manifest[character_id] = {"name": character.name, "url": url, **framing._asdict()}
    target.manifest.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")
    logger.info(f"Uploaded {url}")


async def run(
    args: argparse.Namespace,
    targets: list[Target],
    *,
    fetch_characters: Callable[
        [aiohttp.ClientSession, list[str] | None], Awaitable[dict[str, SpineCharacter]]
    ],
    suggest_framing: SuggestFraming,
) -> None:
    """Render the characters passed on the command line for the targets.

    Args:
        args: Parsed arguments, from make_parser.
        targets: The art areas to render for.
        fetch_characters: Gets the characters with Spine files, all of them for None.
        suggest_framing: Suggests a framing for a character that isn't in a target's spine.yaml.
    """
    if not args.character_ids and not args.all and not args.new:
        sys.exit("pass character IDs, --all or --new")

    manifests = {target: load_manifest(target.manifest) for target in targets}
    semaphore = asyncio.Semaphore(args.jobs)
    failed: list[str] = []

    async def render(
        session: aiohttp.ClientSession, character_id: str, character: SpineCharacter
    ) -> None:
        async with semaphore:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    folder = Path(tmp)
                    skel, atlas = await download_spine(
                        session, character.base_url, character.spine, folder
                    )
                    for target, manifest in manifests.items():
                        if args.new and character_id in manifest:
                            continue
                        await render_target(
                            session,
                            target,
                            manifest,
                            character_id,
                            character,
                            files=SpineFiles(skel, atlas, folder / target.name),
                            suggest_framing=suggest_framing,
                            dry_run=args.dry_run,
                        )
            except Exception:
                logger.exception(f"Failed to render {character.name} ({character_id})")
                failed.append(character_id)

    async with aiohttp.ClientSession() as session:
        characters = await fetch_characters(session, args.character_ids or None)
        if args.new:
            characters = {
                k: v for k, v in characters.items() if any(k not in m for m in manifests.values())
            }
        logger.info(f"Rendering {len(characters)} characters")
        await asyncio.gather(*(render(session, k, v) for k, v in characters.items()))

    if failed:
        sys.exit(f"Failed to render {', '.join(failed)}")
