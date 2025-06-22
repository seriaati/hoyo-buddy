from __future__ import annotations

from typing import TYPE_CHECKING

import genshin
from PIL import Image, ImageDraw

from hoyo_buddy.constants import TRAVELER_IDS
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import seconds_to_time

if TYPE_CHECKING:
    import io


class ImgTheaterCard:
    def __init__(
        self,
        theater: genshin.models.ImgTheaterData,
        chara_consts: dict[int, int],
        character_icons: dict[str, str],
        locale: str,
        traveler_element: str | None,
    ) -> None:
        self._theater = theater
        self._chara_consts = chara_consts
        self._character_icons = character_icons
        self._dark_mode = True  # To write white colored texts
        self._traveler_element = traveler_element

        self._asset_dir = "hoyo-buddy-assets/assets/img-theater"
        self._drawer: Drawer

        self.locale = Locale(locale)

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
        if hasattr(self._theater, "battle_stats") and self._theater.battle_stats is not None:
            total_cast_time = seconds_to_time(self._theater.battle_stats.total_cast_seconds)
        else:
            total_cast_time = "N/A"

        schedule = self._theater.schedule
        lines = (
            f"{schedule.start_datetime.strftime('%Y/%m/%d')} ~ {schedule.end_datetime.strftime('%Y/%m/%d')}",
            LocaleStr(
                key="total_coin_consumed",
                mi18n_game=Game.GENSHIN,
                append=f": {stats.fantasia_flowers_used}",
            ),
            LocaleStr(
                key="role_combat_avatar_bonus",
                mi18n_game=Game.GENSHIN,
                append=f": {stats.audience_support_trigger_num}",
            ),
            LocaleStr(
                key="role_combat_explain_rent_cnt_title",
                mi18n_game=Game.GENSHIN,
                append=f": {stats.player_assists}",
            ),
            LocaleStr(key="img_theater_stats_line_five", time=total_cast_time),
        )
        line_height = 40
        for i, line in enumerate(lines):
            self._drawer.write(line, size=24, position=(112, 175 + i * line_height))

    def _draw_battle_stats(self) -> None:
        if not hasattr(self._theater, "battle_stats"):
            return

        stats = self._theater.battle_stats
        if stats is None:
            return

        characters = (
            (stats.max_defeat_character, "max_rout_count"),
            (stats.max_damage_character, "max_damage"),
            (stats.max_take_damage_character, "max_take_damage"),
        )
        start_pos = (870, 86)

        for character, key in characters:
            if character is not None:
                icon = self._drawer.open_static(
                    self._character_icons[str(character.id)], size=(45, 45)
                )
                icon = self._drawer.circular_crop(icon)
                self._im.alpha_composite(icon, start_pos)

                self._drawer.write(
                    LocaleStr(key=key, mi18n_game=Game.GENSHIN, append=f": {character.value}"),
                    size=20,
                    position=(start_pos[0] + 54, start_pos[1] + icon.height // 2),
                    anchor="lm",
                )
            start_pos = (start_pos[0], start_pos[1] + 57)

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
        if hasattr(self._theater, "battle_stats") and self._theater.battle_stats is not None:
            fastest_charas = self._theater.battle_stats.fastest_character_list
            is_fastest = [chara.id for chara in fastest_charas] == [
                chara.id for chara in act.characters
            ]
            fastest_text = (
                LocaleStr(key="img_theater_fastest_team").translate(self.locale)
                if is_fastest
                else ""
            )
        else:
            fastest_text = ""

        title = LocaleStr(
            key="role_combat_round_count", mi18n_game=Game.GENSHIN, n=act.round_id
        ).translate(self.locale)
        self._drawer.write(
            title + fastest_text, size=32, style="bold", position=(pos[0] + 21, pos[1] + 10)
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
                block_draw, folder="img-theater", dark_mode=self._dark_mode, locale=self.locale
            )

            icon = block_drawer.open_static(self._character_icons[str(character.id)])
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

            if character.id in TRAVELER_IDS:
                element_flair_pos = (92, 92)
                element_flair = self._drawer.open_asset("normal_chara_element_flair.png")
                block.paste(element_flair, element_flair_pos, element_flair)
                element_icon = self._drawer.open_asset(
                    f"Element_White_{self._traveler_element or character.element}.png",
                    folder="gi-elements",
                    size=(25, 25),
                )
                block.paste(
                    element_icon,
                    (
                        element_flair_pos[0] + element_flair.width // 2 - element_icon.width // 2,
                        element_flair_pos[1] + element_flair.height // 2 - element_icon.height // 2,
                    ),
                    element_icon,
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

        return Drawer.save_image(self._im)
