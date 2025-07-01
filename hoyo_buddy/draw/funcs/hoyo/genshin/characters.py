from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import BLACK, DARK_SURFACE, LIGHT_SURFACE, WHITE, Drawer
from hoyo_buddy.l10n import LevelStr, LocaleStr
from hoyo_buddy.models import DynamicBKInput, UnownedGICharacter

if TYPE_CHECKING:
    import io
    from collections.abc import Sequence

    from genshin.models import GenshinDetailCharacter as GICharacter

    from hoyo_buddy.enums import Locale


PC_ICON_OFFSETS = (-65, -32)
PC_ICON_SIZES = (343, 275)
WEAPON_ICON_POS = (365, 26)
WEAPON_ICON_SIZES = (84, 84)


def draw_character_card(
    characters: Sequence[GICharacter | UnownedGICharacter],
    pc_icons: dict[str, str],
    talent_orders: dict[str, list[int]],
    dark_mode: bool,
    locale: Locale,
) -> io.BytesIO:
    c_cards: dict[str, Image.Image] = {}

    for character in characters:
        if isinstance(character, UnownedGICharacter):
            talent_str = ""
        else:
            talent_order = talent_orders.get(str(character.id))
            if talent_order is None:
                # Get the first 3 talents
                talents = character.skills[:3]
            else:
                talents = [
                    next((t for t in character.skills if t.id == talent_id), None)
                    for talent_id in talent_order
                ]

            talent_str = " / ".join(str(t.level) if t is not None else "?" for t in talents)  # noqa: RUF001

        card = draw_small_gi_chara_card(talent_str, dark_mode, character, locale)
        c_cards[str(character.id)] = card

    first_card = next(iter(c_cards.values()), None)
    if first_card is None:
        msg = "No first card"
        raise ValueError(msg)

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
    mask = drawer.open_asset("mask.png")

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
                icon = drawer.mask_image_with_image(icon, mask)
            background.paste(icon, pos, icon)

    return Drawer.save_image(background)


def draw_small_gi_chara_card(
    talent_str: str, dark_mode: bool, character: GICharacter | UnownedGICharacter, locale: Locale
) -> Image.Image:
    prefix = "dark" if dark_mode else "light"
    im = Drawer.open_image(
        f"hoyo-buddy-assets/assets/gi-characters/{prefix}_{character.element.title()}.png"
    )

    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="gi-characters", dark_mode=dark_mode)

    if isinstance(character, UnownedGICharacter):
        return im

    text = LocaleStr(
        key="const_refine_str", const=character.constellation, refine=character.weapon.refinement
    )
    drawer.write(text, size=31, position=(236, 32), locale=locale, style="medium")
    drawer.write(
        LevelStr(character.level), size=31, position=(236, 72), locale=locale, style="medium"
    )

    friendship = drawer.open_asset(f"{prefix}_Friendship.png")
    friendship_pos = (240, 138)
    im.paste(friendship, friendship_pos, friendship)

    friend_tbox = drawer.write(
        str(character.friendship),
        size=24,
        position=(
            friendship_pos[0] + friendship.width + 4,
            friendship_pos[1] + friendship.height // 2,
        ),
        anchor="lm",
        style="bold",
    )
    talent_tbox = drawer.write(
        talent_str,
        size=24,
        position=(457 - 16, friendship_pos[1] + friendship.height // 2),
        anchor="rm",
        style="bold",
    )

    size = 4
    space = talent_tbox.left - friend_tbox.right
    x_start = friend_tbox.right + space // 2 - size // 2
    y_start = friend_tbox[1] + (friend_tbox[3] - friend_tbox[1]) // 2 - size // 2
    draw.ellipse(
        (x_start, y_start, x_start + size, y_start + size), fill=WHITE if dark_mode else BLACK
    )

    weapon_icon = drawer.open_static(character.weapon.icon, size=WEAPON_ICON_SIZES)
    im.paste(weapon_icon, WEAPON_ICON_POS, weapon_icon)

    return im
