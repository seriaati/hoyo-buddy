"""Generate an HSR build card for any character using enka data as the base.

Usage:
    uv run scripts/gen_hsr_build_card.py [--char-id CHAR_ID] [--image-url URL] [--color HEX] [--dark]

The script fetches showcase data for UID 809162009 via enka, picks the first character,
then optionally overrides the character ID (swapping image/color from data.yaml), the
character art image URL, and/or the primary color hex.

The resulting card is saved to scripts/output/hsr_build_card.png.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from loguru import logger

# Parse our own args before any hoyo_buddy imports, because hoyo_buddy.config uses
# pydantic-settings with cli_parse_args=True which would hijack sys.argv.
_parser = argparse.ArgumentParser(description="Generate an HSR build card")
_parser.add_argument(
    "--char-id",
    type=str,
    default=None,
    help="Override character ID for image/color lookup (e.g. 1005)",
)
_parser.add_argument(
    "--image-url", type=str, default=None, help="Override the character art image URL"
)
_parser.add_argument(
    "--color", type=str, default=None, help="Override the primary color hex (e.g. #9f546f)"
)
_parser.add_argument("--dark", action="store_true", default=False, help="Use dark mode")
_args = _parser.parse_args()

# Clear argv so pydantic-settings doesn't try to parse our flags as bot config.
sys.argv = sys.argv[:1]

import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent))

import enka
from seria.utils import read_yaml

from hoyo_buddy.constants import HSR_DEFAULT_ART_URL
from hoyo_buddy.draw.funcs.hoyo.hsr.build_card import draw_hsr_build_card
from hoyo_buddy.draw.static import download_images
from hoyo_buddy.enums import Locale

SHOWCASE_UID = 809162009
HSR_DATA_PATH = Path("hoyo-buddy-assets/assets/hsr-build-card/data.yaml")
OUTPUT_DIR = Path("scripts/output")


async def main() -> None:
    logger.enable("enka")
    args = _args
    card_data: dict[str, dict] = await read_yaml(HSR_DATA_PATH)

    async with enka.HSRClient(enka.hsr.Language.ENGLISH) as client:
        showcase = await client.fetch_showcase(SHOWCASE_UID)

    if not showcase.characters:
        print("No characters found in showcase.")
        return

    character = showcase.characters[0]
    print(f"Using base character: {character.name} (ID: {character.id})")

    # Determine which character ID to use for image/color lookup
    lookup_id = args.char_id or str(character.id)
    char_card_data = card_data.get(lookup_id)

    if char_card_data is None:
        print(f"Warning: No card data found for character ID {lookup_id}, using defaults.")
        image_url = args.image_url or HSR_DEFAULT_ART_URL.format(char_id=character.id)
        primary_hex = args.color or "#888888"
    else:
        arts: list[str] = char_card_data.get("arts", [])
        image_url = args.image_url or (
            arts[0] if arts else HSR_DEFAULT_ART_URL.format(char_id=lookup_id)
        )
        primary_hex = args.color or char_card_data.get("primary", "#888888")

    print(f"Image URL : {image_url}")
    print(f"Primary   : {primary_hex}")
    print(f"Dark mode : {args.dark}")

    urls: list[str] = [image_url]
    urls.extend(trace.icon for trace in character.traces)
    urls.extend(relic.icon for relic in character.relics)
    if character.light_cone is not None:
        urls.append(character.light_cone.icon.image)

    async with aiohttp.ClientSession() as session:
        await download_images(urls, session)

    result = draw_hsr_build_card(
        character=character,
        locale=Locale.american_english,
        dark_mode=args.dark,
        image_url=image_url,
        primary_hex=primary_hex,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "hsr_build_card.png"
    output_path.write_bytes(result.getvalue())
    print(f"Card saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
