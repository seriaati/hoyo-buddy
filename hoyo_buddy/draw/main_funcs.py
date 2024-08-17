from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Literal

import ambr
import enka
import hakushin
from discord import File
from sentry_sdk.metrics import timing

from hoyo_buddy.draw import funcs

from ..models import (
    AbyssCharacter,
    AgentNameData,
    HoyolabHSRCharacter,
    UnownedCharacter,
    ZZZDrawData,
)
from .static import download_images

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

    from genshin.models import Character as GenshinCharacter
    from genshin.models import (
        FullBattlesuit,
        ImgTheaterData,
        PartialGenshinUserStats,
        SpiralAbyss,
        StarRailAPCShadow,
        StarRailChallenge,
        StarRailChallengeSeason,
        StarRailNote,
        StarRailPureFiction,
        ZZZFullAgent,
        ZZZNotes,
    )
    from genshin.models import Notes as GenshinNote
    from genshin.models import StarRailDetailCharacter as StarRailCharacter

    from ..l10n import Translator
    from ..models import DrawInput, FarmData, ItemWithDescription, ItemWithTrailing, Reward


async def draw_item_list_card(
    draw_input: DrawInput,
    items: list[ItemWithDescription] | list[ItemWithTrailing],
) -> File:
    await download_images(
        [item.icon for item in items if item.icon is not None],
        "item-list",
        draw_input.session,
    )
    with timing("draw", tags={"type": "item_list_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.draw_item_list,
            items,
            draw_input.dark_mode,
            draw_input.locale.value,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_checkin_card(draw_input: DrawInput, rewards: list[Reward]) -> BytesIO:
    await download_images([r.icon for r in rewards], "check-in", draw_input.session)
    with timing("draw", tags={"type": "checkin_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.draw_checkin_card,
            rewards,
            draw_input.dark_mode,
        )
    return buffer


async def draw_hsr_build_card(
    draw_input: DrawInput,
    character: enka.hsr.Character | HoyolabHSRCharacter,
    image_url: str,
    primary_hex: str,
) -> BytesIO:
    urls: list[str] = []
    urls.append(image_url)

    for trace in character.traces:
        urls.append(trace.icon)

    stats = (
        character.stats if isinstance(character, HoyolabHSRCharacter) else character.stats.values()
    )
    for stat in stats:
        urls.append(stat.icon)

    for relic in character.relics:
        urls.append(relic.icon)
        urls.append(relic.main_stat.icon)
        for sub_stat in relic.sub_stats:
            urls.append(sub_stat.icon)

    if character.light_cone is not None:
        urls.append(character.light_cone.icon.image)
        if isinstance(character, enka.hsr.Character):
            for stat in character.light_cone.stats:
                urls.append(stat.icon)

    await download_images(urls, "hsr-build-card", draw_input.session)

    with timing("draw", tags={"type": "hsr_build_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hsr.draw_hsr_build_card,
            character,
            draw_input.locale.value,
            draw_input.dark_mode,
            image_url,
            primary_hex,
        )
    return buffer


async def draw_hsr_notes_card(
    draw_input: DrawInput, notes: StarRailNote, translator: Translator
) -> BytesIO:
    await download_images(
        [exped.item_url for exped in notes.expeditions],
        folder="hsr-notes",
        session=draw_input.session,
    )
    with timing("draw", tags={"type": "hsr_notes_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hsr.draw_hsr_notes_card,
            notes,
            draw_input.locale.value,
            translator,
            draw_input.dark_mode,
        )
    return buffer


async def draw_gi_build_card(
    draw_input: DrawInput,
    character: enka.gi.Character,
    *,
    image_url: str,
    zoom: float,
    template: Literal[1, 2],
    top_crop: bool,
) -> BytesIO:
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

    if template == 2:
        async with ambr.AmbrAPI() as api:
            characters = await api.fetch_characters()
            ambr_char = next((char for char in characters if str(character.id) in char.id), None)
            if ambr_char is None:
                msg = f"Character {character.id} not found in Amber's database."
                raise ValueError(msg)

        await download_images(urls, "gi-build-card2", draw_input.session)
        card = funcs.genshin.GITempTwoBuildCard(
            locale=draw_input.locale.value,
            character=character,
            zoom=zoom,
            dark_mode=draw_input.dark_mode,
            character_image=image_url,
            english_name=ambr_char.name,
            top_crop=top_crop,
        )
        with timing("draw", tags={"type": "gi_build_card2"}):
            buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    else:
        await download_images(urls, "gi-build-card", draw_input.session)
        with timing("draw", tags={"type": "gi_build_card"}):
            buffer = await draw_input.loop.run_in_executor(
                draw_input.executor,
                funcs.genshin.draw_genshin_card,
                draw_input.locale.value,
                draw_input.dark_mode,
                character,
                image_url,
                zoom,
            )
    return buffer


async def draw_gi_notes_card(
    draw_input: DrawInput, notes: GenshinNote, translator: Translator
) -> BytesIO:
    await download_images(
        [exped.character_icon for exped in notes.expeditions],
        folder="gi-notes",
        session=draw_input.session,
    )
    with timing("draw", tags={"type": "gi_notes_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.genshin.draw_genshin_notes_card,
            notes,
            draw_input.locale.value,
            translator,
            draw_input.dark_mode,
        )
    return buffer


async def draw_farm_card(
    draw_input: DrawInput, farm_data: list[FarmData], translator: Translator
) -> File:
    image_urls = (
        [r.icon for data in farm_data for r in data.domain.rewards]
        + [c.icon for data in farm_data for c in data.characters]
        + [w.icon for data in farm_data for w in data.weapons]
    )
    await download_images(
        image_urls,
        folder="farm",
        session=draw_input.session,
    )
    with timing("draw", tags={"type": "farm_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.draw_farm_card,
            farm_data,
            draw_input.locale.value,
            draw_input.dark_mode,
            translator,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_gi_characters_card(
    draw_input: DrawInput,
    characters: Sequence[GenshinCharacter | UnownedCharacter],
    talents: dict[str, str],
    pc_icons: dict[str, str],
    translator: Translator,
) -> File:
    urls: list[str] = []
    for c in characters:
        if isinstance(c, UnownedCharacter):
            continue
        urls.append(c.weapon.icon)
    urls.extend(pc_icons[str(c.id)] for c in characters if str(c.id) in pc_icons)

    await download_images(urls, "gi-characters", draw_input.session)
    with timing("draw", tags={"type": "gi_character_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.genshin.draw_character_card,
            characters,
            talents,
            pc_icons,
            draw_input.dark_mode,
            translator,
            draw_input.locale.value,
        )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_hsr_characters_card(
    draw_input: DrawInput,
    characters: Sequence[StarRailCharacter | UnownedCharacter],
    pc_icons: dict[str, str],
    translator: Translator,
) -> File:
    urls: list[str] = []
    for c in characters:
        if isinstance(c, UnownedCharacter) or c.equip is None:
            continue
        urls.append(c.equip.icon)
    urls.extend(pc_icons[str(c.id)] for c in characters if str(c.id) in pc_icons)

    await download_images(urls, "hsr-characters", draw_input.session)
    with timing("draw", tags={"type": "hsr_character_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hsr.draw_character_card,
            characters,
            pc_icons,
            draw_input.dark_mode,
            translator,
            draw_input.locale.value,
        )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_spiral_abyss_card(
    draw_input: DrawInput,
    abyss: SpiralAbyss,
    characters: Sequence[GenshinCharacter],
    translator: Translator,
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

    await download_images(urls, "abyss", draw_input.session)
    with timing("draw", tags={"type": "spiral_abyss_card"}):
        card = funcs.genshin.AbyssCard(
            draw_input.dark_mode,
            draw_input.locale.value,
            translator,
            abyss,
            abyss_characters,
        )
        buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_exploration_card(
    draw_input: DrawInput,
    user: PartialGenshinUserStats,
    translator: Translator,
) -> File:
    with timing("draw", tags={"type": "exploration_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.genshin.ExplorationCard(
                user, draw_input.dark_mode, draw_input.locale.value, translator
            ).draw,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_moc_card(
    draw_input: DrawInput,
    data: StarRailChallenge,
    season: StarRailChallengeSeason,
    translator: Translator,
) -> File:
    for floor in data.floors:
        icons = [chara.icon for chara in floor.node_1.avatars + floor.node_2.avatars]
        await download_images(icons, "moc", draw_input.session)

    with timing("draw", tags={"type": "moc_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hsr.moc.MOCCard(data, season, draw_input.locale.value, translator).draw,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_pure_fiction_card(
    draw_input: DrawInput,
    data: StarRailPureFiction,
    season: StarRailChallengeSeason,
    translator: Translator,
) -> File:
    for floor in data.floors:
        icons = [chara.icon for chara in floor.node_1.avatars + floor.node_2.avatars]
        await download_images(icons, "pf", draw_input.session)

    with timing("draw", tags={"type": "pure_fiction_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hsr.pure_fiction.PureFictionCard(
                data, season, draw_input.locale.value, translator
            ).draw,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_apc_shadow_card(
    draw_input: DrawInput,
    data: StarRailAPCShadow,
    season: StarRailChallengeSeason,
    translator: Translator,
) -> File:
    for floor in data.floors:
        icons = [chara.icon for chara in floor.node_1.avatars + floor.node_2.avatars]
        await download_images(icons, "apc-shadow", draw_input.session)

    with timing("draw", tags={"type": "apc_shadow_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hsr.apc_shadow.APCShadowCard(
                data, season, draw_input.locale.value, translator
            ).draw,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_img_theater_card(
    draw_input: DrawInput,
    data: ImgTheaterData,
    chara_consts: dict[int, int],
    translator: Translator,
) -> File:
    for act in data.acts:
        icons = [chara.icon for chara in act.characters]
        await download_images(icons, "img-theater", draw_input.session)

    with timing("draw", tags={"type": "img_theater_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.genshin.ImgTheaterCard(
                data, chara_consts, draw_input.locale.value, translator
            ).draw,
        )

    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_zzz_notes_card(
    draw_input: DrawInput,
    notes: ZZZNotes,
    translator: Translator,
) -> BytesIO:
    with timing("draw", tags={"type": "zzz_notes_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.zzz.draw_zzz_notes,
            notes,
            draw_input.locale.value,
            translator,
            draw_input.dark_mode,
        )
    return buffer


async def fetch_zzz_draw_data(
    agents: Sequence[ZZZFullAgent], *, template: Literal[1, 2]
) -> ZZZDrawData:
    agent_full_names: dict[str, AgentNameData] = {}

    async with hakushin.HakushinAPI(hakushin.Game.ZZZ) as api:
        characters = await api.fetch_characters()
        for agent in agents:
            chara_detail = await api.fetch_character_detail(agent.id)
            agent_full_names[str(agent.id)] = AgentNameData(
                short_name=chara_detail.name,
                full_name=chara_detail.info.full_name
                if chara_detail.info is not None
                else chara_detail.name,
            )
        if template == 2:
            agent_images = {str(char.id): char.phase_3_cinema_art for char in characters}
        else:
            agent_images = {str(char.id): char.image for char in characters}

        items = await api.fetch_items()
        disc_pos = {"[1]", "[2]", "[3]", "[4]", "[5]", "[6]"}
        disc_icons = {
            str(item.id): item.icon for item in items if any(pos in item.name for pos in disc_pos)
        }

    return ZZZDrawData(agent_full_names, agent_images, disc_icons)


async def draw_zzz_build_card(
    draw_input: DrawInput,
    agent: ZZZFullAgent,
    *,
    card_data: dict[str, Any],
    color: str | None,
    template: Literal[1, 2],
) -> BytesIO:
    draw_data = await fetch_zzz_draw_data([agent], template=template)

    image = draw_data.agent_images[str(agent.id)]
    urls: list[str] = []
    urls.append(image)
    urls.extend(draw_data.disc_icons.values())
    if agent.w_engine is not None:
        urls.append(agent.w_engine.icon)
    await download_images(urls, "zzz-build-card", draw_input.session)

    with timing("draw", tags={"type": "zzz_build_card"}):
        card = funcs.zzz.ZZZAgentCard(
            agent,
            locale=draw_input.locale.value,
            name_data=draw_data.name_data.get(str(agent.id)),
            image_url=image,
            card_data=card_data,
            disc_icons=draw_data.disc_icons,
            color=color,
        )
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            card.draw,
        )
    return buffer


async def draw_zzz_characters_card(
    draw_input: DrawInput,
    agents: Sequence[ZZZFullAgent],
    translator: Translator,
) -> File:
    urls: list[str] = []
    for agent in agents:
        urls.append(agent.banner_icon)
        if agent.w_engine is not None:
            urls.append(agent.w_engine.icon)

    await download_images(urls, "zzz-characters", draw_input.session)
    with timing("draw", tags={"type": "zzz_character_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.zzz.draw_big_agent_card,
            agents,
            draw_input.dark_mode,
            draw_input.locale.value,
            translator,
        )
    buffer.seek(0)

    return File(buffer, filename=draw_input.filename)


async def draw_honkai_suits_card(
    draw_input: DrawInput, suits: Sequence[FullBattlesuit], translator: Translator
) -> File:
    urls: list[str] = []
    for suit in suits:
        urls.append(suit.tall_icon.replace(" ", ""))
        urls.append(suit.weapon.icon)
        for stig in suit.stigmata:
            urls.append(stig.icon)

    await download_images(urls, "honkai-characters", draw_input.session)
    with timing("draw", tags={"type": "honkai_suits_card"}):
        buffer = await draw_input.loop.run_in_executor(
            draw_input.executor,
            funcs.hoyo.honkai.draw_big_suit_card,
            suits,
            draw_input.locale.value,
            draw_input.dark_mode,
            translator,
        )
    buffer.seek(0)
    return File(buffer, filename=draw_input.filename)


async def draw_zzz_team_card(
    draw_input: DrawInput,
    agents: Sequence[ZZZFullAgent],
    agent_colors: dict[str, str],
    agent_images: dict[str, str],
) -> BytesIO:
    draw_data = await fetch_zzz_draw_data(agents, template=1)

    urls = list(agent_images.values())
    urls.extend(agent.w_engine.icon for agent in agents if agent.w_engine is not None)
    urls.extend(draw_data.disc_icons.values())
    await download_images(urls, "zzz-team-card", draw_input.session)

    card = funcs.zzz.ZZZTeamCard(
        locale=draw_input.locale.value,
        agents=agents,
        agent_colors=agent_colors,
        agent_images=agent_images,
        name_datas=draw_data.name_data,
        disc_icons=draw_data.disc_icons,
    )
    with timing("draw", tags={"type": "zzz_team_card"}):
        buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    return buffer


async def draw_hsr_team_card(
    draw_input: DrawInput,
    characters: Sequence[HoyolabHSRCharacter | enka.hsr.Character],
    character_images: dict[str, str],
    character_colors: dict[str, str],
) -> BytesIO:
    urls: list[str] = list(character_images.values())
    for character in characters:
        if character.light_cone is not None:
            urls.append(character.light_cone.icon.image)
            if isinstance(character, enka.hsr.Character):
                urls.extend([stat.icon for stat in character.light_cone.stats])
        urls.extend([trace.icon for trace in character.traces])
        urls.extend([relic.icon for relic in character.relics])
        if isinstance(character, enka.hsr.Character):
            urls.extend([stat.icon for stat in character.stats.values()])
        else:
            urls.extend([stat.icon for stat in character.stats])

    await download_images(urls, "hsr-team-card", draw_input.session)

    with timing("draw", tags={"type": "hsr_team_card"}):
        card = funcs.hsr.HSRTeamCard(
            locale=draw_input.locale.value,
            characters=characters,
            character_images=character_images,
            character_colors=character_colors,
        )
        buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)
    return buffer


async def draw_gi_team_card(
    draw_input: DrawInput,
    characters: Sequence[enka.gi.Character],
    character_images: dict[str, str],
) -> BytesIO:
    urls: list[str] = list(character_images.values())
    for character in characters:
        urls.extend([talent.icon for talent in character.talents])
        urls.extend([const.icon for const in character.constellations])
        urls.extend([artifact.icon for artifact in character.artifacts])
        urls.append(character.weapon.icon)

    await download_images(urls, "gi-team-card", draw_input.session)

    card = funcs.genshin.GITeamCard(
        locale=draw_input.locale.value,
        dark_mode=draw_input.dark_mode,
        characters=characters,
        character_images=character_images,
    )
    with timing("draw", tags={"type": "gi_team_card"}):
        buffer = await draw_input.loop.run_in_executor(draw_input.executor, card.draw)

    return buffer
