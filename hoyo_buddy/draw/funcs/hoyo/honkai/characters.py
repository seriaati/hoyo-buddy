from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.l10n import LevelStr, LocaleStr, Translator

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin


def draw_small_suit_card(
    suit: genshin.models.FullBattlesuit,
    *,
    card: Image.Image,
    mask: Image.Image,
    suit_mask: Image.Image,
    locale: str,
    translator: Translator,
) -> Image.Image:
    im = card.copy()
    draw = ImageDraw.Draw(im)
    drawer = Drawer(
        draw,
        folder="honkai-characters",
        locale=Locale(locale),
        translator=translator,
        dark_mode=True,
    )

    try:
        suit_icon = drawer.open_static(suit.tall_icon.replace(" ", ""), size=(146, 256))
    except FileNotFoundError:
        pass
    else:
        suit_icon = drawer.mask_image_with_image(suit_icon, suit_mask)
        im.paste(suit_icon, (0, 11), suit_icon)

    weapon_icon = drawer.open_static(suit.weapon.icon)
    weapon_icon = drawer.resize_crop(weapon_icon, (75, 75))
    weapon_icon = drawer.mask_image_with_image(weapon_icon, mask)
    im.paste(weapon_icon, (198, 56), weapon_icon)

    start_pos = (198, 156)
    x_diff = 92
    for stig in suit.stigmata:
        stig_icon = drawer.open_static(stig.icon)
        stig_icon = drawer.resize_crop(stig_icon, (75, 75))
        stig_icon = drawer.mask_image_with_image(stig_icon, mask)
        im.paste(stig_icon, start_pos, stig_icon)
        start_pos = (start_pos[0] + x_diff, start_pos[1])

    rarities = {1: "B", 2: "A", 3: "S", 4: "SS", 5: "SSS"}
    rarity_text = LocaleStr(key="honkai_suit_rarity", rarity=rarities[suit.rarity]).translate(
        translator, Locale(locale)
    )
    level_text = LevelStr(suit.level).translate(translator, Locale(locale))
    drawer.write(
        f"{rarity_text}\n{level_text}",
        size=30,
        style="bold",
        position=(290, 94),
        sans=True,
        anchor="lm",
    )

    return im


def draw_big_suit_card(
    suits: Sequence[genshin.models.FullBattlesuit],
    locale: str,
    dark_mode: bool,
    translator: Translator,
) -> BytesIO:
    asset_path = "hoyo-buddy-assets/assets/honkai-characters"
    theme = "dark" if dark_mode else "light"

    # Open assets
    mask = Drawer.open_image(f"{asset_path}/mask.png")
    suit_mask = Drawer.open_image(f"{asset_path}/suit_mask.png")
    card = Drawer.open_image(f"{asset_path}/card_{theme}.png")

    cards: Sequence[Image.Image] = [
        draw_small_suit_card(
            suit,
            card=card,
            mask=mask,
            suit_mask=suit_mask,
            locale=locale,
            translator=translator,
        )
        for suit in suits
    ]

    # Card settings
    card_width = 472
    card_height = 223
    card_x_padding = 44
    card_y_padding = 30
    card_start_pos = (32, 12)

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
        + 36
    )
    big_card_width = card_width * col_num + card_x_padding * (col_num - 1) + card_start_pos[0] * 2

    im = Image.new(
        "RGBA",
        (big_card_width, big_card_height),
        (25, 29, 34) if dark_mode else (227, 239, 255),
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
