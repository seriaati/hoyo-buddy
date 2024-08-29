from __future__ import annotations

import io
from typing import TYPE_CHECKING

from cachetools import LRUCache, cached
from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import DARK_SURFACE, LIGHT_SURFACE, WHITE, Drawer
from hoyo_buddy.l10n import LocaleStr, Translator

if TYPE_CHECKING:
    import ambr

    from hoyo_buddy.models import FarmData

__all__ = ("draw_farm_card",)


def cache_key(farm_data: list[FarmData], locale: str, dark_mode: bool, _: Translator) -> str:
    return f"{locale}-{dark_mode}-{'-'.join(str(data.domain.id) for data in farm_data)}"


@cached(LRUCache(maxsize=32), key=cache_key)
def draw_farm_card(
    farm_data: list[FarmData], locale_: str, dark_mode: bool, translator: Translator
) -> io.BytesIO:
    def get_domain_title(domain: ambr.Domain, locale: Locale, translator: Translator) -> str:
        """Get the title of a GI domain based on its name and city, assuming the language is English."""
        city_name = translator.translate(LocaleStr(custom_str=domain.city.name.title()), locale)
        domain_type = (
            LocaleStr(key="characters") if "Mastery" in domain.name else LocaleStr(key="weapons")
        )
        domain_type_name = translator.translate(domain_type, locale)
        return f"{domain_type_name} ({city_name})"

    locale = Locale(locale_)
    mode = "dark" if dark_mode else "light"
    basic_cards: list[Image.Image] = []

    for data in farm_data:
        basic_card: Image.Image = Drawer.open_image(
            f"hoyo-buddy-assets/assets/farm/{mode}_card.png"
        )
        draw = ImageDraw.Draw(basic_card)
        drawer = Drawer(draw, folder="farm", dark_mode=dark_mode, translator=translator)

        item_per_row = 9
        height_per_row = 199
        new_height = basic_card.height + height_per_row * (
            len(data.characters + data.weapons) // (item_per_row + 1)
        )
        basic_card = basic_card.resize((basic_card.width, new_height))

        lid = drawer.open_asset(f"{data.domain.city.name.lower()}.png")
        basic_card.paste(lid, (8, 3), lid)

        draw = ImageDraw.Draw(basic_card)
        drawer = Drawer(
            draw, folder="farm", dark_mode=dark_mode, translator=translator, locale=locale
        )

        drawer.write(
            get_domain_title(data.domain, locale, translator),
            size=48,
            position=(32, lid.height // 2 + 3),
            style="bold",
            color=WHITE,
            anchor="lm",
        )

        index = 0
        for reward in data.domain.rewards:
            if len(str(reward.id)) != 6:
                continue
            icon = drawer.open_static(reward.icon, size=(82, 82))
            basic_card.paste(icon, (1286 + (-85) * index, 17), icon)
            index += 1

        starting_pos = (50, 154)
        dist_between_items = 148
        next_row_y_up = 152
        for index, item in enumerate(data.characters + data.weapons):
            if index % item_per_row == 0 and index != 0:
                starting_pos = (50, starting_pos[1] + next_row_y_up)

            icon = drawer.open_static(item.icon, size=(114, 114))
            basic_card.paste(icon, starting_pos, icon)
            starting_pos = (starting_pos[0] + dist_between_items, starting_pos[1])

        basic_cards.append(basic_card)

    top_bot_margin = 44
    right_left_margin = 56
    x_padding_between_cards = 80
    y_padding_between_cards = 60
    card_width_offset = -50
    card_per_column = 4
    col_num = (
        len(basic_cards) // card_per_column + 1
        if len(basic_cards) % card_per_column != 0
        else len(basic_cards) // card_per_column
    )

    background_width = (
        right_left_margin * 2
        + (basic_cards[0].width + card_width_offset) * col_num
        + x_padding_between_cards * (col_num - 1)
    )

    background_height = top_bot_margin * 2
    card_heights = [card.height for card in basic_cards]
    max_card_height = max(card_heights)
    max_card_height_col = card_heights.index(max_card_height) // 4
    for card in basic_cards[max_card_height_col * 4 : (max_card_height_col + 1) * 4]:
        item_row_num = (card.height - 437) // 199 + 1
        card_height_offset = -114 + (-55 * (item_row_num - 1))
        background_height += card.height + card_height_offset + y_padding_between_cards - 15

    background = Image.new(
        "RGBA", (background_width, background_height), DARK_SURFACE if dark_mode else LIGHT_SURFACE
    )

    x = right_left_margin
    y = top_bot_margin
    for index, card in enumerate(basic_cards):
        item_row_num = (card.height - 437) // 199 + 1
        card_height_offset = -114 + (-55 * (item_row_num - 1))
        if index % card_per_column == 0 and index != 0:
            x += basic_cards[index - 1].width + card_width_offset + x_padding_between_cards
            y = top_bot_margin
        background.paste(card, (x, y), card)
        y += card.height + card_height_offset + y_padding_between_cards

    buffer = io.BytesIO()
    background.save(buffer, format="WEBP", loseless=True)
    return buffer
