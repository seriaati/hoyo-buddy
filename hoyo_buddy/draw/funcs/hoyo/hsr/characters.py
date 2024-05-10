from __future__ import annotations

import io
from typing import TYPE_CHECKING

from cachetools import LRUCache, cached
from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.draw.drawer import DARK_SURFACE, LIGHT_SURFACE, Drawer
from hoyo_buddy.models import DynamicBKInput

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.bot.translator import Translator

PC_ICON_OFFSETS = (0, 38)
PC_ICON_SIZES = (208, 146)
WEAPON_ICON_POS = (356, 17)
WEAPON_ICON_SIZES = (102, 102)


def draw_character_card(
    characters: Sequence[genshin.models.StarRailDetailCharacter],
    pc_icons: dict[str, str],
    dark_mode: bool,
    translator: Translator,
    locale_: str,
) -> io.BytesIO:
    locale = Locale(locale_)
    c_cards: dict[str, Image.Image] = {}

    for character in characters:
        talent = "/".join(str(s.level) for s in character.skills[:4])
        card = draw_small_hsr_chara_card(talent, dark_mode, character, translator, locale)
        c_cards[str(character.id)] = card

    first_card = next(iter(c_cards.values()))
    bk_input = DynamicBKInput(
        top_padding=35,
        bottom_padding=5,
        left_padding=10,
        right_padding=5,
        card_width=first_card.width,
        card_height=first_card.height,
        card_x_padding=5,
        card_y_padding=35,
        card_num=len(c_cards),
        background_color=DARK_SURFACE if dark_mode else LIGHT_SURFACE,
        draw_title=False,
    )
    background, max_card_num = Drawer.draw_dynamic_background(bk_input)
    draw = ImageDraw.Draw(background)
    drawer = Drawer(draw, folder="gi-characters", dark_mode=dark_mode)

    for index, card in enumerate(c_cards.values()):
        x = (index // max_card_num) * (
            bk_input.card_width + bk_input.card_x_padding
        ) + bk_input.left_padding
        y = 0
        if isinstance(bk_input.top_padding, int):
            y = (index % max_card_num) * (
                bk_input.card_height + bk_input.card_y_padding
            ) + bk_input.top_padding
        background.paste(card, (x, y), card)
        character_id = list(c_cards.keys())[index]
        pc_icon_url = pc_icons.get(character_id)
        if pc_icon_url:
            offset = PC_ICON_OFFSETS
            pos = (x + offset[0], y + offset[1])
            icon = drawer.open_static(pc_icon_url, size=PC_ICON_SIZES)
            background.paste(icon, pos, icon)

    fp = io.BytesIO()
    background.save(fp, format="WEBP", loseless=True)
    return fp


def hsr_cache_key(
    talent_str: str,
    dark_mode: bool,
    character: genshin.models.StarRailDetailCharacter,
    _: Translator,
    locale: Locale,
) -> str:
    return (
        f"{talent_str}_"
        f"{dark_mode}_"
        f"{character.id}_"
        f"{character.level}_"
        f"{character.rank}_"
        f"{character.equip.rank if character.equip else 0}_"
        f"{character.equip.id if character.equip else 0}_"
        f"{character.element}"
        f"{locale.value}"
    )


@cached(LRUCache(maxsize=128), key=hsr_cache_key)
def draw_small_hsr_chara_card(
    talent_str: str,
    dark_mode: bool,
    character: genshin.models.StarRailDetailCharacter,
    translator: Translator,
    locale: Locale,
) -> Image.Image:
    im = Image.open(
        f"hoyo-buddy-assets/assets/hsr-characters/{'dark' if dark_mode else 'light'}_{character.element.title()}.png"
    )

    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="gi-characters", dark_mode=dark_mode, translator=translator)

    text = LocaleStr("Lv.{level}", key="level_str", level=character.level)
    drawer.write(text, size=31, position=(230, 35), locale=locale, style="medium")
    text = LocaleStr(
        "E{eidolon}S{superimpose}",
        key="eidolon_superimpose_str",
        eidolon=character.rank,
        superimpose=character.equip.rank if character.equip else 0,
    )
    drawer.write(text, size=31, position=(230, 77), locale=locale, style="medium")
    drawer.write(talent_str, size=18, position=(345, 151), anchor="mm")

    if character.equip is not None:
        weapon_icon = drawer.open_static(character.equip.icon, size=WEAPON_ICON_SIZES)
        im.paste(weapon_icon, WEAPON_ICON_POS, weapon_icon)

    return im
