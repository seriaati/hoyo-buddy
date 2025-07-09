from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import TRANSPARENT, WHITE, Drawer
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import get_floor_difficulty

if TYPE_CHECKING:
    from io import BytesIO

    from genshin.models.starrail import (
        FloorCharacter,
        StarRailChallenge,
        StarRailChallengeSeason,
        StarRailFloor,
    )

    from hoyo_buddy.enums import Locale


class MOCCard:
    def __init__(
        self,
        data: StarRailChallenge,
        season: StarRailChallengeSeason,
        locale: Locale,
        uid: int | None,
    ) -> None:
        self._data = data
        self._season = season
        self._locale = locale
        self._uid = uid

    def _write_uid(self) -> None:
        if self._uid is None:
            return

        self._drawer.write(
            f"UID: {self._uid}",
            size=18,
            position=(self._im.width - 29, 20),
            style="bold",
            color=WHITE,
            anchor="rt",
        )

    def _write_title(self) -> None:
        self._drawer.write(
            self._season.name,
            size=80,
            position=(76, 75),
            style="bold",
            color=WHITE,
            locale=self._locale,
        )

    def _write_season_time(self) -> None:
        text = f"{self._season.begin_time.datetime.strftime('%Y/%m/%d')} ~ {self._season.end_time.datetime.strftime('%Y/%m/%d')}"
        self._drawer.write(text, size=36, position=(76, 197), style="medium", color=WHITE)

    def _write_max_stars(self) -> None:
        self._drawer.write(
            str(self._data.total_stars),
            size=50,
            position=(193, 374),
            style="medium",
            anchor="mm",
            color=WHITE,
        )

    def _write_farthest_stage(self) -> None:
        self._drawer.write(
            LocaleStr(
                key="moc_card_farthest_stage",
                stage=get_floor_difficulty(self._data.max_floor, self._season.name),
            ),
            size=25,
            position=(303, 340),
            color=WHITE,
            locale=self._locale,
        )

    def _write_battles_fought(self) -> None:
        self._drawer.write(
            LocaleStr(key="moc_card_battles_fought", battles=self._data.total_battles),
            size=25,
            position=(303, 374),
            color=WHITE,
            locale=self._locale,
        )

    def _draw_block(self, chara: FloorCharacter | None = None) -> Image.Image:
        block = Drawer.open_image("hoyo-buddy-assets/assets/moc/block.png")
        if chara is None:
            empty = Drawer.open_image("hoyo-buddy-assets/assets/moc/empty.png")
            block.paste(empty, (28, 28), empty)
            return block

        drawer = Drawer(ImageDraw.Draw(block), folder="moc", dark_mode=True)

        icon = drawer.open_static(chara.icon)
        icon = drawer.resize_crop(icon, (120, 120))
        mask = drawer.open_asset("mask.png")
        icon = drawer.mask_image_with_image(icon, mask)
        block.paste(icon, (1, 1), icon)

        level_flair = drawer.open_asset("level_flair.png")
        level_flair_pos = (0, 97)
        block.paste(level_flair, level_flair_pos, level_flair)
        drawer.write(
            f"Lv.{chara.level}",
            size=18,
            position=(
                level_flair_pos[0] + level_flair.width // 2,
                level_flair_pos[1] + level_flair.height // 2,
            ),
            style="bold",
            anchor="mm",
            color=WHITE,
        )

        const_flair = drawer.open_asset("const_flair.png")
        const_flair_pos = (91, 0)
        block.paste(const_flair, const_flair_pos, const_flair)
        drawer.write(
            str(chara.rank),
            size=18,
            position=(
                const_flair_pos[0] + const_flair.width // 2,
                const_flair_pos[1] + const_flair.height // 2,
            ),
            style="bold",
            anchor="mm",
            color=WHITE,
        )

        return block

    def _draw_stage(self, stage: StarRailFloor) -> Image.Image:
        im = Image.new("RGBA", (639, 421), TRANSPARENT)
        drawer = Drawer(ImageDraw.Draw(im), folder="moc", dark_mode=True)

        stage_name = get_floor_difficulty(stage.name, self._season.name)
        name_tbox = drawer.write(
            stage_name, size=44, position=(0, 0), style="bold", color=WHITE, locale=self._locale
        )
        if stage.is_quick_clear:
            cycle_tbox = drawer.write(
                LocaleStr(key="moc_quick_clear"),
                size=25,
                position=(0, 60),
                color=WHITE,
                style="medium",
                locale=self._locale,
            )
        else:
            cycle_tbox = drawer.write(
                LocaleStr(key="moc_card_cycles_used", cycles=stage.round_num),
                size=25,
                position=(0, 60),
                color=WHITE,
                style="medium",
                locale=self._locale,
            )

        rightmost = max(name_tbox[2], cycle_tbox[2])
        line = drawer.open_asset("line.png")
        padding = 26
        im.paste(line, (rightmost + padding, 10))

        star = drawer.open_asset("star.png")
        pos = (rightmost + padding + 37, 21)
        for _ in range(stage.star_num):
            im.paste(star, pos)
            pos = (pos[0] + 82, pos[1])

        characters = stage.node_1.avatars + stage.node_2.avatars

        pos = (0, 135)
        for i in range(8):
            try:
                chara = characters[i]
            except IndexError:
                chara = None
            block = self._draw_block(chara)
            im.paste(block, pos, block)
            pos = (pos[0] + 172, pos[1])

            if i == 3:
                pos = (0, 301)

        return im

    def draw(self) -> BytesIO:
        floors = list(self._data.floors)
        floors.reverse()
        battled_floors = [f for f in floors if not f.is_quick_clear]

        is_square = False
        if len(battled_floors) == 4:
            filename = "moc_square.png"
            floors = battled_floors
            is_square = True
        elif len(battled_floors) <= 3:
            filename = "moc_short.png"
            floors = battled_floors
        else:
            filename = "moc.png"
            floors = floors[-6:]

        self._im = Drawer.open_image(f"hoyo-buddy-assets/assets/moc/{filename}")
        self._drawer = Drawer(ImageDraw.Draw(self._im), folder="moc", dark_mode=True)

        self._write_title()
        self._write_season_time()
        self._write_max_stars()
        self._write_farthest_stage()
        self._write_battles_fought()
        self._write_uid()

        pos = (83, 492)
        for i, stage in enumerate(floors):
            stage_im = self._draw_stage(stage)
            self._im.paste(stage_im, pos, stage_im)
            pos = (pos[0] + 779, pos[1])

            if i == (1 if is_square else 2):
                pos = (83, 990)

        return Drawer.save_image(self._im)
