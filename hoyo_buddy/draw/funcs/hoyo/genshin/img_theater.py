from __future__ import annotations

import io

import discord
import genshin
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.utils import seconds_to_time


class ImgTheaterCard:
    def __init__(
        self,
        theater: genshin.models.ImgTheaterData,
        chara_consts: dict[int, int],
        locale: str,
        translator: Translator,
    ) -> None:
        self._theater = theater
        self._chara_consts = chara_consts
        self._dark_mode = True  # To write white colored texts
        self._translator = translator
        self._locale = locale
        self._asset_dir = "hoyo-buddy-assets/assets/img-theater"
        self._drawer: Drawer

    @property
    def locale(self) -> discord.Locale:
        return discord.Locale(self._locale)

    def _open_asset(self, asset: str) -> Image.Image:
        return Drawer.open_image(f"{self._asset_dir}/{asset}")

    def _write_large_block_texts(self) -> None:
        self._drawer.write(
            LocaleStr(key="img_theater_large_block_title"),
            size=64,
            position=(112, 83),
            style="bold",
        )

        stats = self._theater.stats
        if hasattr(self._theater, "battle_stats"):
            total_cast_time = seconds_to_time(self._theater.battle_stats.total_cast_seconds)
        else:
            total_cast_time = "N/A"

        lines = (
            LocaleStr(key="img_theater_stats_line_one", act=stats.best_record),
            LocaleStr(key="img_theater_stats_line_two", flower=stats.fantasia_flowers_used),
            LocaleStr(
                key="img_theater_stats_line_three", support=stats.audience_support_trigger_num
            ),
            LocaleStr(key="img_theater_stats_line_four", assist=stats.player_assists),
            LocaleStr(key="img_theater_stats_line_five", time=total_cast_time),
        )
        line_height = 40
        for i, line in enumerate(lines):
            self._drawer.write(line, size=24, position=(112, 175 + i * line_height))

    def _draw_battle_stats(self) -> None:
        if not hasattr(self._theater, "battle_stats"):
            return

        stats = self._theater.battle_stats

        characters = (
            (stats.max_defeat_character, "abyss.most_defeats"),
            (stats.max_damage_character, "img_theater_max_damage"),
            (stats.max_take_damage_character, "abyss.most_dmg_taken"),
        )
        start_pos = (870, 76)

        for character, key in characters:
            if character is not None:
                icon = self._drawer.open_static(character.icon, size=(55, 55))
                self._im.alpha_composite(icon, start_pos)

            self._drawer.write(
                LocaleStr(key=key, val=0 if character is None else character.value),
                size=20,
                position=(start_pos[0] + 67, start_pos[1] + 34),
                anchor="lm",
            )
            start_pos = (start_pos[0], start_pos[1] + 55)

    def _write_legend_block_texts(self) -> None:
        self._drawer.write(
            LocaleStr(key="img_theater_legend_block_support_chara"),
            size=24,
            position=(933, 310),
            anchor="lm",
        )
        self._drawer.write(
            LocaleStr(key="img_theater_legend_block_trial_chara"),
            size=24,
            position=(933, 354),
            anchor="lm",
        )

    def _draw_act_block(self, act: genshin.models.Act, pos: tuple[int, int]) -> None:
        self._drawer.write(
            LocaleStr(key="img_theater_act_block_title", act=act.round_id),
            size=32,
            style="bold",
            position=(pos[0] + 21, pos[1] + 10),
        )

        medal = (
            self._drawer.open_asset("medal.png")
            if act.medal_obtained
            else self._drawer.open_asset("medal_empty.png")
        )
        self._im.paste(medal, (pos[0] + 509, pos[1] + 10), medal)

        padding = 146
        start_pos = (pos[0] + 0, pos[1] + 75)

        for character in act.characters:
            if character.type is genshin.models.TheaterCharaType.SUPPORT:
                name = "support_chara"
            elif character.type is genshin.models.TheaterCharaType.TRIAL:
                name = "trial_chara"
            else:
                name = "normal_chara"

            block = self._drawer.open_asset(f"{name}_block.png")
            const_flair = self._drawer.open_asset(f"{name}_const_flair.png")
            level_flair = self._drawer.open_asset(f"{name}_level_flair.png")

            block_draw = ImageDraw.Draw(block)
            block_drawer = Drawer(
                block_draw,
                folder="img-theater",
                dark_mode=self._dark_mode,
                locale=self.locale,
                translator=self._translator,
            )

            icon = block_drawer.open_static(character.icon)
            icon = self._drawer.resize_crop(icon, (120, 120))
            mask = self._drawer.open_asset("mask.png")
            icon = self._drawer.mask_image_with_image(icon, mask)
            block.paste(icon, (2, 2), icon)

            block.paste(const_flair, (92, 0), const_flair)
            const_text = {
                genshin.models.TheaterCharaType.NORMAL: str(
                    self._chara_consts.get(character.id, "?")
                ),
                genshin.models.TheaterCharaType.SUPPORT: "?",
                genshin.models.TheaterCharaType.TRIAL: "0",
            }
            text = const_text[character.type]
            block_drawer.write(text, size=18, position=(107, 15), anchor="mm", style="bold")

            block.paste(level_flair, (2, 98), level_flair)
            block_drawer.write(
                str(character.level), size=18, position=(27, 110), anchor="mm", style="bold"
            )

            self._im.paste(block, start_pos, block)
            start_pos = (start_pos[0] + padding, start_pos[1])

    def draw(self) -> io.BytesIO:
        self._im = self._open_asset(f"bg_{self._theater.stats.difficulty.value}.png")
        self._drawer = Drawer(
            ImageDraw.Draw(self._im),
            folder="img-theater",
            dark_mode=self._dark_mode,
            locale=self.locale,
            translator=self._translator,
        )

        self._write_large_block_texts()
        self._draw_battle_stats()
        self._write_legend_block_texts()

        start_pos = (76, 431)
        x_padding = 601
        y_padding = 255

        for i, act in enumerate(self._theater.acts):
            self._draw_act_block(
                act, (start_pos[0] + i % 2 * x_padding, start_pos[1] + i // 2 * y_padding)
            )

        buffer = io.BytesIO()
        self._im.save(buffer, format="PNG")
        return buffer
