from io import BytesIO

from cachetools import LRUCache, cached
from PIL import Image, ImageDraw

from ..hoyo.dataclasses import ItemWithDescription, ItemWithTrailing
from .draw import (
    DARK_ON_SURFACE,
    DARK_ON_SURFACE_VARIANT,
    DARK_SURFACE,
    LIGHT_ON_SURFACE,
    LIGHT_SURFACE,
    Drawer,
)


def cache_key(items: list[ItemWithDescription] | list[ItemWithTrailing], dark_mode: bool) -> str:
    items_key = "_".join(
        f"{item.title}_{item.description if isinstance(item, ItemWithDescription) else item.trailing}"
        for item in items
    )
    return f"{items_key}_{dark_mode}"


@cached(cache=LRUCache(maxsize=100), key=cache_key)
def draw_item_list(
    items: list[ItemWithDescription] | list[ItemWithTrailing], dark_mode: bool
) -> BytesIO:
    is_trailing = any(isinstance(item, ItemWithTrailing) for item in items)

    # Variables
    card_size = (360, 56) if is_trailing else (360, 72)
    overall_top_bottom_padding = 8
    icon_size = (40, 40)
    icon_top_left_padding = 8 if is_trailing else 16
    title_top_padding = 16 if is_trailing else 14
    title_left_padding = 72
    description_top_padding = 38
    description_left_padding = 72
    trailing_top_padding = 20
    trailing_left_pading = 322

    rows = min(6, len(items))
    columns = 2 if len(items) > 6 else 1

    im = Image.new(
        "RGB",
        (card_size[0] * columns, card_size[1] * rows + overall_top_bottom_padding * 2),
        color=DARK_SURFACE if dark_mode else LIGHT_SURFACE,
    )
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="draw-list", dark_mode=dark_mode)

    for index, item in enumerate(items):
        pos = (
            card_size[0] if index >= rows else 0,
            card_size[1] * (index % rows) + overall_top_bottom_padding,
        )
        icon = drawer.open_static(item.icon, size=icon_size)
        im.paste(icon, (pos[0] + icon_top_left_padding, pos[1] + icon_top_left_padding), icon)

        drawer.write(
            item.title,
            size=16,
            position=(pos[0] + title_left_padding, pos[1] + title_top_padding),
            color=DARK_ON_SURFACE if drawer.dark_mode else LIGHT_ON_SURFACE,
        )

        if isinstance(item, ItemWithTrailing):
            drawer.write(
                item.trailing,
                size=11,
                position=(pos[0] + trailing_left_pading, pos[1] + trailing_top_padding),
                color=DARK_ON_SURFACE_VARIANT if drawer.dark_mode else LIGHT_ON_SURFACE,
            )
        elif isinstance(item, ItemWithDescription):
            drawer.write(
                item.description,
                size=14,
                position=(pos[0] + description_left_padding, pos[1] + description_top_padding),
                color=DARK_ON_SURFACE_VARIANT if drawer.dark_mode else LIGHT_ON_SURFACE,
            )

    buffer = BytesIO()
    im.save(buffer, format="WEBP", loseless=True)
    return buffer
