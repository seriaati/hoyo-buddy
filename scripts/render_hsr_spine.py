"""Pre-render HSR characters' Spine loops into animated WEBPs for animated build cards.

Looks up the character's Spine files on nanoka and renders them for template 1 and 2 cards with
scripts/spine_common.py, which records them in spine.yaml next to the template's card assets
(hsr-build-card for template 1, hsr-build-card2 for template 2).

A new character's framing covers the art area with the loop's bounds, centered. The Spine art
isn't the static art, so check the renders and adjust x, y or height in spine.yaml when a crop is
off. Characters made of several skeletons are skipped, nanoka can't render them either. Needs Node
and Chrome:
    npm ci --prefix scripts/spine
    uv run scripts/render_hsr_spine.py 1310 1005
    uv run scripts/render_hsr_spine.py 1310 --template 2
    uv run scripts/render_hsr_spine.py --all
    uv run scripts/render_hsr_spine.py --new  # characters that aren't in spine.yaml yet
    uv run scripts/render_hsr_spine.py 1310 --dry-run  # only writes scripts/output/spine/hsr*/
"""

from __future__ import annotations

import asyncio
import math
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.spine_common import (
    NANOKA_URL,
    Framing,
    SpineCharacter,
    SpineFiles,
    Target,
    fetch_json,
    make_parser,
    render_frames,
    run,
)

if TYPE_CHECKING:
    import aiohttp

SPINE_URL = f"{NANOKA_URL}/assets/hsr/spine"
ASSET_PATH = Path("hoyo-buddy-assets/assets")
REFERENCE_HEIGHT = 1000
"""Height the animation is rendered at to measure its bounds."""
CARD_SIZE_RATIO = 0.5
"""Measured 0.37-0.43."""


def _mask_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as mask:
        return mask.size


TARGETS = {
    1: Target(
        "hsr1",
        ASSET_PATH / "hsr-build-card/spine.yaml",
        _mask_size(ASSET_PATH / "hsr-build-card/img/mask.png"),
        CARD_SIZE_RATIO,
    ),
    2: Target(
        "hsr2",
        ASSET_PATH / "hsr-build-card2/spine.yaml",
        _mask_size(ASSET_PATH / "hsr-build-card2/image_mask.png"),
        CARD_SIZE_RATIO,
    ),
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
            characters[character_id] = SpineCharacter(name, spine, f"{SPINE_URL}/{character_id}")
    return characters


async def cover_framing(
    _session: aiohttp.ClientSession,
    _character_id: str,
    character: SpineCharacter,
    target: Target,
    files: SpineFiles,
) -> Framing:
    """Frame the animation's bounds to cover the art area, centered."""
    info, _ = await render_frames(
        files.skel,
        files.atlas,
        files.folder,
        spine=character.spine,
        height=REFERENCE_HEIGHT,
        frames=0,
    )
    width, height = target.area
    aspect = info["width"] / info["height"]
    framing_height = max(height, math.ceil(width / aspect))
    framing_width = framing_height * aspect
    return Framing(
        round((width - framing_width) / 2), round((height - framing_height) / 2), framing_height
    )


if __name__ == "__main__":
    parser = make_parser("Pre-render HSR characters' Spine loops")
    parser.add_argument(
        "--template", type=int, choices=TARGETS, action="append", help="Templates to render for"
    )
    args = parser.parse_args()
    targets = [TARGETS[num] for num in args.template or TARGETS]
    asyncio.run(
        run(args, targets, fetch_characters=fetch_spine_characters, suggest_framing=cover_framing)
    )
