import asyncio
import contextlib
from typing import TYPE_CHECKING

from discord import File
from genshin.models import Character as GenshinCharacter
from genshin.models import StarRailDetailCharacter as StarRailCharacter
from mihomo.models import Character as MihomoCharacter
from sentry_sdk.metrics import timing

from hoyo_buddy.draw import funcs

from ..models import AbyssCharacter, HoyolabHSRCharacter
from .static import download_and_save_static_images

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

    from enka.models import Character as EnkaCharacter
    from genshin.models import Notes as GenshinNote
    from genshin.models import PartialGenshinUserStats, SpiralAbyss, StarRailNote

    from ..bot.translator import Translator
    from ..models import DrawInput, FarmData, ItemWithDescription, ItemWithTrailing, Reward


async def draw_item_list_card(
    draw_input: "DrawInput",
    items: list["ItemWithDescription"] | list["ItemWithTrailing"],
) -> File:
    await download_and_save_static_images(
        [item.icon for item in items],
        "item-list",
        draw_input.session,
    )
    with timing("draw", tags={"type": "item_list_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_item_list, items, draw_input.dark_mode, draw_input.locale
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_checkin_card(draw_input: "DrawInput", rewards: list["Reward"]) -> File:
    await download_and_save_static_images([r.icon for r in rewards], "check-in", draw_input.session)
    with timing("draw", tags={"type": "checkin_card"}):
        buffer = await asyncio.to_thread(funcs.draw_checkin_card, rewards, draw_input.dark_mode)
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_hsr_build_card(
    draw_input: "DrawInput",
    character: "MihomoCharacter | HoyolabHSRCharacter",
    image_url: str,
    primary_hex: str,
) -> "BytesIO":
    urls: list[str] = []
    urls.append(image_url)
    if isinstance(character, HoyolabHSRCharacter):
        for stat in character.stats:
            urls.append(stat.icon)
    else:
        for trace in character.traces:
            urls.append(trace.icon)
        for attr in character.attributes:
            urls.append(attr.icon)
        for addition in character.additions:
            urls.append(addition.icon)

    for trace in character.trace_tree:
        urls.append(trace.icon)

    for relic in character.relics:
        urls.append(relic.icon)
        urls.append(relic.main_affix.icon)
        for affix in relic.sub_affixes:
            urls.append(affix.icon)

    if character.light_cone is not None:
        urls.append(character.light_cone.portrait)
        if isinstance(character, MihomoCharacter):
            for attr in character.light_cone.attributes:
                urls.append(attr.icon)
    urls.append(
        "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/property/IconEnergyRecovery.png"
    )
    await download_and_save_static_images(urls, "hsr-build-card", draw_input.session)

    with timing("draw", tags={"type": "hsr_build_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_hsr_build_card,
            character,
            draw_input.locale,
            draw_input.dark_mode,
            image_url,
            primary_hex,
        )
    return buffer


async def draw_hsr_notes_card(
    draw_input: "DrawInput", notes: "StarRailNote", translator: "Translator"
) -> File:
    await download_and_save_static_images(
        [exped.item_url for exped in notes.expeditions],
        folder="hsr-notes",
        session=draw_input.session,
    )
    with timing("draw", tags={"type": "hsr_notes_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_hsr_notes_card, notes, draw_input.locale, translator, draw_input.dark_mode
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_gi_build_card(
    draw_input: "DrawInput", character: "EnkaCharacter", image_url: str
) -> "BytesIO":
    urls: list[str] = []
    urls.append(image_url)
    urls.append(character.weapon.icon)
    urls.append(character.icon.gacha)
    for artifact in character.artifacts:
        urls.append(artifact.icon)
    for talent in character.talents:
        urls.append(talent.icon)
    for constellation in character.constellations:
        urls.append(constellation.icon)
    await download_and_save_static_images(urls, "gi-build-card", draw_input.session)

    with timing("draw", tags={"type": "gi_build_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_genshin_card, draw_input.locale, draw_input.dark_mode, character, image_url
        )
    return buffer


async def draw_gi_notes_card(
    draw_input: "DrawInput", notes: "GenshinNote", translator: "Translator"
) -> File:
    await download_and_save_static_images(
        [exped.character_icon for exped in notes.expeditions],
        folder="gi-notes",
        session=draw_input.session,
    )
    with timing("draw", tags={"type": "gi_notes_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_genshin_notes_card,
            notes,
            draw_input.locale,
            translator,
            draw_input.dark_mode,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_farm_card(
    draw_input: "DrawInput", farm_data: list["FarmData"], translator: "Translator"
) -> File:
    image_urls = (
        [r.icon for data in farm_data for r in data.domain.rewards]
        + [c.icon for data in farm_data for c in data.characters]
        + [w.icon for data in farm_data for w in data.weapons]
    )
    await download_and_save_static_images(
        image_urls,
        folder="farm",
        session=draw_input.session,
    )
    with timing("draw", tags={"type": "farm_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_farm_card, farm_data, draw_input.locale, draw_input.dark_mode, translator
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_chara_card(
    draw_input: "DrawInput",
    characters: "Sequence[GenshinCharacter | StarRailCharacter]",
    talents: dict[str, str],
    pc_icons: dict[str, str],
    translator: "Translator",
) -> File:
    urls: list[str] = []
    for c in characters:
        if isinstance(c, GenshinCharacter):
            urls.append(c.weapon.icon)
        elif isinstance(c, StarRailCharacter) and c.equip:
            urls.append(c.equip.icon)
    urls.extend(pc_icons[str(c.id)] for c in characters if str(c.id) in pc_icons)

    await download_and_save_static_images(urls, "gi-characters", draw_input.session)
    with timing("draw", tags={"type": "hsr_character_card"}):
        buffer = await asyncio.to_thread(
            funcs.draw_character_card,
            characters,
            talents,
            pc_icons,
            draw_input.dark_mode,
            translator,
            draw_input.locale,
        )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_spiral_abyss_card(
    draw_input: "DrawInput",
    abyss: "SpiralAbyss",
    characters: "Sequence[GenshinCharacter]",
    translator: "Translator",
) -> File:
    abyss_characters: dict[str, AbyssCharacter] = {
        str(chara.id): AbyssCharacter(level=chara.level, const=chara.constellation, icon=chara.icon)
        for chara in characters
    }

    urls = [
        chara.icon
        for floor in abyss.floors
        for chamber in floor.chambers
        for battle in chamber.battles
        for chara in battle.characters
    ]
    with contextlib.suppress(IndexError):
        for chara in [
            abyss.ranks.most_bursts_used[0],
            abyss.ranks.most_damage_taken[0],
            abyss.ranks.most_kills[0],
            abyss.ranks.most_skills_used[0],
            abyss.ranks.strongest_strike[0],
        ]:
            urls.append(chara.icon)

    await download_and_save_static_images(urls, "abyss", draw_input.session)
    with timing("draw", tags={"type": "spiral_abyss_card"}):
        buffer = await asyncio.to_thread(
            funcs.AbyssCard.draw,
            draw_input.dark_mode,
            draw_input.locale,
            translator,
            abyss,
            abyss_characters,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_exploration_card(
    draw_input: "DrawInput",
    user: "PartialGenshinUserStats",
    translator: "Translator",
) -> File:
    with timing("draw", tags={"type": "exploration_card"}):
        buffer = await asyncio.to_thread(
            funcs.ExplorationCard.draw,
            user,
            draw_input.dark_mode,
            draw_input.locale,
            translator,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)
