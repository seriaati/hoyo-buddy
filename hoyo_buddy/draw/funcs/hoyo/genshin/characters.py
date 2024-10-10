from __future__ import annotations

import io
from typing import TYPE_CHECKING

from cachetools import TTLCache, cached
from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import BLACK, DARK_SURFACE, LIGHT_SURFACE, WHITE, Drawer
from hoyo_buddy.l10n import LevelStr, LocaleStr
from hoyo_buddy.models import DynamicBKInput, UnownedGICharacter

if TYPE_CHECKING:
    from collections.abc import Sequence

    from genshin.models import GenshinDetailCharacter as GICharacter

    from hoyo_buddy.l10n import Translator

PC_ICON_OFFSETS = (0, -29)
PC_ICON_SIZES = (214, 214)
WEAPON_ICON_POS = (365, 26)
WEAPON_ICON_SIZES = (84, 84)


def draw_character_card(
    characters: Sequence[GICharacter | UnownedGICharacter],
    pc_icons: dict[str, str],
    talent_orders: dict[int, list[int]],
    dark_mode: bool,
    translator: Translator,
    locale_: str,
) -> io.BytesIO:
    locale = Locale(locale_)
    c_cards: dict[str, Image.Image] = {}

    for character in characters:
        if isinstance(character, UnownedGICharacter):
            talent_str = ""
        else:
            talent_order = talent_orders.get(character.id)
            if talent_order is None:
                # Get the first 3 talents
                talents = character.skills[:3]
            else:
                talents = [
                    next((t for t in character.skills if t.id == talent_id), None)
                    for talent_id in talent_order
                ]

            talent_str = "/".join(str(t.level) if t is not None else "?" for t in talents)

        card = draw_small_gi_chara_card(talent_str, dark_mode, character, translator, locale)
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
            if "ambr" in pc_icon_url:
                icon = drawer.open_static(pc_icon_url)
                icon = drawer.middle_crop(icon, PC_ICON_SIZES)
            else:
                icon = drawer.open_static(pc_icon_url, size=PC_ICON_SIZES)
            background.paste(icon, pos, icon)

    fp = io.BytesIO()
    background.save(fp, format="PNG")
    return fp


def gi_cache_key(
    talent_str: str,
    dark_mode: bool,
    character: GICharacter | UnownedGICharacter,
    _: Translator,
    locale: Locale,
) -> str:
    if isinstance(character, UnownedGICharacter):
        return f"{dark_mode}_{character.id}_{character.element}"
    return (
        f"{talent_str}_"
        f"{dark_mode}_"
        f"{character.id}_"
        f"{character.level}_"
        f"{character.friendship}_"
        f"{character.constellation}_"
        f"{character.weapon.refinement}_"
        f"{character.weapon.id}_"
        f"{character.element}"
        f"{locale.value}"
    )


@cached(TTLCache(maxsize=64, ttl=180), key=gi_cache_key)
def draw_small_gi_chara_card(
    talent_str: str,
    dark_mode: bool,
    character: GICharacter | UnownedGICharacter,
    translator: Translator,
    locale: Locale,
) -> Image.Image:
    im = Drawer.open_image(
        f"hoyo-buddy-assets/assets/gi-characters/{'dark' if dark_mode else 'light'}_{character.element.title()}.png"
    )

    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="gi-characters", dark_mode=dark_mode, translator=translator)

    if isinstance(character, UnownedGICharacter):
        return im

    text = LocaleStr(
        key="const_refine_str", const=character.constellation, refine=character.weapon.refinement
    )
    drawer.write(text, size=31, position=(236, 32), locale=locale, style="medium")
    drawer.write(
        LevelStr(character.level), size=31, position=(236, 72), locale=locale, style="medium"
    )

    friend_textbbox = drawer.write(
        str(character.friendship), size=18, position=(284, 151), anchor="mm"
    )
    talent_textbbox = drawer.write(talent_str, size=18, position=(405, 151), anchor="mm")

    size = 4
    space = talent_textbbox[0] - friend_textbbox[2]
    x_start = friend_textbbox[2] + space // 2 - size // 2
    y_start = friend_textbbox[1] + (friend_textbbox[3] - friend_textbbox[1]) // 2 - size // 2
    draw.ellipse(
        (x_start, y_start, x_start + size, y_start + size), fill=WHITE if dark_mode else BLACK
    )

    weapon_icon = drawer.open_static(character.weapon.icon, size=WEAPON_ICON_SIZES)
    im.paste(weapon_icon, WEAPON_ICON_POS, weapon_icon)

    return im
