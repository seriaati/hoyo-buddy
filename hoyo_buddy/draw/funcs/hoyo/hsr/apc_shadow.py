from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import TRANSPARENT, WHITE, Drawer
from hoyo_buddy.enums import ChallengeType
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.utils import get_floor_difficulty

if TYPE_CHECKING:
    from genshin.models.starrail import (
        APCShadowFloor,
        FloorCharacter,
        StarRailAPCShadow,
        StarRailChallengeSeason,
    )


class APCShadowCard:
    def __init__(
        self, data: StarRailAPCShadow, season: StarRailChallengeSeason, locale: str
    ) -> None:
        self._data = data
        self._season = season

        self._locale = locale

    @property
    def locale(self) -> Locale:
        return Locale(self._locale)

    def _write_title(self) -> None:
        self._drawer.write(
            EnumStr(ChallengeType.APC_SHADOW), size=80, position=(76, 75), style="bold"
        )

    def _write_apc_shadow_name(self) -> None:
        self._drawer.write(self._season.name, size=64, position=(76, 197), style="medium")

    def _write_max_stars(self) -> None:
        self._drawer.write(
            str(self._data.total_stars), size=50, position=(193, 374), style="medium", anchor="mm"
        )

    def _write_farthest_stage(self) -> None:
        self._drawer.write(
            LocaleStr(
                key="apc_shadow.highest_diff_cleared",
                diff=get_floor_difficulty(self._data.max_floor, self._season.name),
            ),
            size=25,
            position=(303, 340),
        )

    def _write_times_challenged(self) -> None:
        self._drawer.write(
            LocaleStr(key="apc_shadow.times_challenged", times=self._data.total_battles),
            size=25,
            position=(303, 374),
        )

    def _draw_block(self, chara: FloorCharacter | None = None) -> Image.Image:
        block = Drawer.open_image("hoyo-buddy-assets/assets/apc-shadow/block.png")
        if chara is None:
            empty = Drawer.open_image("hoyo-buddy-assets/assets/apc-shadow/empty.png")
            block.paste(empty, (28, 28), empty)
            return block

        drawer = Drawer(
            ImageDraw.Draw(block), folder="apc-shadow", dark_mode=True, locale=self.locale
        )

        icon = drawer.open_static(chara.icon)
        icon = drawer.resize_crop(icon, (120, 120))
        mask = drawer.open_asset("mask.png")
        icon = drawer.mask_image_with_image(icon, mask)
        block.paste(icon, (0, 0), icon)

        level_flair = drawer.open_asset("level_flair.png")
        level_flair_pos = (0, 97)
        block.paste(level_flair, level_flair_pos, level_flair)
        drawer.write(
            str(chara.level),
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

    def _draw_stage(self, stage: APCShadowFloor) -> Image.Image:
        im = Image.new("RGBA", (639, 421), TRANSPARENT)
        drawer = Drawer(ImageDraw.Draw(im), folder="apc-shadow", dark_mode=True, locale=self.locale)

        stage_name = get_floor_difficulty(stage.name, self._season.name)
        name_tbox = drawer.write(stage_name, size=44, position=(0, 0), style="bold", color=WHITE)
        score_tbox = drawer.write(
            LocaleStr(
                key="pf_card_total_score",
                score=f"{stage.node_1.score}+{stage.node_2.score}={stage.score}"
                if not stage.is_quick_clear
                else 8000,
            ),
            size=25,
            position=(0, 60),
            color=WHITE,
            style="medium",
        )

        rightmost = max(name_tbox[2], score_tbox[2])
        line = drawer.open_asset("line.png")
        padding = 26
        im.paste(line, (rightmost + padding, 10))

        star = drawer.open_asset("star.png")
        pos = (rightmost + padding + 37, 0)
        for _ in range(stage.star_num):
            im.paste(star, pos)
            pos = (pos[0] + 62, pos[1])

        defeated_text = LocaleStr(key="apc_shadow.boss_defeated").translate(self.locale)
        not_defeated_text = LocaleStr(key="apc_shadow.boss_defeated_no").translate(self.locale)
        quick_clear_text = LocaleStr(key="moc_quick_clear").translate(self.locale)

        if stage.is_quick_clear:
            text = quick_clear_text
        elif stage.node_1.boss_defeated and stage.node_2.boss_defeated:
            text = defeated_text
        elif not stage.node_1.boss_defeated and not stage.node_2.boss_defeated:
            text = not_defeated_text
        else:
            text = f"{defeated_text} / {not_defeated_text}"

        drawer.write(text, size=25, position=(rightmost + padding + 37, 60), color=WHITE)

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
        self._im = Drawer.open_image("hoyo-buddy-assets/assets/apc-shadow/apc_shadow.png")
        self._drawer = Drawer(
            ImageDraw.Draw(self._im), folder="apc-shadow", locale=self.locale, dark_mode=True
        )

        self._write_title()
        self._write_apc_shadow_name()
        self._write_max_stars()
        self._write_farthest_stage()
        self._write_times_challenged()

        self._data.floors.reverse()
        pos = (83, 482)
        for i, stage in enumerate(self._data.floors):
            stage_im = self._draw_stage(stage)
            self._im.paste(stage_im, pos, stage_im)
            pos = (pos[0] + 779, pos[1])

            if i == 1:
                pos = (83, 980)

        buffer = BytesIO()
        self._im.save(buffer, format="PNG")
        return buffer
