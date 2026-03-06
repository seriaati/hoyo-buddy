from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import ImageDraw

from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils.misc import format_time

if TYPE_CHECKING:
    from io import BytesIO

    import genshin


class ShiyuV2Card:
    def __init__(
        self, data: genshin.models.ShiyuDefenseV2, *, uid: int | None, locale: str
    ) -> None:
        self.data = data
        self.locale = Locale(locale)
        self.uid = uid

    def write_uid(self) -> None:
        if self.uid is not None:
            self.drawer.write(
                f"UID: {self.uid}", size=32, position=(3449, 18), style="medium", anchor="rt"
            )

    def write_stats(self) -> None:
        self.drawer.write(
            LocaleStr(key="shiyu_overview"),
            size=70,
            position=(110, 658),
            style="bold",
            locale=self.locale,
        )

        s_count = 0
        a_count = 0
        b_count = 0

        if self.data.fourth_frontier is not None:
            s_count += 1 if self.data.fourth_frontier.rating == "S" else 0
            a_count += 1 if self.data.fourth_frontier.rating == "A" else 0
            b_count += 1 if self.data.fourth_frontier.rating == "B" else 0
        if self.data.fifth_frontier is not None:
            s_count += sum([1 for l in self.data.fifth_frontier.layers if l.rating == "S"])
            a_count += sum([1 for l in self.data.fifth_frontier.layers if l.rating == "A"])
            b_count += sum([1 for l in self.data.fifth_frontier.layers if l.rating == "B"])

        positions = {(186, 794): s_count, (416, 794): a_count, (641, 794): b_count}
        for pos, count in positions.items():
            self.drawer.write(
                f"x {count}", size=58, position=pos, style="bold_italic", locale=self.locale
            )

        if (info := self.data.brief_info) is not None:
            total_clear_time = info.total_clear_time
            score = info.score
            rank_percent = info.rank_percent
        else:
            total_clear_time = 0
            score = 0
            rank_percent = "0.00%"

        tbox = self.drawer.write(
            LocaleStr(key="shiyu_total_clear_time"),
            size=44,
            position=(110, 905),
            style="medium",
            locale=self.locale,
        )
        self.drawer.write(
            format_time(total_clear_time),
            size=55,
            position=(110, 905 + tbox.height + 25),
            style="bold",
        )

        self.drawer.write(
            rank_percent, size=48, position=(213.5, 1138.5), style="bold_italic", anchor="mm"
        )
        self.drawer.write(f"{score}", size=160, position=(143, 1147), style="black_italic")

    def draw_fifth_frontier(self) -> None:
        if self.data.fifth_frontier is None:
            return

        frontier = self.data.fifth_frontier
        tbox = self.drawer.write(
            LocaleStr(key="shiyu_5_frontier"),
            size=90,
            position=(1273, 525),
            style="bold",
            locale=self.locale,
        )

        if self.data.brief_info is not None and self.data.brief_info.rating is not None:
            long_line = self.drawer.open_asset("long_line.png")
            self.im.alpha_composite(
                long_line, (tbox.right + 40, tbox.top + tbox.height // 2 - long_line.height // 2)
            )
            self.drawer.write(
                self.data.brief_info.rating,
                size=110,
                position=(tbox.right + 40 + long_line.width + 30, tbox.top + tbox.height // 2),
                style="black_italic",
                anchor="lm",
            )

        start_pos = (1279, 680)

        short_line = self.drawer.open_asset("short_line.png")
        boss_mask = self.drawer.open_asset("boss_mask.png")
        char_mask = self.drawer.open_asset("5_char_mask.png")
        char_level_flair = self.drawer.open_asset("5_char_level_flair.png")
        char_rank_flair = self.drawer.open_asset("5_char_rank_flair.png")
        bangboo_mask = self.drawer.open_asset("5_bangboo_mask.png")
        bangboo_level_flair = self.drawer.open_asset("5_bangboo_level_flair.png")

        for layer in frontier.layers:
            self.drawer.write(f"{layer.score}", size=75, style="bold_italic", position=start_pos)

            clear_time_pos = (start_pos[0] + 479, start_pos[1] + 10)
            title_tbox = self.drawer.write(
                LocaleStr(key="shiyu_clear_time"),
                size=28,
                style="bold",
                position=clear_time_pos,
                locale=self.locale,
                anchor="rt",
            )
            value_tbox = self.drawer.write(
                format_time(layer.clear_time),
                size=40,
                position=(clear_time_pos[0], clear_time_pos[1] + title_tbox.height + 15),
                style="bold",
                anchor="rt",
            )
            total_height = title_tbox.height + value_tbox.height

            self.im.alpha_composite(
                short_line,
                (
                    clear_time_pos[0] + 15,
                    clear_time_pos[1] + total_height // 2 - short_line.height // 2 + 10,
                ),
            )

            self.drawer.write(
                f"{layer.rating}",
                size=110,
                position=(
                    clear_time_pos[0] + 15 + short_line.width + 15,
                    clear_time_pos[1] + total_height // 2 + 10,
                ),
                style="black_italic",
                anchor="lm",
            )

            boss_pos = (start_pos[0] - 12, start_pos[1] + 109)
            boss_im = Drawer.open_static(layer.boss_icon)
            boss_im = Drawer.ratio_resize(boss_im, width=boss_mask.width)
            boss_im = Drawer.top_crop(
                boss_im, height=boss_mask.height, top_offset=int(boss_im.height * 0.1)
            )
            boss_im = Drawer.mask_image_with_image(boss_im, boss_mask)
            self.im.alpha_composite(boss_im, boss_pos)

            char_pos = (start_pos[0] - 12, start_pos[1] + 452)

            for char in layer.characters:
                char_im = Drawer.open_static(char.icon)
                char_im = Drawer.resize_crop(char_im, char_mask.size)
                char_im = Drawer.mask_image_with_image(char_im, char_mask)
                self.im.alpha_composite(char_im, char_pos)

                level_flair_pos = (
                    char_pos[0],
                    char_pos[1] + char_mask.height - char_level_flair.height,
                )
                self.im.alpha_composite(char_level_flair, level_flair_pos)
                self.drawer.write(
                    f"Lv. {char.level}",
                    size=24,
                    position=(
                        level_flair_pos[0] + char_level_flair.width // 2,
                        level_flair_pos[1] + char_level_flair.height // 2,
                    ),
                    style="bold",
                    anchor="mm",
                    color=WHITE,
                )

                rank_flair_pos = (
                    char_pos[0] + char_mask.width - char_rank_flair.width,
                    char_pos[1],
                )
                self.im.alpha_composite(char_rank_flair, rank_flair_pos)
                self.drawer.write(
                    f"{char.mindscape}",
                    size=34,
                    position=(
                        rank_flair_pos[0] + char_rank_flair.width // 2,
                        rank_flair_pos[1] + char_rank_flair.height // 2,
                    ),
                    style="bold",
                    anchor="mm",
                    color=WHITE,
                )

                char_pos = (char_pos[0] + 157, char_pos[1])

            if layer.bangboo is not None:
                bangboo_pos = (start_pos[0] + 471 - 12, char_pos[1] + 73)
                bangboo_im = Drawer.open_static(layer.bangboo.icon)
                bangboo_im = Drawer.middle_crop(bangboo_im.resize((250, 250)), bangboo_mask.size)
                bangboo_im = Drawer.mask_image_with_image(bangboo_im, bangboo_mask)
                self.im.alpha_composite(bangboo_im, bangboo_pos)
                level_flair_pos = (
                    bangboo_pos[0],
                    bangboo_pos[1] + bangboo_im.height - bangboo_level_flair.height,
                )
                self.im.alpha_composite(bangboo_level_flair, level_flair_pos)
                self.drawer.write(
                    f"Lv. {layer.bangboo.level}",
                    size=24,
                    position=(
                        level_flair_pos[0] + bangboo_level_flair.width // 2,
                        level_flair_pos[1] + bangboo_level_flair.height // 2,
                    ),
                    style="bold",
                    anchor="mm",
                    color=WHITE,
                )

            start_pos = (start_pos[0] + 746, start_pos[1])

    def draw_fourth_frontier(self) -> None:
        if self.data.fourth_frontier is None:
            return

        frontier = self.data.fourth_frontier
        tbox = self.drawer.write(
            LocaleStr(key="shiyu_4_frontier"),
            size=90,
            position=(1267, 72),
            style="bold",
            locale=self.locale,
        )

        long_line = self.drawer.open_asset("long_line.png")
        self.im.alpha_composite(
            long_line, (tbox.right + 40, tbox.top + tbox.height // 2 - long_line.height // 2)
        )

        self.drawer.write(
            frontier.rating,
            size=110,
            position=(tbox.right + 40 + long_line.width + 30, tbox.top + tbox.height // 2),
            style="black_italic",
            anchor="lm",
        )

        start_pos = (1267, 235)

        char_mask = self.drawer.open_asset("4_char_mask.png")
        char_level_flair = self.drawer.open_asset("4_char_level_flair.png")
        char_rank_flair = self.drawer.open_asset("4_char_rank_flair.png")

        bangboo_mask = self.drawer.open_asset("4_bangboo_mask.png")
        bangboo_level_flair = self.drawer.open_asset("4_bangboo_level_flair.png")

        for layer in frontier.layers:
            char_pos = start_pos

            for char in layer.characters:
                char_im = Drawer.open_static(char.icon)
                char_im = Drawer.resize_crop(char_im, char_mask.size)
                char_im = Drawer.mask_image_with_image(char_im, char_mask)
                self.im.alpha_composite(char_im, char_pos)

                level_flair_pos = (
                    char_pos[0],
                    char_pos[1] + char_mask.height - char_level_flair.height,
                )
                self.im.alpha_composite(char_level_flair, level_flair_pos)
                self.drawer.write(
                    f"Lv. {char.level}",
                    size=24,
                    position=(
                        level_flair_pos[0] + char_level_flair.width // 2,
                        level_flair_pos[1] + char_level_flair.height // 2,
                    ),
                    style="bold",
                    anchor="mm",
                    color=WHITE,
                )

                rank_flair_pos = (
                    char_pos[0] + char_mask.width - char_rank_flair.width,
                    char_pos[1],
                )
                self.im.alpha_composite(char_rank_flair, rank_flair_pos)
                self.drawer.write(
                    f"{char.mindscape}",
                    size=34,
                    position=(
                        rank_flair_pos[0] + char_rank_flair.width // 2,
                        rank_flair_pos[1] + char_rank_flair.height // 2,
                    ),
                    style="bold",
                    anchor="mm",
                    color=WHITE,
                )

                char_pos = (char_pos[0] + 253, char_pos[1])

            if layer.bangboo is not None:
                bangboo_im = Drawer.open_static(layer.bangboo.icon)
                bangboo_im = Drawer.middle_crop(bangboo_im.resize((250, 250)), bangboo_mask.size)
                bangboo_im = Drawer.mask_image_with_image(bangboo_im, bangboo_mask)
                self.im.alpha_composite(bangboo_im, (start_pos[0] + 759, start_pos[1] + 77))

                level_flair_pos = (
                    start_pos[0] + 759,
                    start_pos[1] + 77 + bangboo_im.height - bangboo_level_flair.height,
                )
                self.im.alpha_composite(bangboo_level_flair, level_flair_pos)
                self.drawer.write(
                    f"Lv. {layer.bangboo.level}",
                    size=24,
                    position=(
                        level_flair_pos[0] + bangboo_level_flair.width // 2,
                        level_flair_pos[1] + bangboo_level_flair.height // 2,
                    ),
                    style="bold",
                    anchor="mm",
                    color=WHITE,
                )

            start_pos = (start_pos[0] + 1155, start_pos[1])

    def draw(self) -> BytesIO:
        self.im = Drawer.open_image("hoyo-buddy-assets/assets/shiyu-v2/bg.png")
        self.drawer = Drawer(ImageDraw.Draw(self.im), folder="shiyu-v2", dark_mode=False, sans=True)

        self.write_stats()
        self.draw_fourth_frontier()
        self.draw_fifth_frontier()
        self.write_uid()
        return Drawer.save_image(self.im)
