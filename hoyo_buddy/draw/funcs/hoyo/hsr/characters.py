from __future__ import annotations

import io
from typing import TYPE_CHECKING

from discord import Locale
from genshin.models import StarRailDetailCharacter as HSRCharacter
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import DARK_SURFACE, LIGHT_SURFACE, Drawer
from hoyo_buddy.l10n import LevelStr, LocaleStr
from hoyo_buddy.models import DynamicBKInput, UnownedHSRCharacter

if TYPE_CHECKING:
    from collections.abc import Sequence


WEAPON_ICON_POS = (356, 17)
WEAPON_ICON_SIZES = (102, 102)


def draw_character_card(
    characters: Sequence[HSRCharacter | UnownedHSRCharacter],
    pc_icons: dict[str, str],
    dark_mode: bool,
    locale_: str,
) -> io.BytesIO:
    locale = Locale(locale_)
    c_cards: dict[str, Image.Image] = {}

    for character in characters:
        talent = (
            "/".join(str(s.level) for s in character.skills[:4])
            if isinstance(character, HSRCharacter)
            else ""
        )
        card = draw_small_hsr_chara_card(talent, dark_mode, character, locale)
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
    drawer = Drawer(draw, folder="hsr-characters", dark_mode=dark_mode)

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
            pos = (x, y + 2)
            icon = drawer.open_static(pc_icon_url)
            icon = drawer.resize_crop(icon, (189, 184))
            icon = drawer.mask_image_with_image(icon, drawer.open_asset("pc_icon_mask.png"))
            background.paste(icon, pos, icon)

    fp = io.BytesIO()
    background.save(fp, format="PNG")
    return fp


def draw_small_hsr_chara_card(
    talent_str: str, dark_mode: bool, character: HSRCharacter | UnownedHSRCharacter, locale: Locale
) -> Image.Image:
    im = Drawer.open_image(
        f"hoyo-buddy-assets/assets/hsr-characters/{'dark' if dark_mode else 'light'}_{character.element.title()}.png"
    )

    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="hsr-characters", dark_mode=dark_mode)

    if isinstance(character, UnownedHSRCharacter):
        return im

    text = LevelStr(character.level)
    drawer.write(text, size=31, position=(230, 35), locale=locale, style="medium")
    text = LocaleStr(
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
