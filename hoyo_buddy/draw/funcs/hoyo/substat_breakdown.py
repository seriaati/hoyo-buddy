"""Substat breakdown strip drawn under build cards, totalling each substat across all gear."""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from hoyo_buddy.draw.drawer import Drawer
    from hoyo_buddy.types import FontStyle

type RGB = tuple[int, int, int]
type Box = tuple[int, int, int, int]


@dataclass(kw_only=True, frozen=True)
class SubstatTotal[T]:
    """A substat's total across all gear."""

    stat: T
    """One of the substat's stats, for its icon."""
    value: float
    is_percent: bool
    decimals: int
    rolls: int
    roll_value: float | None
    """The total in max rolls, None when every roll has the same value."""

    @property
    def formatted_value(self) -> str:
        value = f"{self.value:,.{self.decimals}f}"
        return f"{value}%" if self.is_percent else value


@dataclass(kw_only=True, frozen=True)
class Substat[K, T]:
    """A sub stat on one piece of gear."""

    key: K
    """What the sub stat is totalled by."""
    stat: T
    value: float
    is_percent: bool
    decimals: int
    rolls: int
    max_roll: float | None
    """The gear's highest single roll of the sub stat, None when it has no roll value."""


def total_substats[K, T](
    substats: Iterable[Substat[K, T]], *, order: Iterable[K]
) -> list[SubstatTotal[T]]:
    """Total the sub stats by key, in the given order of keys."""
    groups: defaultdict[K, list[Substat[K, T]]] = defaultdict(list)
    for substat in substats:
        groups[substat.key].append(substat)

    totals: list[SubstatTotal[T]] = []
    for key in order:
        if not (group := groups.get(key)):
            continue
        max_rolls = [s.max_roll for s in group]
        totals.append(
            SubstatTotal(
                stat=group[0].stat,
                value=sum(s.value for s in group),
                is_percent=group[0].is_percent,
                decimals=group[0].decimals,
                rolls=sum(s.rolls for s in group),
                roll_value=None
                if None in max_rolls
                else sum(s.value / m for s, m in zip(group, max_rolls, strict=True) if m),
            )
        )
    return totals


@dataclass(kw_only=True, frozen=True)
class BreakdownStyle:
    value_size: int
    value_style: FontStyle
    value_color: RGB
    label_size: int
    """Size of the roll value fraction's numbers or the roll count."""
    label_style: FontStyle
    label_color: RGB
    icon_size: int
    gap: int
    """Gap between the label, the icon and the value."""
    line_width: int = 2


def parse_stat_value(formatted_value: str) -> float:
    """Parse a formatted stat value like "+5.8%" or "1,024"."""
    return float(formatted_value.strip().lstrip("+").rstrip("%").replace(",", ""))


def extend_image(im: Image.Image, *, at: int, height: int) -> Image.Image:
    """Make the image taller by stretching its row at the given y."""
    extended = Image.new(im.mode, (im.width, im.height + height))
    extended.paste(im.crop((0, 0, im.width, at)), (0, 0))
    extended.paste(im.crop((0, at, im.width, at + 1)).resize((im.width, height)), (0, at))
    extended.paste(im.crop((0, at, im.width, im.height)), (0, at + height))
    return extended


def draw_panel(im: Image.Image, box: Box, *, radius: int, color: tuple[int, int, int, int]) -> None:
    """Draw a rounded panel, blending it with what's below when it's translucent."""
    width, height = box[2] - box[0] + 1, box[3] - box[1] + 1
    layer = Image.new("RGBA", (width, height))
    ImageDraw.Draw(layer).rounded_rectangle((0, 0, width - 1, height - 1), radius, fill=color)
    im.alpha_composite(layer, (box[0], box[1]))


def _label_texts(total: SubstatTotal) -> tuple[str, str | None]:
    if total.roll_value is None:
        return str(total.rolls), None
    return f"{total.roll_value:.1f}", str(total.rolls)


def _text_width(drawer: Drawer, text: str, *, size: int, style: FontStyle) -> int:
    tbox = drawer.write(text, size=size, style=style, position=(0, 0), no_write=True)
    return tbox.right - tbox.left


def _label_width(drawer: Drawer, total: SubstatTotal, style: BreakdownStyle) -> int:
    texts = [t for t in _label_texts(total) if t is not None]
    return max(
        _text_width(drawer, t, size=style.label_size, style=style.label_style) for t in texts
    )


def _entry_width(
    drawer: Drawer, total: SubstatTotal, style: BreakdownStyle, *, label_width: int
) -> int:
    value_width = _text_width(
        drawer, total.formatted_value, size=style.value_size, style=style.value_style
    )
    return label_width + style.icon_size + value_width + style.gap * 2


def _scale_style(style: BreakdownStyle, factor: float) -> BreakdownStyle:
    return replace(
        style,
        value_size=round(style.value_size * factor),
        label_size=round(style.label_size * factor),
        icon_size=round(style.icon_size * factor),
        gap=round(style.gap * factor),
    )


def _draw_label(
    drawer: Drawer, total: SubstatTotal, style: BreakdownStyle, *, x: int, center_y: int, width: int
) -> None:
    """Draw the roll value over the roll count as a fraction, or only the roll count."""
    top, bottom = _label_texts(total)
    color = style.label_color

    if bottom is None:
        drawer.write(
            top,
            size=style.label_size,
            style=style.label_style,
            position=(x, center_y),
            color=color,
            anchor="lm",
        )
        return

    pad = max(1, style.label_size // 8)
    line_top = center_y - style.line_width // 2
    drawer.draw.rectangle((x, line_top, x + width - 1, line_top + style.line_width - 1), color)
    middle_x = x + width / 2
    for text, y, anchor in (
        (top, line_top - pad, "ms"),
        (bottom, line_top + style.line_width + pad, "mt"),
    ):
        drawer.write(
            text,
            size=style.label_size,
            style=style.label_style,
            position=(middle_x, y),
            color=color,
            anchor=anchor,
        )


def _draw_entry(
    im: Image.Image,
    drawer: Drawer,
    total: SubstatTotal,
    icon: Image.Image,
    style: BreakdownStyle,
    *,
    x: int,
    center_y: int,
    label_width: int,
) -> None:
    _draw_label(drawer, total, style, x=x, center_y=center_y, width=label_width)
    x += label_width + style.gap
    im.alpha_composite(icon, (x, center_y - icon.height // 2))
    x += icon.width + style.gap
    drawer.write(
        total.formatted_value,
        size=style.value_size,
        style=style.value_style,
        position=(x, center_y),
        color=style.value_color,
        anchor="lm",
    )


def draw_breakdown_row(
    im: Image.Image,
    drawer: Drawer,
    totals: Sequence[SubstatTotal],
    icons: Sequence[Image.Image],
    style: BreakdownStyle,
    *,
    box: Box,
) -> None:
    """Draw the substat totals in a row, spaced evenly in the box, shrunk when they don't fit."""
    box_width = box[2] - box[0]
    min_space = style.gap * 2 * (len(totals) + 1)
    label_widths = [_label_width(drawer, total, style) for total in totals]
    widths = [
        _entry_width(drawer, total, style, label_width=w)
        for total, w in zip(totals, label_widths, strict=True)
    ]
    if totals and sum(widths) + min_space > box_width:
        factor = (box_width - min_space) / sum(widths)
        style = _scale_style(style, factor)
        icons = [
            icon.resize((round(icon.width * factor), round(icon.height * factor))) for icon in icons
        ]
        label_widths = [_label_width(drawer, total, style) for total in totals]
        widths = [
            _entry_width(drawer, total, style, label_width=w)
            for total, w in zip(totals, label_widths, strict=True)
        ]

    space = max(0, (box_width - sum(widths)) / (len(totals) + 1))
    center_y = (box[1] + box[3]) // 2
    x = box[0] + space
    for total, icon, width, label_width in zip(totals, icons, widths, label_widths, strict=True):
        _draw_entry(
            im, drawer, total, icon, style, x=round(x), center_y=center_y, label_width=label_width
        )
        x += width + space


def draw_breakdown_grid(
    im: Image.Image,
    drawer: Drawer,
    totals: Sequence[SubstatTotal],
    icons: Sequence[Image.Image],
    style: BreakdownStyle,
    *,
    box: Box,
    columns: int,
) -> None:
    """Draw the substat totals in a grid filling the box, left-aligned in their cells."""
    if not totals:
        return
    rows = math.ceil(len(totals) / columns)
    cell_width = (box[2] - box[0]) / columns
    cell_height = (box[3] - box[1]) / rows
    for index, (total, icon) in enumerate(zip(totals, icons, strict=True)):
        row, column = divmod(index, columns)
        x = round(box[0] + cell_width * column)
        center_y = round(box[1] + cell_height * (row + 0.5))
        label_width = _label_width(drawer, total, style)
        _draw_entry(im, drawer, total, icon, style, x=x, center_y=center_y, label_width=label_width)
