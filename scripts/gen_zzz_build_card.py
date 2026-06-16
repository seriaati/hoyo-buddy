"""Generate a ZZZ build card for any agent using enka data as the base.

Usage:
    uv run scripts/gen_zzz_build_card.py [--uid UID] [--char-id CHAR_ID] \
        [--image-url URL] [--color HEX] [--template {1,2,3,4}] [--use-m3-art]

The script fetches showcase data for a ZZZ UID via enka, picks the first agent, then
applies a specific agent's template data (color, image positions, art, name) on top of
that agent's real in-game data (stats, level, discs, w-engine). This mirrors how the bot
draws ZZZ build cards, but lets you preview any agent's template against arbitrary stats.

ZZZ build cards have four templates:
    1, 2 -> ZZZAgentCard   (single-agent layouts, positions per-agent in agent_data*.yaml)
    3    -> ZZZTeamCard    (single agent rendered through the team-card layout)
    4    -> ZZZAgentCard4  (vertical layout)

Without --template, all four are generated. Output is saved to
scripts/output/zzz_build_card_t{N}.png.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger

# Parse our own args before any hoyo_buddy imports, because hoyo_buddy.config uses
# pydantic-settings with cli_parse_args=True which would hijack sys.argv.
_parser = argparse.ArgumentParser(description="Generate a ZZZ build card")
_parser.add_argument("--uid", type=int, default=10000827, help="ZZZ UID to fetch showcase for")
_parser.add_argument(
    "--char-id",
    type=str,
    default=None,
    help="Override agent ID for template/image/color lookup (e.g. 1091)",
)
_parser.add_argument("--image-url", type=str, default=None, help="Override the agent art image URL")
_parser.add_argument(
    "--color", type=str, default=None, help="Override the primary color hex (e.g. #95B84B)"
)
_parser.add_argument(
    "--template",
    type=int,
    choices=(1, 2, 3, 4),
    default=None,
    help="Template to generate; omit to generate all four",
)
_parser.add_argument(
    "--use-m3-art", action="store_true", default=False, help="Use M3 cinema art (template 2)"
)
_args = _parser.parse_args()

# Clear argv so pydantic-settings doesn't try to parse our flags as bot config.
sys.argv = sys.argv[:1]

import aiohttp

sys.path.insert(0, str(Path(__file__).parent.parent))

import enka
import hb_data
from seria.utils import read_yaml

from hoyo_buddy.constants import ZZZ_TEAM_IMAGE_OVERRIDES
from hoyo_buddy.draw.funcs.hoyo.zzz import ZZZAgentCard, ZZZAgentCard4, ZZZTeamCard
from hoyo_buddy.draw.static import ZZZ_V2_GAME_RECORD, download_images
from hoyo_buddy.enums import Locale
from hoyo_buddy.hoyo.clients.gpy import GenshinClient
from hoyo_buddy.models import AgentNameData, ZZZEnkaCharacter
from hoyo_buddy.models.draw import ZZZTemp1CardData, ZZZTemp2CardData

ZZZ_DATA_PATH = Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data.yaml")
ZZZ_DATA2_PATH = Path("hoyo-buddy-assets/assets/zzz-build-card/agent_data_temp2.yaml")
OUTPUT_DIR = Path("scripts/output")


def _resolve_image_url(
    template: int,
    *,
    lookup_id: str,
    char: hb_data.zzz.models.Character | None,
    override: str | None,
    use_m3_art: bool,
) -> str:
    if override is not None:
        return override
    if template == 1:
        return char.image if char is not None else ""
    if template == 2:
        if char is None:
            return ""
        return char.phase_2_cinema_art if use_m3_art else char.phase_3_cinema_art
    # 3, 4: banner / vertical-painting art (or curated override)
    return ZZZ_TEAM_IMAGE_OVERRIDES.get(
        lookup_id,
        str(ZZZ_V2_GAME_RECORD / f"role_vertical_painting/role_vertical_painting_{lookup_id}.png"),
    )


def _build_card(
    template: int,
    *,
    agent: ZZZEnkaCharacter,
    card_data: ZZZTemp1CardData,
    color: str | None,
    image_url: str,
    disc_icons: dict[int, str],
    name_data: AgentNameData | None,
) -> ZZZAgentCard | ZZZAgentCard4 | ZZZTeamCard:
    if template == 3:
        return ZZZTeamCard(
            locale=Locale.american_english.value,
            agents=[agent],
            agent_colors={agent.id: color or card_data.color},
            agent_images={agent.id: image_url},
            name_datas={agent.id: name_data} if name_data is not None else {},
            disc_icons=disc_icons,
            show_substat_rolls={agent.id: True},
            agent_special_stat_map={},
            agent_hl_substat_map={agent.id: []},
            hl_special_stats={agent.id: False},
        )
    if template == 4:
        return ZZZAgentCard4(
            agent,
            locale=Locale.american_english,
            name_data=name_data,
            image_url=image_url,
            disc_icons=disc_icons,
            color=color or card_data.color,
            show_substat_rolls=True,
            agent_special_stats=[],
            hl_substats=[],
            hl_special_stats=False,
        )
    return ZZZAgentCard(
        agent,
        locale=Locale.american_english.value,
        image_url=image_url,
        card_data=card_data,
        disc_icons=disc_icons,
        name_data=name_data,
        color=color,
        template=template,  # pyright: ignore[reportArgumentType]
        show_substat_rolls=True,
        agent_special_stats=[],
        hl_substats=[],
        hl_special_stats=False,
    )


async def main() -> None:
    logger.enable("enka")
    args = _args
    templates: list[int] = [args.template] if args.template is not None else [1, 2, 3, 4]

    temp1_data: dict[str, dict] = await read_yaml(ZZZ_DATA_PATH)
    temp2_data: dict[str, dict] = await read_yaml(ZZZ_DATA2_PATH)

    async with enka.ZZZClient(enka.zzz.Language.ENGLISH) as client:
        showcase = await client.fetch_showcase(args.uid)

    if not showcase.agents:
        print("No agents found in showcase.")
        return

    agent = GenshinClient.convert_zzz_character(showcase.agents[0])
    print(f"Using base agent: {agent.name} (ID: {agent.id})")

    lookup_id = args.char_id or str(agent.id)
    print(f"Template lookup ID: {lookup_id}")

    # Fetch name data and disc icons directly from hb_data (the bot reads these from its DB
    # cache, which this standalone script doesn't have).
    async with hb_data.ZZZClient() as data_client:
        characters = data_client.get_characters()
        drive_discs = data_client.get_drive_discs()

    char_by_id = {char.id: char for char in characters}
    template_char = char_by_id.get(int(lookup_id))
    if template_char is not None:
        name_data = AgentNameData(short_name=template_char.name, full_name=template_char.full_name)
    else:
        print(f"Warning: No character data for ID {lookup_id}, using base agent name.")
        name_data = AgentNameData(short_name=agent.name, full_name=agent.name)

    disc_icons: dict[int, str] = {}
    for disc in agent.discs:
        disc_item = next((d for d in drive_discs if d.id == disc.id), None)
        if disc_item is not None:
            disc_icons[disc.id] = disc_item.icon

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        for template in templates:
            if template == 2:
                temp2 = temp2_data.get(lookup_id)
                temp1 = temp1_data.get(lookup_id)
                if temp2 is None:
                    print(f"Skipping template 2: no temp2 data for ID {lookup_id}.")
                    continue
                card_data: ZZZTemp1CardData = ZZZTemp2CardData.model_validate(temp2)
                if card_data.color is None and temp1 is not None:
                    card_data = card_data.model_copy(
                        update={"color": ZZZTemp1CardData.model_validate(temp1).color}
                    )
            else:
                temp1 = temp1_data.get(lookup_id)
                if temp1 is None:
                    print(f"Skipping template {template}: no data for ID {lookup_id}.")
                    continue
                card_data = ZZZTemp1CardData.model_validate(temp1)

            image_url = _resolve_image_url(
                template,
                lookup_id=lookup_id,
                char=template_char,
                override=args.image_url,
                use_m3_art=args.use_m3_art,
            )
            urls: list[str] = [image_url, *disc_icons.values()]
            if agent.w_engine is not None:
                urls.append(agent.w_engine.icon)
            await download_images(urls, session)

            print(
                f"Template {template} | image: {image_url} | color: {args.color or card_data.color}"
            )
            card = _build_card(
                template,
                agent=agent,
                card_data=card_data,
                color=args.color,
                image_url=image_url,
                disc_icons=disc_icons,
                name_data=name_data,
            )
            result = card.draw()

            output_path = OUTPUT_DIR / f"zzz_build_card_t{template}.png"
            output_path.write_bytes(result.getvalue())
            print(f"  saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
