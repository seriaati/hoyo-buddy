"""Pre-render ZZZ agents' Spine loops into animated WEBPs for animated build cards.

Looks up the agent's Spine files on nanoka and renders them for template 1 cards with
scripts/spine_common.py, which records them in hoyo-buddy-assets/assets/zzz-build-card/spine.yaml.
A new agent's framing is suggested by overlaying the first frame on its static template 1 art;
review and adjust it with `uv run scripts/zzz_card_variants.py spine`. Needs Node and Chrome:
    npm ci --prefix scripts/spine
    uv run scripts/render_zzz_spine.py 1511 1371
    uv run scripts/render_zzz_spine.py --all
    uv run scripts/render_zzz_spine.py --new  # agents that aren't in spine.yaml yet
    uv run scripts/render_zzz_spine.py 1511 --dry-run  # only writes scripts/output/spine/zzz/1511.webp
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import aiohttp
import numpy as np
import yaml
from loguru import logger
from PIL import Image
from PIL.Image import Transpose

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.draw.drawer import Drawer
from scripts.spine_common import (
    NANOKA_URL,
    Framing,
    SpineCharacter,
    SpineFiles,
    Target,
    download_image,
    fetch_json,
    make_parser,
    render_frames,
    run,
)

SPINE_URL = f"{NANOKA_URL}/assets/zzz/live2d"
MANIFEST_PATH = Path("hoyo-buddy-assets/assets/zzz-build-card/spine.yaml")
CARD_DATA_PATH = Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data.yaml")

CARD_SIZE = (3324, 1286)
TARGET = Target("zzz", MANIFEST_PATH, CARD_SIZE, card_size_ratio=0.6)
"""Template 1 cards, the art area is the whole card. Card size ratio measured 0.52-0.55."""
REFERENCE_HEIGHT = 1500
"""Height the animation is rendered at to compare it with the static art."""
MIN_REGISTRATION_IOU = 0.5
"""Below it, the animation likely isn't the static art, so its suggested framing needs a look."""


async def fetch_spine_agents(
    session: aiohttp.ClientSession, agent_ids: list[str] | None
) -> dict[str, SpineCharacter]:
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
    agents: dict[str, SpineCharacter] = {}
    for agent_id, detail in zip(agent_ids, details, strict=True):
        if spine := detail.get("live2_d"):
            image = next(iter(detail["skin"].values()))["image"]
            agents[agent_id] = SpineCharacter(
                detail["name"], spine, SPINE_URL, f"{NANOKA_URL}/assets/zzz/{image}.webp"
            )
        else:
            logger.warning(f"{detail['name']} ({agent_id}) has no Spine files on nanoka")
    return agents


def load_card_data(agent_id: str) -> dict[str, Any]:
    card_data: dict[str, Any] = yaml.safe_load(CARD_DATA_PATH.read_text("utf-8"))
    if agent_id not in card_data:
        msg = f"{agent_id} has no template 1 card data in {CARD_DATA_PATH}, design it first"
        raise ValueError(msg)
    return card_data[agent_id]


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


async def _suggest_framing(
    session: aiohttp.ClientSession,
    agent_id: str,
    agent: SpineCharacter,
    _target: Target,
    files: SpineFiles,
) -> Framing:
    if agent.image is None:
        msg = f"{agent.name} ({agent_id}) has no static art to frame the animation by"
        raise ValueError(msg)
    return await suggest_framing(
        files.skel,
        files.atlas,
        files.folder,
        spine=agent.spine,
        static_art=await download_image(session, agent.image),
        card_data=load_card_data(agent_id),
    )


if __name__ == "__main__":
    args = make_parser("Pre-render ZZZ agents' Spine loops").parse_args()
    asyncio.run(
        run(args, [TARGET], fetch_characters=fetch_spine_agents, suggest_framing=_suggest_framing)
    )
