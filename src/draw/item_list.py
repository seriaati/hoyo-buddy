from io import BytesIO
from typing import TYPE_CHECKING

from cachetools import LRUCache, cached
from PIL import Image, ImageDraw

from ..models import ItemWithDescription, ItemWithTrailing
from .draw import (
    DARK_ON_SURFACE,
    DARK_ON_SURFACE_VARIANT,
    DARK_SURFACE,
    LIGHT_ON_SURFACE,
    LIGHT_SURFACE,
    Drawer,
)

if TYPE_CHECKING:
    from discord import Locale


def cache_key(
    items: list[ItemWithDescription] | list[ItemWithTrailing], dark_mode: bool, locale: "Locale"
) -> str:
    items_key = "_".join(
        f"{item.title}_{item.description if isinstance(item, ItemWithDescription) else item.trailing}"
        for item in items
    )
    return f"{items_key}_{dark_mode}_{locale.value}"


@cached(cache=LRUCache(maxsize=100), key=cache_key)
def draw_item_list(
    items: list[ItemWithDescription] | list[ItemWithTrailing], dark_mode: bool, locale: "Locale"
) -> BytesIO:
    is_trailing = any(isinstance(item, ItemWithTrailing) for item in items)

    # Variables
    card_size = (720, 112) if is_trailing else (720, 144)
    overall_top_bottom_padding = 16
    icon_size = (80, 80)
    icon_top_left_padding = 16 if is_trailing else 32
    title_top_padding = 32 if is_trailing else 28
    title_left_padding = 144
    description_top_padding = 76
    description_left_padding = 144
    trailing_top_padding = 40
    trailing_left_pading = 644

    rows = min(6, len(items))
    columns = 2 if len(items) > 6 else 1

    im = Image.new(
        "RGB",
        (card_size[0] * columns, card_size[1] * rows + overall_top_bottom_padding * 2),
        color=DARK_SURFACE if dark_mode else LIGHT_SURFACE,
    )
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="draw-list", dark_mode=dark_mode, locale=locale)

    for index, item in enumerate(items):
        pos = (
            card_size[0] if index >= rows else 0,
            card_size[1] * (index % rows) + overall_top_bottom_padding,
        )
        icon = drawer.open_static(item.icon, size=icon_size)
        icon = drawer.circular_crop(icon)
        im.paste(icon, (pos[0] + icon_top_left_padding, pos[1] + icon_top_left_padding), icon)

        drawer.write(
            item.title,
            size=32,
            position=(pos[0] + title_left_padding, pos[1] + title_top_padding),
            color=DARK_ON_SURFACE if drawer.dark_mode else LIGHT_ON_SURFACE,
            style="medium",
        )

        if isinstance(item, ItemWithTrailing):
            drawer.write(
                item.trailing,
                size=22,
                position=(pos[0] + trailing_left_pading, pos[1] + trailing_top_padding),
                color=DARK_ON_SURFACE_VARIANT if drawer.dark_mode else LIGHT_ON_SURFACE,
            )
        elif isinstance(item, ItemWithDescription):
            drawer.write(
                item.description,
                size=28,
                position=(pos[0] + description_left_padding, pos[1] + description_top_padding),
                color=DARK_ON_SURFACE_VARIANT if drawer.dark_mode else LIGHT_ON_SURFACE,
            )

    buffer = BytesIO()
    im.save(buffer, format="WEBP", loseless=True)
    return buffer
