"""Generate an HSR build card for any character using enka data as the base.

Usage:
    uv run scripts/gen_hsr_build_card.py [--char-id CHAR_ID] [--image-url URL]
        [--color HEX[/DARK_HEX] ...] [--dark | --both]

The script fetches showcase data for UID 809162009 via enka, picks the first character,
then optionally overrides the character ID (swapping image/color from data.yaml), the
character art image URL, and/or the primary color hex.

A single card is saved to scripts/output/hsr_build_card.png. Several colors or --both save a
contact sheet (a row per color, light and dark side by side) to
scripts/output/hsr_build_card_sheet.png. Dark mode uses DARK_HEX (primary-dark) when given,
otherwise the card's automatic dark conversion of HEX.
"""

from __future__ import annotations

import argparse
import asyncio
import io
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
    "--color",
    nargs="+",
    default=None,
    metavar="HEX[/DARK_HEX]",
    help="Override the primary color hex (e.g. #9f546f), a /DARK_HEX suffix sets primary-dark",
)
_parser.add_argument("--dark", action="store_true", default=False, help="Use dark mode")
_parser.add_argument(
    "--both", action="store_true", default=False, help="Render light and dark mode"
)
_args = _parser.parse_args()

# Clear argv so pydantic-settings doesn't try to parse our flags as bot config.
sys.argv = sys.argv[:1]

import aiohttp
from PIL import Image, ImageDraw, ImageFont

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
THUMB_WIDTH = 1100


def _render(character: enka.hsr.Character, image_url: str, color: str, dark: bool) -> Image.Image:
    light_hex, _, dark_hex = color.partition("/")
    result = draw_hsr_build_card(
        character=character,
        locale=Locale.american_english,
        dark_mode=dark,
        image_url=image_url,
        primary_hex=(dark_hex or light_hex) if dark else light_hex,
        uid=None,
        show_substat_rolls=True,
        show_substat_breakdown=False,
    )
    return Image.open(io.BytesIO(result.getvalue()))


def _label(color: str, dark: bool) -> str:
    light_hex, _, dark_hex = color.partition("/")
    if not dark:
        return f"{light_hex} light"
    return f"{dark_hex} dark" if dark_hex else f"{light_hex} dark (auto)"


def _make_contact_sheet(
    cards: dict[tuple[str, bool], Image.Image], colors: list[str], modes: list[bool]
) -> Image.Image:
    pad, label_h = 16, 44
    first = next(iter(cards.values()))
    thumb_h = round(first.height * THUMB_WIDTH / first.width)
    sheet = Image.new(
        "RGB",
        (pad + len(modes) * (THUMB_WIDTH + pad), pad + len(colors) * (label_h + thumb_h + pad)),
        (128, 128, 128),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=30)
    for r, color in enumerate(colors):
        for c, dark in enumerate(modes):
            x = pad + c * (THUMB_WIDTH + pad)
            y = pad + r * (label_h + thumb_h + pad)
            draw.text((x, y), _label(color, dark), font=font, fill=(255, 255, 255))
            thumb = (
                cards[color, dark]
                .convert("RGB")
                .resize((THUMB_WIDTH, thumb_h), Image.Resampling.LANCZOS)
            )
            sheet.paste(thumb, (x, y + label_h))
    return sheet


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
    image_url = args.image_url or HSR_DEFAULT_ART_URL.format(char_id=lookup_id)

    if args.color:
        colors: list[str] = args.color
    elif char_card_data is None:
        print(f"Warning: No card data found for character ID {lookup_id}, using defaults.")
        colors = ["#888888"]
    else:
        primary_dark = char_card_data.get("primary-dark")
        colors = [f"{char_card_data['primary']}/{primary_dark or ''}".rstrip("/")]
    modes = [False, True] if args.both else [args.dark]

    print(f"Image URL : {image_url}")
    print(f"Colors    : {', '.join(colors)}")

    urls: list[str] = [image_url]
    urls.extend(trace.icon for trace in character.traces)
    urls.extend(relic.icon for relic in character.relics)
    if character.light_cone is not None:
        urls.append(character.light_cone.icon.image)

    async with aiohttp.ClientSession() as session:
        await download_images(urls, session)

    cards = {
        (color, dark): _render(character, image_url, color, dark)
        for color in colors
        for dark in modes
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if len(cards) == 1:
        output_path = OUTPUT_DIR / "hsr_build_card.png"
        next(iter(cards.values())).save(output_path)
    else:
        output_path = OUTPUT_DIR / "hsr_build_card_sheet.png"
        _make_contact_sheet(cards, colors, modes).save(output_path)
    print(f"Card saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
