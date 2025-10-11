from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.constants import HSR_DEFAULT_ART_URL
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import io

    from genshin.models import AnomalyRecord

    from hoyo_buddy.enums import Locale


class AnomalyArbitrationCard:
    def __init__(
        self,
        data: AnomalyRecord,
        locale: Locale,
        char_names: dict[int, str],
        uid: int | None = None,
    ) -> None:
        self._record = data
        self._locale = locale
        self._char_names = char_names
        self._uid = uid

    def _write_titles(self, drawer: Drawer) -> None:
        tbox = drawer.write(
            LocaleStr(key="anomaly_arbitration_title"),
            size=110,
            position=(55, 39),
            style="bold",
            locale=self._locale,
            upper=True,
            max_width=793,
            max_lines=2,
        )

        season = self._record.season
        tbox = drawer.write(
            season.name,
            size=60,
            position=(tbox.left, tbox.bottom + 21),
            style="medium",
            locale=self._locale,
        )
        tbox = drawer.write(
            f"{season.begin_time.datetime:%Y/%m/%d} - {season.end_time.datetime:%Y/%m/%d}",
            size=38,
            position=(tbox.left, tbox.bottom + 33),
        )

        if self._uid is not None:
            drawer.write(f"UID: {self._uid}", size=38, position=(tbox.left, tbox.bottom + 19))

    def _write_stars(self, drawer: Drawer, im: Image.Image) -> None:
        boss_star = drawer.open_asset("boss_star.png", size=(70, 70))
        star_pos = (55, 750)
        im.alpha_composite(boss_star, star_pos)
        tbox = drawer.write(
            str(self._record.boss_stars),
            size=70,
            position=(star_pos[0] + 85 + 41 / 2, star_pos[1] + 70 / 2),
            anchor="mm",
            style="medium",
        )

        star = drawer.open_asset("star.png", size=(70, 70))
        star_pos = (tbox.right + 25, 750)
        im.alpha_composite(star, star_pos)
        drawer.write(
            str(self._record.mini_boss_stars),
            size=70,
            position=(star_pos[0] + 85 + 41 / 2, star_pos[1] + 70 / 2),
            anchor="mm",
            style="medium",
        )

    def _draw_boss(self, drawer: Drawer, im: Image.Image) -> None:
        boss = drawer.open_static(self._record.boss.icon, size=(580, 726))
        mask_shadow = drawer.open_asset("mask_shadow.png")
        gradient_mask = drawer.open_asset("gradient_mask.png")

        boss_im = Image.new("RGBA", boss.size)
        boss_im.alpha_composite(boss, (0, 0))
        boss_im.alpha_composite(gradient_mask, (0, 0))
        boss_im = drawer.top_crop(boss_im, 371)

        im.alpha_composite(mask_shadow, (902, 80))
        im.alpha_composite(boss_im, (902, 80))

    def _write_boss_texts(self, drawer: Drawer, im: Image.Image) -> None:
        # Name
        text_pos = (928, 133.5)
        tbox = drawer.write(
            self._record.boss.game_mode_name,
            size=52,
            anchor="lm",
            position=text_pos,
            style="bold",
            max_width=538,
            locale=self._locale,
        )

        record = self._record.boss_record
        if record is None or not record.has_data:
            return

        # Cleared
        pos = tbox.bottom + 14
        checkmark = drawer.open_asset("checkmark.png")
        im.alpha_composite(checkmark, (tbox.left, pos))
        tbox = drawer.write(
            LocaleStr(key="cleared"),
            size=36,
            anchor="lm",
            position=(tbox.left + checkmark.width + 5, pos + checkmark.height / 2),
            locale=self._locale,
        )

        boss_star = drawer.open_asset("boss_star.png", size=(51, 51))
        star_pos = (928, tbox.bottom + 30)
        star_padding = 19

        # Stars
        for _ in range(record.stars):
            im.alpha_composite(boss_star, star_pos)
            star_pos = (star_pos[0] + boss_star.width + star_padding, star_pos[1])

        # Cycles used
        pos = (928, star_pos[1] + boss_star.height + 35)
        tbox = drawer.write(
            LocaleStr(key="moc_card_cycles_used", cycles=record.cycles_used),
            size=30,
            anchor="lm",
            position=pos,
            locale=self._locale,
        )

        # Buff name and icon
        buff_icon = drawer.open_static(record.buff.icon, size=(64, 64))
        im.alpha_composite(buff_icon, (917, 379))
        drawer.write(
            record.buff.name,
            size=20,
            anchor="lm",
            position=(917 + buff_icon.width + 10, 379 + buff_icon.height / 2),
            max_lines=2,
            max_width=459,
            locale=self._locale,
        )

    def _draw_boss_record(self, drawer: Drawer, im: Image.Image) -> None:
        record = self._record.boss_record
        if record is None or not record.has_data:
            return

        pos = (1506, 125)
        padding = 44

        level_flair = drawer.open_asset("boss_char_level_flair.png")
        rank_flair = drawer.open_asset("boss_char_rank_flair.png")
        shadow = drawer.open_asset("boss_char_bg_shadow.png")
        mask = drawer.open_asset("boss_char_mask.png")

        for char in record.characters:
            name = self._char_names.get(char.id, "")

            char_im = drawer.open_asset("boss_char_bg.png")

            # Character image
            char_image = drawer.open_static(HSR_DEFAULT_ART_URL.format(char_id=char.id))
            char_image = drawer.resize_crop(char_image, (162, 326))
            char_image = drawer.mask_image_with_image(char_image, mask)
            char_im.alpha_composite(char_image, (0, 0))

            # Name (rotated)
            tbox = drawer.write(
                name, size=105, style="bold", position=(0, 0), no_write=True, anchor="lt"
            )
            text_im = Image.new("RGBA", tbox.size)
            text_im_drawer = Drawer(
                ImageDraw.Draw(text_im), folder="anomaly-arbitration", dark_mode=True, sans=True
            )
            text_im_drawer.write(
                name,
                size=105,
                style="bold",
                position=(0, 0),
                anchor="lt",
                color=(240, 240, 240),
                emphasis="medium",
            )

            text_im = text_im.rotate(90, expand=True)
            char_im.alpha_composite(text_im, (90, char_im.height - text_im.height))
            char_im = drawer.mask_image_with_image(char_im, mask)

            # Level and Rank flairs
            char_im.alpha_composite(level_flair, (0, 297))
            char_im_drawer = Drawer(
                ImageDraw.Draw(char_im), folder="anomaly-arbitration", dark_mode=True
            )
            char_im_drawer.write(
                f"Lv.{char.level}",
                size=24,
                position=(level_flair.width / 2, 297 + level_flair.height / 2),
                anchor="mm",
                style="bold",
                color=(240, 240, 240),
            )

            char_im.alpha_composite(rank_flair, (char_im.width - rank_flair.width, 0))
            char_im_drawer.write(
                str(char.rank),
                size=24,
                position=(char_im.width - rank_flair.width / 2, rank_flair.height / 2),
                anchor="mm",
                style="bold",
                color=(240, 240, 240),
            )

            im.alpha_composite(shadow, pos)
            im.alpha_composite(char_im, pos)

            pos = (pos[0] + char_im.width + padding, pos[1])

    def _draw_mini_boss_records(self, drawer: Drawer, im: Image.Image) -> None:
        pos = (902, 535)
        padding = 48
        width = 452
        checkmark = drawer.open_asset("small_checkmark.png")
        star = drawer.open_asset("star.png", size=(40, 40))

        mini_boss_map = {mb.id: mb for mb in self._record.mini_bosses}

        for record in self._record.mini_boss_records:
            mini_boss = mini_boss_map.get(record.id)
            if mini_boss is None:
                continue

            # Name
            text = mini_boss.level_name
            tbox = drawer.write(
                text,
                size=44,
                position=pos,
                anchor="lm",
                style="bold",
                max_width=449,
                locale=self._locale,
            )

            # Cleared
            if record.has_data:
                checkmark_pos = (pos[0], tbox.bottom + 13)
                im.alpha_composite(checkmark, checkmark_pos)
                drawer.write(
                    LocaleStr(key="cleared"),
                    size=32,
                    position=(
                        checkmark_pos[0] + checkmark.width + 5,
                        checkmark_pos[1] + checkmark.height / 2,
                    ),
                    anchor="lm",
                    style="bold",
                    locale=self._locale,
                )

            # Stars
            star_pos = (pos[0], pos[1] + 101)
            for _ in range(record.stars):
                im.alpha_composite(star, (star_pos[0], star_pos[1]))
                star_pos = (star_pos[0] + star.width + 10, star_pos[1])

            # Cycles used
            drawer.write(
                LocaleStr(key="moc_card_cycles_used", cycles=record.cycles_used),
                size=24,
                position=(pos[0] + width, pos[1] + 123),
                anchor="rm",
                locale=self._locale,
            )

            # Characters
            char_pos = (pos[0], pos[1] + 180)
            char_padding = 12

            level_flair = drawer.open_asset("normal_char_level_flair.png")
            rank_flair = drawer.open_asset("normal_char_rank_flair.png")
            mask = drawer.open_asset("normal_char_mask.png")
            empty = drawer.open_asset("empty.png")
            shadow = drawer.open_asset("normal_char_bg_shadow.png")

            for index in range(4):
                try:
                    char = record.characters[index]
                except IndexError:
                    char = None

                char_bg = drawer.open_asset("normal_char_bg.png")
                char_bg_drawer = Drawer(
                    ImageDraw.Draw(char_bg), folder="anomaly-arbitration", dark_mode=True
                )

                if char is None:
                    char_bg.alpha_composite(empty, (28, 28))
                else:
                    icon = drawer.open_static(char.icon)
                    icon = drawer.resize_crop(icon, (104, 104))
                    icon = drawer.mask_image_with_image(icon, mask)
                    char_bg.alpha_composite(icon, (0, 0))

                    char_bg.alpha_composite(level_flair, (0, 83))
                    char_bg_drawer.write(
                        f"Lv.{char.level}",
                        size=16,
                        position=(level_flair.width / 2, 83 + level_flair.height / 2),
                        anchor="mm",
                        style="bold",
                        color=(240, 240, 240),
                    )

                    char_bg.alpha_composite(rank_flair, (80, 0))
                    char_bg_drawer.write(
                        str(char.rank),
                        size=16,
                        position=(char_bg.width - rank_flair.width / 2, rank_flair.height / 2),
                        anchor="mm",
                        style="bold",
                        color=(240, 240, 240),
                    )

                im.alpha_composite(shadow, char_pos)
                im.alpha_composite(char_bg, char_pos)

                char_pos = (char_pos[0] + char_bg.width + char_padding, char_pos[1])

            pos = (pos[0] + width + padding, pos[1])

    def draw(self) -> io.BytesIO:
        im = Drawer.open_image("hoyo-buddy-assets/assets/anomaly-arbitration/bg.png")
        drawer = Drawer(ImageDraw.Draw(im), folder="anomaly-arbitration", dark_mode=True, sans=True)

        self._write_titles(drawer)
        self._write_stars(drawer, im)
        self._draw_boss(drawer, im)
        self._write_boss_texts(drawer, im)
        self._draw_boss_record(drawer, im)
        self._draw_mini_boss_records(drawer, im)

        return Drawer.save_image(im)
