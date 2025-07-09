from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import TRANSPARENT, WHITE, Drawer
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import get_floor_difficulty

if TYPE_CHECKING:
    from io import BytesIO

    from genshin.models.starrail import (
        FictionFloor,
        FloorCharacter,
        StarRailChallengeSeason,
        StarRailPureFiction,
    )

    from hoyo_buddy.enums import Locale


class PureFictionCard:
    def __init__(
        self, data: StarRailPureFiction, season: StarRailChallengeSeason, locale: Locale
    ) -> None:
        self._data = data
        self._season = season
        self._locale = locale

    def _write_title(self) -> None:
        self._drawer.write(
            self._season.name, size=80, position=(76, 75), style="bold", locale=self._locale
        )

    def _write_season_time(self) -> None:
        text = f"{self._season.begin_time.datetime.strftime('%Y/%m/%d')} ~ {self._season.end_time.datetime.strftime('%Y/%m/%d')}"
        self._drawer.write(text, size=36, position=(76, 197), style="medium")

    def _write_max_stars(self) -> None:
        self._drawer.write(
            str(self._data.total_stars), size=50, position=(193, 374), style="medium", anchor="mm"
        )

    def _write_farthest_stage(self) -> None:
        self._drawer.write(
            LocaleStr(
                key="moc_card_farthest_stage",
                stage=get_floor_difficulty(self._data.max_floor, self._season.name),
            ),
            size=25,
            position=(303, 340),
            locale=self._locale,
        )

    def _write_battles_fought(self) -> None:
        self._drawer.write(
            LocaleStr(key="moc_card_battles_fought", battles=self._data.total_battles),
            size=25,
            position=(303, 374),
            locale=self._locale,
        )

    def _draw_block(self, chara: FloorCharacter | None = None) -> Image.Image:
        block = Drawer.open_image("hoyo-buddy-assets/assets/pf/block.png")
        if chara is None:
            empty = Drawer.open_image("hoyo-buddy-assets/assets/pf/empty.png")
            block.paste(empty, (28, 28), empty)
            return block

        drawer = Drawer(ImageDraw.Draw(block), folder="pf", dark_mode=True)

        icon = drawer.open_static(chara.icon)
        icon = drawer.resize_crop(icon, (120, 120))
        mask = drawer.open_asset("mask.png")
        icon = drawer.mask_image_with_image(icon, mask)
        block.paste(icon, (2, 2), icon)

        level_flair = drawer.open_asset("level_flair.png")
        level_flair_pos = (2, 98)
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
        const_flair_pos = (92, 2)
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

    def _draw_stage(self, stage: FictionFloor) -> Image.Image:
        im = Image.new("RGBA", (639, 421), TRANSPARENT)
        drawer = Drawer(ImageDraw.Draw(im), folder="pf", dark_mode=True)

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
        pos = (rightmost + padding + 37, 14)
        for _ in range(stage.star_num):
            im.paste(star, pos)
            pos = (pos[0] + 62, pos[1])

        drawer.write(
            LocaleStr(
                key="pf_card_total_score",
                score=f"{stage.node_1.score}+{stage.node_2.score}={stage.score}"
                if not stage.is_quick_clear
                else 80000,
            ),
            size=25,
            position=(rightmost + padding + 37, 60),
            color=WHITE,
            locale=self._locale,
        )

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
        stages = [f for f in self._data.floors if not f.is_quick_clear]
        stages.reverse()

        filename = "pf_short.png" if len(stages) <= 2 else "pf.png"
        self._im = Drawer.open_image(f"hoyo-buddy-assets/assets/pf/{filename}")
        self._drawer = Drawer(ImageDraw.Draw(self._im), folder="pf", dark_mode=True)

        self._write_title()
        self._write_season_time()
        self._write_max_stars()
        self._write_farthest_stage()
        self._write_battles_fought()

        stages = [f for f in self._data.floors if not f.is_quick_clear]
        stages.reverse()

        pos = (83, 482)
        for i, stage in enumerate(stages):
            stage_im = self._draw_stage(stage)
            self._im.paste(stage_im, pos, stage_im)
            pos = (pos[0] + 779, pos[1])

            if i == 1:
                pos = (83, 980)

        return Drawer.save_image(self._im)
