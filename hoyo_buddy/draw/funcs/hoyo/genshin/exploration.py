from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LevelStr, LocaleStr

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from io import BytesIO

    from genshin.models import Exploration, PartialGenshinUserStats, Stats

FOLDER = "gi-exploration"
PLACEHOLDER = "? ? ?"

CANVAS_WIDTH = 1667
COLUMN_X = (114, 868)
TITLE_POS = (114, 81)
SUMMARY_Y = 249
SUMMARY_HEIGHT = 235
SUMMARY_GAP = 63
ROW_GAP = 31
BOTTOM_MARGIN = 77

BLOCK_WIDTH = 688
CORNER_RADIUS = 15
ART_OPACITY = 0.7
BLOCK_TITLE_POS = (34, 23)
ICON_CENTER_X = 52
TEXT_X = 75

# (blur, x offset, y offset, alpha) of each drop shadow layer in Figma
SHADOW_LAYERS = ((11, 4, 3, 0.10), (20, 15, 13, 0.09), (27, 33, 30, 0.05), (32, 59, 54, 0.01))
SHADOW_OPACITY = 0.3
SHADOW_PAD = 110


@dataclass(frozen=True, slots=True)
class BlockSize:
    height: int
    first_line_y: int
    line_gap: int


REGULAR = BlockSize(287, first_line_y=117, line_gap=46)
TALL = BlockSize(320, first_line_y=134, line_gap=45)
SHORT = BlockSize(245, first_line_y=120, line_gap=64)


@dataclass(frozen=True, slots=True)
class StatLine:
    icon: str
    """Filename in the icons folder, without the _light/_dark suffix."""
    text: Callable[[ExplorationCard, Exploration | None], LocaleStr | str]


@dataclass(frozen=True, slots=True, kw_only=True)
class RegionBlock:
    art: str
    """Filename in the art folder, without the extension."""
    exploration_id: int
    lines: Sequence[StatLine]
    size: BlockSize = REGULAR
    fade_start: float = 0.08
    """Where the fade starts fading out, as a fraction of the block width."""


def oculus(icon: str, key: str, count: Callable[[Stats], int]) -> StatLine:
    return StatLine(
        icon,
        lambda card, _: LocaleStr(
            key=key, mi18n_game=Game.GENSHIN, append=f": {count(card.user.stats)}"
        ),
    )


def offering(icon: str) -> StatLine:
    return StatLine(icon, lambda card, exploration: card.offering_text(exploration))


def sub_area(exploration_id: int) -> StatLine:
    return StatLine("pin", lambda card, _: card.sub_area_text(exploration_id))


PROGRESS = StatLine(
    "pin",
    lambda _, e: LocaleStr(key="exploration.progress", progress=0 if e is None else e.explored),
)
REPUTATION = StatLine(
    "reputation",
    lambda _, e: LocaleStr(
        key="reputation_level", mi18n_game=Game.GENSHIN, append=str(0 if e is None else e.level)
    ),
)
NATLAN_REPUTATION = StatLine(
    "reputation",
    lambda _, e: LocaleStr(
        key="natlan_reputation",
        reputation=0 if e is None else e.level,
        tribes=ExplorationCard.tribe_levels(e),
    ),
)

# Blocks are laid out in this order, two per row
REGIONS: tuple[RegionBlock, ...] = (
    RegionBlock(
        art="mondstadt",
        exploration_id=1,
        lines=(PROGRESS, oculus("anemoculus", "wind_god", lambda s: s.anemoculi), REPUTATION),
    ),
    RegionBlock(
        art="liyue",
        exploration_id=2,
        lines=(PROGRESS, oculus("geoculus", "geoculus", lambda s: s.geoculi), REPUTATION),
        fade_start=0.13,
    ),
    RegionBlock(
        art="inazuma",
        exploration_id=4,
        lines=(
            PROGRESS,
            oculus("electroculus", "electroculus", lambda s: s.electroculi),
            REPUTATION,
            offering("offering_inazuma"),
        ),
        fade_start=0.07,
    ),
    RegionBlock(
        art="sumeru",
        exploration_id=8,
        lines=(
            PROGRESS,
            oculus("dendroculus", "dendro_culus", lambda s: s.dendroculi),
            REPUTATION,
            offering("offering_sumeru"),
        ),
        fade_start=0.01,
    ),
    RegionBlock(
        art="fontaine",
        exploration_id=9,
        lines=(
            PROGRESS,
            oculus("hydroculus", "hydro_god", lambda s: s.hydroculi),
            REPUTATION,
            offering("offering_fontaine"),
        ),
    ),
    RegionBlock(
        art="natlan",
        exploration_id=15,
        lines=(
            PROGRESS,
            oculus("pyroculus", "pyroculus_number", lambda s: s.pyroculi),
            NATLAN_REPUTATION,
            offering("offering_natlan"),
        ),
    ),
    RegionBlock(art="ancientSacredMountain", exploration_id=16, lines=(PROGRESS,), fade_start=0.02),
    RegionBlock(art="seaOfBygoneEras", exploration_id=14, lines=(PROGRESS,), fade_start=0.01),
    RegionBlock(
        art="chenyuVale",
        exploration_id=10,
        lines=(sub_area(13), sub_area(12), sub_area(11), offering("offering_chenyu")),
        size=TALL,
        fade_start=0.21,
    ),
    RegionBlock(
        art="theChasm",
        exploration_id=6,
        lines=(PROGRESS, sub_area(7), offering("offering_chasm")),
        size=TALL,
        fade_start=0.14,
    ),
    RegionBlock(
        art="dragonspine",
        exploration_id=3,
        lines=(PROGRESS, offering("offering_dragonspine")),
        size=SHORT,
        fade_start=0.21,
    ),
    RegionBlock(art="enkanomiya", exploration_id=5, lines=(PROGRESS,), size=SHORT, fade_start=0.04),
)


@functools.cache
def get_shadow(width: int, height: int) -> Image.Image:
    size = (width + SHADOW_PAD * 2, height + SHADOW_PAD * 2)
    shape = Image.new("L", size, 0)
    ImageDraw.Draw(shape).rounded_rectangle(
        (SHADOW_PAD, SHADOW_PAD, SHADOW_PAD + width - 1, SHADOW_PAD + height - 1),
        CORNER_RADIUS,
        fill=255,
    )

    coverage = np.zeros((size[1], size[0]))
    for blur, dx, dy, alpha in SHADOW_LAYERS:
        layer = shape.transform(size, Image.Transform.AFFINE, (1, 0, -dx, 0, 1, -dy)).filter(
            ImageFilter.GaussianBlur(blur / 2)
        )
        coverage += np.asarray(layer) / 255 * alpha * (1 - coverage)

    shadow = Image.new("RGBA", size, (0, 0, 0, 0))
    shadow.putalpha(Image.fromarray((coverage * SHADOW_OPACITY * 255).round().astype(np.uint8)))
    return shadow


class ExplorationCard:
    def __init__(self, user: PartialGenshinUserStats, dark_mode: bool, locale: str) -> None:
        self.user = user
        self._dark_mode = dark_mode
        self._locale = locale

    @property
    def locale(self) -> Locale:
        return Locale(self._locale)

    @property
    def _theme(self) -> str:
        return "dark" if self._dark_mode else "light"

    @staticmethod
    def tribe_levels(exploration: Exploration | None) -> str:
        if exploration is None or exploration.natlan_reputation is None:
            return "0"
        return "/".join(str(t.level) for t in exploration.natlan_reputation.tribes)

    def get_exploration(self, exploration_id: int) -> Exploration | None:
        return next((e for e in self.user.explorations if e.id == exploration_id), None)

    def offering_text(self, exploration: Exploration | None) -> str:
        if exploration is None or not exploration.offerings:
            offering_name = PLACEHOLDER
            level = 0
        else:
            offering = exploration.offerings[0]
            offering_name = offering.name
            level = offering.level

        level_str = LevelStr(level).translate(self.locale)
        return f"{offering_name}: {level_str}"

    def sub_area_text(self, exploration_id: int) -> str:
        area = self.get_exploration(exploration_id)
        if area is None:
            return f"{PLACEHOLDER}: 0%"
        return f"{area.name}: {area.explored}%"

    def _new_drawer(self, im: Image.Image) -> Drawer:
        return Drawer(
            ImageDraw.Draw(im), folder=FOLDER, dark_mode=self._dark_mode, locale=self.locale
        )

    def _write_title(
        self, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(text, position=position, size=48, style="medium")

    def _write_small_text(
        self, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(text, position=position, size=26, style="regular", anchor="lm")

    def _draw_waypoint_card(self) -> Image.Image:
        im = self._drawer.open_asset(f"waypoint_{self._theme}.png")
        drawer = self._new_drawer(im)
        self._write_title(LocaleStr(key="exploration.waypoints"), position=(35, 20), drawer=drawer)

        texts: dict[str, tuple[int, int]] = {
            str(self.user.stats.unlocked_waypoints): (75, 193),
            str(self.user.stats.unlocked_domains): (200, 193),
        }
        for text, pos in texts.items():
            drawer.write(
                text,
                position=pos,
                size=24,
                style="regular",
                anchor="mm",
                locale=Locale.american_english,
            )

        return im

    def _draw_chest_card(self) -> Image.Image:
        im = self._drawer.open_asset(f"chest_{self._theme}.png")
        drawer = self._new_drawer(im)
        self._write_title(LocaleStr(key="exploration.chests"), position=(21, 20), drawer=drawer)

        chest_types: dict[LocaleStr, tuple[int, int]] = {
            LocaleStr(key="exploration.common_chests"): (78, 167),
            LocaleStr(key="exploration.exquisite_chests"): (210, 167),
            LocaleStr(key="exploration.precious_chests"): (343, 167),
            LocaleStr(key="exploration.luxurious_chests"): (476, 167),
            LocaleStr(key="exploration.remarkable_chests"): (611, 167),
        }
        chest_nums: dict[int, tuple[int, int]] = {
            self.user.stats.common_chests: (79, 196),
            self.user.stats.exquisite_chests: (210, 196),
            self.user.stats.precious_chests: (343, 196),
            self.user.stats.luxurious_chests: (476, 196),
            self.user.stats.remarkable_chests: (610, 196),
        }
        for text, pos in chest_types.items():
            drawer.write(
                text,
                position=pos,
                size=18,
                style="light",
                anchor="mm",
                locale=Locale.american_english,
            )
        for text, pos in chest_nums.items():
            drawer.write(
                str(text),
                position=pos,
                size=24,
                style="regular",
                anchor="mm",
                locale=Locale.american_english,
            )

        return im

    def _draw_region_background(self, block: RegionBlock) -> Image.Image:
        size = (BLOCK_WIDTH, block.size.height)
        art = Drawer.resize_crop(self._drawer.open_asset(f"art/{block.art}.png"), size)
        art_alpha = np.asarray(art.getchannel("A")) * ART_OPACITY
        art.putalpha(Image.fromarray(art_alpha.round().astype(np.uint8)))

        color, start_alpha = ((42, 42, 42), 0.7) if self._dark_mode else ((255, 255, 255), 0.9)
        progress = np.clip(
            (np.arange(size[0]) / size[0] - block.fade_start) / (1 - block.fade_start), 0, 1
        )
        alpha = (start_alpha * (1 - progress) * 255).round().astype(np.uint8)
        fade = Image.new("RGBA", size, color)
        fade.putalpha(Image.fromarray(np.tile(alpha, (size[1], 1))))

        return Image.alpha_composite(art, fade)

    def _draw_region(self, block: RegionBlock) -> Image.Image:
        im = self._draw_region_background(block)
        drawer = self._new_drawer(im)
        exploration = self.get_exploration(block.exploration_id)

        self._write_title(
            PLACEHOLDER if exploration is None else exploration.name,
            position=BLOCK_TITLE_POS,
            drawer=drawer,
        )
        for i, line in enumerate(block.lines):
            y = block.size.first_line_y + i * block.size.line_gap
            icon = drawer.open_asset(f"icons/{line.icon}_{self._theme}.png")
            im.alpha_composite(icon, (ICON_CENTER_X - icon.width // 2, y - icon.height // 2))
            self._write_small_text(
                line.text(self, exploration), position=(TEXT_X, y), drawer=drawer
            )

        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            (0, 0, im.width - 1, im.height - 1), CORNER_RADIUS, fill=255
        )
        im.putalpha(ImageChops.multiply(im.getchannel("A"), mask))
        return im

    def _paste_block(self, block: Image.Image, position: tuple[int, int]) -> None:
        x, y = position
        self._im.alpha_composite(get_shadow(*block.size), (x - SHADOW_PAD, y - SHADOW_PAD))
        self._im.alpha_composite(block, position)

    def draw(self) -> BytesIO:
        rows = [REGIONS[i : i + 2] for i in range(0, len(REGIONS), 2)]
        row_heights = [max(block.size.height for block in row) for row in rows]
        regions_y = SUMMARY_Y + SUMMARY_HEIGHT + SUMMARY_GAP
        height = regions_y + sum(row_heights) + ROW_GAP * (len(rows) - 1) + BOTTOM_MARGIN

        bg_color = (37, 37, 37) if self._dark_mode else (245, 245, 245)
        self._im = Image.new("RGBA", (CANVAS_WIDTH, height), bg_color)
        self._drawer = self._new_drawer(self._im)
        self._drawer.write(
            LocaleStr(key="exploration.title"), position=TITLE_POS, size=72, style="bold"
        )

        self._paste_block(self._draw_waypoint_card(), (COLUMN_X[0], SUMMARY_Y))
        self._paste_block(self._draw_chest_card(), (COLUMN_X[1], SUMMARY_Y))

        y = regions_y
        for row, row_height in zip(rows, row_heights, strict=True):
            for block, x in zip(row, COLUMN_X, strict=False):
                self._paste_block(self._draw_region(block), (x, y))
            y += row_height + ROW_GAP

        return Drawer.save_image(self._im)
