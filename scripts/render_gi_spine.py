"""Pre-render GI characters' animated TCG card faces into animated WEBPs for animated build cards.

Genius Invokation TCG dynamic card faces are Spine 4.0 skeletons over a background image. Most have
a scenery skeleton beneath the main one (_Sub), some more (_Sub1, _Sub2, ...), and the character can
be in any of them, with the main one drawn on top. They're looked up on Senkin219/GI-Character-Spine,
by the character's internal name in their icon, and rendered for template 1 cards with
scripts/spine_common.py, which records them in hoyo-buddy-assets/assets/gi-build-card/spine.yaml.
Every card face shares the same view, so it's framed to cover the art area. Needs Node and Chrome:
    npm ci --prefix scripts/spine
    uv run scripts/render_gi_spine.py 10000073 10000089
    uv run scripts/render_gi_spine.py --all
    uv run scripts/render_gi_spine.py --new  # characters that aren't in spine.yaml yet
    uv run scripts/render_gi_spine.py 10000073 --dry-run  # only writes scripts/output/spine/gi/
"""

from __future__ import annotations

import asyncio
import math
import re
import sys
from pathlib import Path

import aiohttp
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
    run,
)

REPO = "Senkin219/GI-Character-Spine"
TREE_URL = f"https://api.github.com/repos/{REPO}/git/trees/HEAD?recursive=1"
SPINE_URL = f"https://raw.githubusercontent.com/{REPO}/HEAD/TCG"
CARD_DATA_PATH = Path("hoyo-buddy-assets/assets/gi-build-card")

CARD_VIEW = (-315, -540, 630, 1080)
"""The card face's world rect, the static 420x720 card face scaled 1.5x around the origin. Measured
by matching renders to in-game recordings."""


def _sub_layers(folder: str, files: set[str]) -> tuple[str, ...]:
    """Get the names of the card face's _Sub skeletons, bottom to top: higher numbers are further
    back, then _Sub. Matched against in-game recordings."""
    pattern = re.compile(rf"TCG/{folder}/(Gcg_CardFace_Char_{folder}_Sub(\d*)_Spine)\.skel")
    matches = (m for path in files if (m := pattern.fullmatch(path)))
    layers = sorted(((int(m[2] or 0), m[1]) for m in matches), reverse=True)
    return tuple(name for _, name in layers)


def _mask_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as mask:
        return mask.size


TARGET = Target(
    "gi",
    CARD_DATA_PATH / "spine.yaml",
    _mask_size(CARD_DATA_PATH / "mask.png"),
    CARD_DATA_PATH / "mask.png",
)
"""Template 1 cards' art area, the size of its image mask."""


async def fetch_spine_characters(
    session: aiohttp.ClientSession, character_ids: list[str] | None
) -> dict[str, SpineCharacter]:
    """Get the characters that have a TCG card face with Spine files.

    Args:
        session: The aiohttp session.
        character_ids: The character IDs to look up, or None for every character.
    """
    version = (await fetch_json(session, f"{NANOKA_URL}/manifest.json"))["gi"]["latest"]
    names = await fetch_json(session, f"{NANOKA_URL}/gi/{version}/character.json")
    tree = await fetch_json(session, TREE_URL)
    files = {item["path"] for item in tree["tree"]}

    characters: dict[str, SpineCharacter] = {}
    for character_id in character_ids or list(names):
        data = names.get(character_id)
        if data is None:
            logger.warning(f"{character_id} isn't a character")
            continue

        folder = data["icon"].replace("UI_AvatarIcon_", "Avatar_")
        spine = f"Gcg_CardFace_Char_{folder}_Spine"
        if f"TCG/{folder}/{spine}.skel" not in files:
            if character_ids:
                logger.warning(f"{data['en']} ({character_id}) has no TCG card face Spine files")
            continue

        background = f"{spine}_Bg.png"
        characters[character_id] = SpineCharacter(
            data["en"],
            spine,
            f"{SPINE_URL}/{folder}",
            under=_sub_layers(folder, files),
            background=background if f"TCG/{folder}/{background}" in files else None,
            view=CARD_VIEW,
            untint_flags=True,
        )
    return characters


async def _suggest_framing(
    _session: aiohttp.ClientSession,
    _character_id: str,
    _character: SpineCharacter,
    target: Target,
    _files: SpineFiles,
) -> Framing:
    """Cover the art area with the card face, centered."""
    view_width, view_height = CARD_VIEW[2:]
    width, height = target.area
    height = max(height, math.ceil(width * view_height / view_width))
    # The renderer rounds the view's width up
    width = math.ceil(height * view_width / view_height)
    return Framing((target.area[0] - width) // 2, (target.area[1] - height) // 2, height)


if __name__ == "__main__":
    args = make_parser("Pre-render GI characters' animated TCG card faces").parse_args()
    asyncio.run(
        run(
            args,
            [TARGET],
            fetch_characters=fetch_spine_characters,
            suggest_framing=_suggest_framing,
        )
    )
