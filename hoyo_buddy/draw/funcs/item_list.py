from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.models import ItemWithDescription, ItemWithTrailing

from ..drawer import (
    DARK_ON_SURFACE,
    DARK_ON_SURFACE_CONTAINER_HIGHEST,
    DARK_SURFACE,
    LIGHT_ON_SURFACE,
    LIGHT_SURFACE,
    Drawer,
)

if TYPE_CHECKING:
    from io import BytesIO

    from hoyo_buddy.enums import Locale


def draw_item_list(
    items: list[ItemWithDescription] | list[ItemWithTrailing], dark_mode: bool, locale: Locale
) -> BytesIO:
    is_trailing = any(isinstance(item, ItemWithTrailing) for item in items)

    # Variables
    card_size = (720, 112) if is_trailing else (720, 144)
    overall_top_bottom_padding = 16
    icon_size = (80, 80)
    icon_top_left_padding = 16 if is_trailing else 32
    title_top_padding = card_size[1] // 2 if is_trailing else 28
    title_left_padding = 144
    description_top_padding = 76
    description_left_padding = 144

    rows = min(6, len(items))
    columns = 2 if len(items) > 6 else 1

    im = Image.new(
        "RGB",
        (card_size[0] * columns, card_size[1] * rows + overall_top_bottom_padding * 2),
        color=DARK_SURFACE if dark_mode else LIGHT_SURFACE,
    )
    draw = ImageDraw.Draw(im)
    drawer = Drawer(draw, folder="item-list", dark_mode=dark_mode, locale=locale)

    for index, item in enumerate(items):
        pos = (
            card_size[0] if index >= rows else 0,
            card_size[1] * (index % rows) + overall_top_bottom_padding,
        )
        if item.icon is not None:
            icon = drawer.open_static(item.icon, size=icon_size)
            icon = drawer.circular_crop(icon)
            im.paste(icon, (pos[0] + icon_top_left_padding, pos[1] + icon_top_left_padding), icon)

        tbox = None
        if isinstance(item, ItemWithTrailing):
            tbox = drawer.write(
                item.trailing,
                size=22,
                position=(pos[0] + card_size[0] - 48, pos[1] + 56),
                color=DARK_ON_SURFACE_CONTAINER_HIGHEST if drawer.dark_mode else LIGHT_ON_SURFACE,
                anchor="rm",
            )
        else:
            drawer.write(
                item.description,
                size=28,
                position=(pos[0] + description_left_padding, pos[1] + description_top_padding),
                color=DARK_ON_SURFACE_CONTAINER_HIGHEST if drawer.dark_mode else LIGHT_ON_SURFACE,
            )

        drawer.write(
            item.title,
            size=32,
            position=(pos[0] + title_left_padding, pos[1] + title_top_padding),
            color=DARK_ON_SURFACE if drawer.dark_mode else LIGHT_ON_SURFACE,
            style="medium",
            anchor="lm" if is_trailing else None,
            max_width=528 if tbox is None else tbox.left - 32 - title_left_padding,
        )

    return Drawer.save_image(im)
