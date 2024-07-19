from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

import discord
from cachetools import TTLCache, cached
from discord import utils as dutils
from genshin.models import ZZZSkillType
from PIL import Image, ImageDraw

from hoyo_buddy.bot.translator import LevelStr, Translator
from hoyo_buddy.draw.drawer import WHITE, Drawer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from genshin.models.zzz.character import ZZZFullAgent


def cache_key(agent: ZZZFullAgent, dark_mode: bool, locale: str, **kwargs: Any) -> str:  # noqa: ARG001
    return f"{agent.id}-{dark_mode}-{locale}"


@cached(cache=TTLCache(maxsize=64, ttl=180), key=cache_key)
def draw_agent_small_card(
    agent: ZZZFullAgent,
    *,
    dark_mode: bool,
    locale: str,
    translator: Translator,
    mask: Image.Image,
    card: Image.Image,
    circle: Image.Image,
    level_bar: Image.Image,
    skill_bar: Image.Image,
    engine_block: Image.Image,
) -> Image.Image:
    im = card.copy()
    draw = ImageDraw.Draw(im)
    drawer = Drawer(
        draw,
        folder="zzz-characters",
        dark_mode=dark_mode,
        locale=discord.Locale(locale),
        translator=translator,
    )

    # Banner icon
    icon = drawer.open_static(agent.banner_icon, size=(880, 458))
    icon = drawer.crop_with_mask(icon, mask)
    im.paste(icon, (-204, 0), icon)

    # Rank
    im.paste(circle, (29, 29), circle)
    drawer.write(
        str(agent.rank), size=58, position=(69, 69), style="medium", anchor="mm", color=WHITE
    )

    # Level
    im.paste(level_bar, (29, 362), level_bar)
    drawer.write(
        LevelStr(agent.level),
        size=42,
        position=(107, 394),
        style="medium",
        anchor="mm",
        color=WHITE,
    )

    # W-engine
    im.paste(engine_block, (588, 45), engine_block)
    if agent.w_engine is not None:
        icon = drawer.open_static(agent.w_engine.icon, size=(268, 268))
        im.paste(icon, (593, 49), icon)

        im.paste(circle, (765, 214), circle)
        drawer.write(
            str(agent.w_engine.refinement),
            size=58,
            position=(805, 254),
            style="medium",
            anchor="mm",
            color=WHITE,
        )

    # Skill
    im.paste(skill_bar, (457, 362), skill_bar)
    skill_order = (
        ZZZSkillType.BASIC_ATTACK,
        ZZZSkillType.DODGE,
        ZZZSkillType.ASSIST,
        ZZZSkillType.SPECIAL_ATTACK,
        ZZZSkillType.CHAIN_ATTACK,
        ZZZSkillType.CORE_SKILL,
    )
    skill_levels: list[int] = []
    for skill_type in skill_order:
        skill = dutils.get(agent.skills, type=skill_type)
        if skill is None:
            continue
        skill_levels.append(skill.level)
    text = "/".join(str(level) for level in skill_levels)
    drawer.write(
        text,
        size=42,
        position=(661, 394),
        style="medium",
        anchor="mm",
        color=WHITE if dark_mode else (95, 95, 95),
    )

    return im


def draw_big_agent_card(
    agents: Sequence[ZZZFullAgent], dark_mode: bool, locale: str, translator: Translator
) -> BytesIO:
    asset_path = "hoyo-buddy-assets/assets/zzz-characters"
    theme = "dark" if dark_mode else "light"

    # Open assets
    mask = Image.open(f"{asset_path}/mask_{theme}.png")
    card = Image.open(f"{asset_path}/card_{theme}.png")
    circle = Image.open(f"{asset_path}/circle_{theme}.png")
    level_bar = Image.open(f"{asset_path}/level_bar_{theme}.png")
    skill_bar = Image.open(f"{asset_path}/skill_bar_{theme}.png")
    engine_block = Image.open(f"{asset_path}/engine_block_{theme}.png")

    cards: list[Image.Image] = [
        draw_agent_small_card(
            agent,
            dark_mode=dark_mode,
            locale=locale,
            translator=translator,
            mask=mask,
            card=card,
            circle=circle,
            level_bar=level_bar,
            skill_bar=skill_bar,
            engine_block=engine_block,
        )
        for agent in agents
    ]

    card_height = card.height
    card_width = card.width
    card_x_padding = 38
    card_y_padding = 30
    card_start_pos = (65, 70)

    max_card_per_col = 7
    total_card = len(cards)
    if total_card < max_card_per_col:
        max_card_per_col = total_card
    col_num = total_card // max_card_per_col + 1
    if total_card % max_card_per_col == 0:
        col_num -= 1

    big_card_height = (
        card_height * max_card_per_col
        + card_y_padding * (max_card_per_col - 1)
        + card_start_pos[1] * 2
    )
    big_card_width = card_width * col_num + card_x_padding * (col_num - 1) + card_start_pos[0] * 2

    im = Image.new(
        "RGBA",
        (big_card_width, big_card_height),
        (33, 33, 33) if dark_mode else (239, 239, 239),
    )

    for i, card in enumerate(cards):
        col = i // max_card_per_col
        row = i % max_card_per_col
        x = card_start_pos[0] + col * (card_width + card_x_padding)
        y = card_start_pos[1] + row * (card_height + card_y_padding)
        im.paste(card, (x, y), card)

    buffer = BytesIO()
    im.save(buffer, format="WEBP", quality=80)
    return buffer
