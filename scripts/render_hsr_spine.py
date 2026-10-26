"""Pre-render HSR characters' Spine loops into animated WEBPs for animated build cards.

Looks up the character's Spine files on nanoka and renders them for template 1 and 2 cards with
scripts/spine_common.py, which records them in spine.yaml next to the template's card assets
(hsr-build-card for template 1, hsr-build-card2 for template 2).

A new character's framing is suggested by overlaying the first frame on the static art, which is a
crop of the Spine art; review and adjust it with `uv run scripts/hsr_spine_framing.py`. When they
match poorly, a comparison is sent to the Discord webhook at SPINE_WEBHOOK_URL, if it's set.
Characters made of several skeletons are skipped, nanoka can't render them either. Needs Node and
Chrome:
    npm ci --prefix scripts/spine
    uv run scripts/render_hsr_spine.py 1310 1005
    uv run scripts/render_hsr_spine.py 1310 --template 2
    uv run scripts/render_hsr_spine.py --all
    uv run scripts/render_hsr_spine.py --new  # characters that aren't in spine.yaml yet
    uv run scripts/render_hsr_spine.py 1310 --dry-run  # only writes scripts/output/spine/hsr*/
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

import aiohttp
import numpy as np
from loguru import logger
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from hoyo_buddy.constants import HSR_DEFAULT_ART_URL
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

SPINE_URL = f"{NANOKA_URL}/assets/hsr/spine"
ASSET_PATH = Path("hoyo-buddy-assets/assets")
REFERENCE_HEIGHT = 1500
"""Height the animation is rendered at to compare it with the static art."""
MIN_REGISTRATION_SCORE = 0.5
"""Below it, the animation likely isn't laid out like the static art, so its suggested framing
needs a look."""
MASKS = {
    1: ASSET_PATH / "hsr-build-card/img/mask.png",
    2: ASSET_PATH / "hsr-build-card2/image_mask.png",
}
"""Templates' art area masks, the static art is resized and cropped to cover them."""
PREVIEW_WIDTH = 1600
"""Width of the comparisons sent to the SPINE_WEBHOOK_URL Discord webhook."""
PREVIEW_BACKGROUND = (60, 60, 60)


def _mask_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as mask:
        return mask.size


TARGETS = {
    1: Target("hsr1", ASSET_PATH / "hsr-build-card/spine.yaml", _mask_size(MASKS[1]), MASKS[1]),
    2: Target("hsr2", ASSET_PATH / "hsr-build-card2/spine.yaml", _mask_size(MASKS[2]), MASKS[2]),
}
"""Templates' art areas, the size of their image masks."""


async def fetch_spine_characters(
    session: aiohttp.ClientSession, character_ids: list[str] | None
) -> dict[str, SpineCharacter]:
    """Get the characters that have Spine files on nanoka.

    Args:
        session: The aiohttp session.
        character_ids: The character IDs to look up, or None for every character.
    """
    spines: dict[str, str] = await fetch_json(session, f"{SPINE_URL}/manifest.json")
    version = (await fetch_json(session, f"{NANOKA_URL}/manifest.json"))["hsr"]["latest"]
    names = await fetch_json(session, f"{NANOKA_URL}/hsr/{version}/character.json")

    characters: dict[str, SpineCharacter] = {}
    for character_id in character_ids or list(spines):
        name = names.get(character_id, {}).get("en", character_id)
        name = re.sub(r"<[^>]+>", "", name.replace("{NICKNAME}", "Trailblazer"))
        spine = spines.get(character_id)
        if spine is None:
            logger.warning(f"{name} ({character_id}) has no Spine files on nanoka")
        elif "|" in spine:
            logger.warning(f"{name} ({character_id}) has several skeletons, skipping")
        else:
            characters[character_id] = SpineCharacter(
                name,
                spine,
                f"{SPINE_URL}/{character_id}",
                HSR_DEFAULT_ART_URL.format(char_id=character_id),
            )
    return characters


def _correlate(a: np.ndarray, b: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    return np.fft.irfft2(np.fft.rfft2(a, shape) * np.conj(np.fft.rfft2(b, shape)), shape)


def _opaque_gray(image: Image.Image, size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Get the image's grayscale, zeroed where it isn't opaque, and its opaque mask."""
    image = image.resize(size, Image.Resampling.BOX)
    mask = (np.asarray(image.getchannel("A")) > 230).astype(np.float64)
    return np.asarray(image.convert("L"), dtype=np.float64) / 255 * mask, mask


def _best_offset(
    frame: tuple[np.ndarray, np.ndarray], static: tuple[np.ndarray, np.ndarray]
) -> tuple[float, int, int]:
    """Find where the static art matches the frame best, by normalized cross-correlation of their
    opaque pixels (Padfield's masked NCC).

    Returns:
        The correlation and the static art's top-left offset in the frame.
    """
    (f, f_mask), (s, s_mask) = frame, static
    shape = (f.shape[0] + s.shape[0], f.shape[1] + s.shape[1])
    overlap = np.maximum(np.round(_correlate(f_mask, s_mask, shape)), 1)
    f_sum = _correlate(f, s_mask, shape)
    s_sum = _correlate(f_mask, s, shape)
    covariance = _correlate(f, s, shape) - f_sum * s_sum / overlap
    f_var = _correlate(f * f, s_mask, shape) - f_sum**2 / overlap
    s_var = _correlate(f_mask, s * s, shape) - s_sum**2 / overlap
    ncc = covariance / np.sqrt(np.maximum(f_var * s_var, 1e-9))
    # The static art has background the animation lacks, but most of it should overlap
    ncc[overlap < s_mask.sum() * 0.6] = -1

    dy, dx = (int(v) for v in np.unravel_index(np.argmax(ncc), ncc.shape))
    # Offsets wrap around, indices past the frame are negative offsets
    dy = dy - shape[0] if dy > f.shape[0] else dy
    dx = dx - shape[1] if dx > f.shape[1] else dx
    return float(ncc.max()), dx, dy


def register_art(
    frame: Image.Image, static: Image.Image, scales: np.ndarray, *, size: int
) -> tuple[float, float, int, int]:
    """Find the scale and offset that overlay the static art onto the animation's frame.

    The static art is matched at a fixed size and the frame is scaled instead, so small scales
    don't win by matching less detail.

    Args:
        frame: The animation's frame.
        static: The static art.
        scales: The static art's scales on the frame to try.
        size: Width the static art is matched at.

    Returns:
        The correlation, the scale, and the scaled static art's top-left in the frame.
    """
    static_size = (size, round(static.height * size / static.width))
    static_gray = _opaque_gray(static, static_size)
    best = (-1.0, 1.0, 0, 0)
    for scale in scales:
        factor = size / (static.width * scale)
        frame_size = (round(frame.width * factor), round(frame.height * factor))
        score, dx, dy = _best_offset(_opaque_gray(frame, frame_size), static_gray)
        if score > best[0]:
            best = (score, float(scale), round(dx / factor), round(dy / factor))
    return best


class Registration(NamedTuple):
    """Where the static art lies on the animation's first frame."""

    frame: Image.Image
    static: Image.Image
    score: float
    """Correlation of the static art and the frame where they overlap, 1 is a perfect match."""
    scale: float
    """The static art's scale on the frame."""
    x: int
    y: int
    """The static art's top-left on the frame."""


async def register_spine(  # ruff:ignore[too-many-arguments]
    skel: Path,
    atlas: Path,
    folder: Path,
    *,
    spine: str,
    static_art: Image.Image,
    min_size: float = 0.1,
) -> Registration:
    """Find where the static art lies on the animation's first frame.

    Args:
        skel: The Spine skeleton file.
        atlas: The Spine atlas file, next to its texture pages.
        folder: Folder to render the first frame into.
        spine: nanoka's name of the Spine files.
        static_art: The static art.
        min_size: Smallest share of the frame's height the static art may cover. Raise it when the
            static art matches a tiny patch of a differently laid out animation.
    """
    _, paths = await render_frames(
        skel, atlas, folder, spine=spine, height=REFERENCE_HEIGHT, frames=1
    )
    with Image.open(paths[0]) as im:
        frame = im.convert("RGBA")
    static = static_art.convert("RGBA")

    # The static art's height on the frame, up to 80% of it
    scales = np.geomspace(min_size, 0.8, 50) * frame.height / static.height
    coarse = await asyncio.to_thread(register_art, frame, static, scales, size=96)
    scales = np.linspace(coarse[1] * 0.96, coarse[1] * 1.04, 9)
    score, scale, dx, dy = await asyncio.to_thread(register_art, frame, static, scales, size=256)
    if score < MIN_REGISTRATION_SCORE:
        logger.warning(f"{spine} matches its static art poorly ({score:.2f}), check it")
    return Registration(frame, static, score, scale, dx, dy)


def frame_like_static(registration: Registration, area: tuple[int, int]) -> Framing:
    """Frame the animation to show the static art's crop, sized to cover the art area like the
    static art is.
    """
    static = registration.static
    # Like Drawer.resize_crop, which the cards draw the static art with
    ratio = min(static.width / area[0], static.height / area[1])
    left = (static.width / ratio - area[0]) / 2
    top = (static.height / ratio - area[1]) / 2
    card_scale = 1 / (ratio * registration.scale)  # Static-scale card pixels per frame pixel
    return Framing(
        x=round(-left - registration.x * card_scale),
        y=round(-top - registration.y * card_scale),
        height=round(REFERENCE_HEIGHT * card_scale),
    )


async def suggest_framing(  # ruff:ignore[too-many-arguments]
    skel: Path,
    atlas: Path,
    folder: Path,
    *,
    spine: str,
    static_art: Image.Image,
    area: tuple[int, int],
    min_size: float = 0.1,
) -> Framing:
    """Frame the animation like the static art in an art area, by overlaying its first frame on it.

    The static art is a crop of the Spine art (around the character's face), so the animation is
    zoomed in and moved to show the same crop. See register_spine for the arguments.
    """
    registration = await register_spine(
        skel, atlas, folder, spine=spine, static_art=static_art, min_size=min_size
    )
    return frame_like_static(registration, area)


def draw_comparison(registration: Registration, framing: Framing, mask: Image.Image) -> Image.Image:
    """Draw the static art and the animation's first frame side by side, as a framing shows them
    in the art area.
    """
    static = Drawer.resize_crop(registration.static, mask.size)
    scale = framing.height / registration.frame.height  # Static-scale card pixels per frame pixel
    box = (
        -framing.x / scale,
        -framing.y / scale,
        (mask.width - framing.x) / scale,
        (mask.height - framing.y) / scale,
    )
    frame = registration.frame.resize(mask.size, Image.Resampling.LANCZOS, box=box)

    im = Image.new("RGB", (mask.width * 2, mask.height))
    for i, art in enumerate((static, frame)):
        area = Image.new("RGBA", mask.size, PREVIEW_BACKGROUND)
        area.alpha_composite(art)
        im.paste(area, (mask.width * i, 0), mask)
    return im


def _draw_comparisons(registration: Registration) -> bytes:
    """Draw each template's comparison in a row of one image."""
    rows: list[Image.Image] = []
    for num, target in TARGETS.items():
        mask = Drawer.open_image(MASKS[num])
        row = draw_comparison(registration, frame_like_static(registration, target.area), mask)
        rows.append(row.resize((PREVIEW_WIDTH, round(row.height * PREVIEW_WIDTH / row.width))))

    im = Image.new("RGB", (PREVIEW_WIDTH, sum(row.height for row in rows)))
    y = 0
    for row in rows:
        im.paste(row, (0, y))
        y += row.height
    buffer = io.BytesIO()
    im.save(buffer, format="PNG")
    return buffer.getvalue()


async def _alert_poor_match(
    session: aiohttp.ClientSession,
    character_id: str,
    character: SpineCharacter,
    registration: Registration,
) -> None:
    """Send the comparisons to the Discord webhook, to review the suggested framings."""
    # Unset GitHub Actions secrets are empty
    if not (url := os.environ.get("SPINE_WEBHOOK_URL")):
        return

    content = (
        f"**{character.name} ({character_id})**'s animated card framing matches its static art "
        f"poorly ({registration.score:.2f}). Each row is a template, the static art on the left "
        "and the animation on the right. Review it with `uv run scripts/hsr_spine_framing.py "
        f"init {character_id} --force`."
    )
    form = aiohttp.FormData()
    form.add_field("payload_json", json.dumps({"content": content}))
    image = await asyncio.to_thread(_draw_comparisons, registration)
    form.add_field("files[0]", image, filename=f"{character_id}.png", content_type="image/png")
    async with session.post(url, data=form) as resp:
        resp.raise_for_status()


_registrations: dict[str, Registration] = {}
"""Characters' registrations, the same for every template."""


async def _suggest_framing(
    session: aiohttp.ClientSession,
    character_id: str,
    character: SpineCharacter,
    target: Target,
    files: SpineFiles,
) -> Framing:
    if character.image is None:
        msg = f"{character.name} ({character_id}) has no static art to frame the animation by"
        raise ValueError(msg)

    if (registration := _registrations.get(character_id)) is None:
        registration = await register_spine(
            files.skel,
            files.atlas,
            files.folder,
            spine=character.spine,
            static_art=await download_image(session, character.image),
        )
        _registrations[character_id] = registration
        if registration.score < MIN_REGISTRATION_SCORE:
            try:
                await _alert_poor_match(session, character_id, character, registration)
            except aiohttp.ClientError:
                # The framing still gets rendered and can be reviewed later
                logger.exception(f"Failed to alert about {character.name} ({character_id})")
    return frame_like_static(registration, target.area)


if __name__ == "__main__":
    parser = make_parser("Pre-render HSR characters' Spine loops")
    parser.add_argument(
        "--template", type=int, choices=TARGETS, action="append", help="Templates to render for"
    )
    args = parser.parse_args()
    targets = [TARGETS[num] for num in args.template or TARGETS]
    asyncio.run(
        run(
            args, targets, fetch_characters=fetch_spine_characters, suggest_framing=_suggest_framing
        )
    )
