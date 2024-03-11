import asyncio
from typing import TYPE_CHECKING

from discord import File

from hoyo_buddy.draw import funcs

from .static import download_and_save_static_images

if TYPE_CHECKING:
    from io import BytesIO

    from enka.models import Character as EnkaCharacter
    from genshin.models import Notes as GenshinNote
    from genshin.models import StarRailNote
    from mihomo.models import Character as MihomoCharacter

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
    buffer = await asyncio.to_thread(
        funcs.draw_item_list, items, draw_input.dark_mode, draw_input.locale
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_checkin_card(draw_input: "DrawInput", rewards: list["Reward"]) -> File:
    await download_and_save_static_images([r.icon for r in rewards], "check-in", draw_input.session)
    buffer = await asyncio.to_thread(funcs.draw_checkin_card, rewards, draw_input.dark_mode)
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_hsr_build_card(
    draw_input: "DrawInput", character: "MihomoCharacter", image_url: str, primary_hex: str
) -> "BytesIO":
    urls: list[str] = []
    urls.append(image_url)
    for trace in character.traces:
        urls.append(trace.icon)
    for trace in character.trace_tree:
        urls.append(trace.icon)
    for relic in character.relics:
        urls.append(relic.icon)
        urls.append(relic.main_affix.icon)
        for affix in relic.sub_affixes:
            urls.append(affix.icon)
    for attr in character.attributes:
        urls.append(attr.icon)
    for addition in character.additions:
        urls.append(addition.icon)
    if character.light_cone is not None:
        urls.append(character.light_cone.portrait)
        for attr in character.light_cone.attributes:
            urls.append(attr.icon)
    urls.append(
        "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/property/IconEnergyRecovery.png"
    )
    await download_and_save_static_images(urls, "hsr-build-card", draw_input.session)

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
    buffer = await asyncio.to_thread(
        funcs.draw_genshin_notes_card, notes, draw_input.locale, translator, draw_input.dark_mode
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
    buffer = await asyncio.to_thread(
        funcs.draw_farm_card, farm_data, draw_input.locale, draw_input.dark_mode, translator
    )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)
