from __future__ import annotations

from typing import TYPE_CHECKING

import genshin
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import io

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import HardChallengeMode

LIGHT_PURPLE = (196, 181, 253)


class HardChallengeCard:
    def __init__(
        self,
        data: genshin.models.HardChallenge,
        uid: str,
        locale: Locale,
        *,
        mode: HardChallengeMode,
    ) -> None:
        self._data = data
        self._uid = uid
        self._locale = locale
        self._mode = mode

    def _write_period(self, drawer: Drawer) -> None:
        season = self._data.season
        period = LocaleStr(
            key="hard_challenge_period",
            period=f"{season.start_at.strftime('%Y.%m.%d')} - {season.end_at.strftime('%Y.%m.%d')}",
        )
        drawer.write(
            period,
            size=40,
            position=(754, 64),
            color=LIGHT_PURPLE,
            anchor="mm",
            locale=self._locale,
        )

    def _write_uid(self, drawer: Drawer) -> None:
        drawer.write(
            f"UID: {self._uid}", size=40, position=(754, 121), color=LIGHT_PURPLE, anchor="mm"
        )

    def _write_best_record(self, drawer: Drawer, im: Image.Image) -> None:
        best_record = (
            self._data.single_player.best_record
            if self._mode == "single"
            else self._data.multi_player.best_record
        )
        if best_record is None:
            return

        icon = drawer.open_asset(f"{best_record.icon}.png", size=(100, 100))
        im.paste(icon, (143, 289), icon)

        mode_key = "hard_challenge_type_1" if self._mode == "single" else "hard_challenge_type_2"
        text = LocaleStr(
            custom_str="{title} ({mode})",
            title=LocaleStr(key="role_combat_best_record", mi18n_game=Game.GENSHIN),
            mode=LocaleStr(key=mode_key, mi18n_game=Game.GENSHIN),
        )
        drawer.write(
            text,
            size=48,
            style="black",
            position=(274, 338),
            color=WHITE,
            anchor="lm",
            locale=self._locale,
        )

        second = f"{best_record.time_used}s"
        drawer.write(
            second, size=80, style="black", position=(1205, 338), color=(250, 191, 37), anchor="lm"
        )

    def _draw_challenge_team(
        self,
        drawer: Drawer,
        im: Image.Image,
        pos: tuple[int, int],
        challenge: genshin.models.HardChallengeChallenge,
    ) -> None:
        team_composition = LocaleStr(key="hard_challenge_team_composition")
        tbox = drawer.write(
            team_composition,
            size=40,
            style="bold",
            position=(pos[0] + 48, pos[1] + 328),
            color=LIGHT_PURPLE,
            locale=self._locale,
        )

        flair = drawer.open_asset("char_flair.png")
        bottom = drawer.open_asset("char_bottom.png")
        mask = drawer.open_asset("char_mask.png")
        five_bk = drawer.open_asset("char_5.png")
        four_bk = drawer.open_asset("char_4.png")

        original_pos = (pos[0] + 48, tbox.bottom + 34)

        for i, char in enumerate(challenge.team):
            char_pos = (original_pos[0] + (i * 185), original_pos[1])
            bk = five_bk if char.rarity == 5 else four_bk
            im.paste(bk, char_pos, bk)

            char_icon = drawer.open_static(char.icon)
            char_icon = drawer.resize_crop(char_icon, mask.size)
            char_icon = drawer.mask_image_with_image(char_icon, mask)
            im.paste(char_icon, char_pos, char_icon)

            im.paste(flair, (char_pos[0] + 125, char_pos[1]), flair)
            drawer.write(
                str(char.constellation),
                size=24,
                style="bold",
                position=(char_pos[0] + 125 + flair.width / 2, char_pos[1] + flair.height / 2),
                color=WHITE,
                anchor="mm",
            )

            im.paste(bottom, (char_pos[0], char_pos[1] + bk.height), bottom)
            level = f"Lv.{char.level}"
            drawer.write(
                level,
                size=24,
                style="bold",
                position=(
                    char_pos[0] + bk.width // 2,
                    char_pos[1] + bk.height + bottom.height // 2,
                ),
                color=WHITE,
                anchor="mm",
            )

    def _draw_challenge_stat_box(
        self,
        drawer: Drawer,
        im: Image.Image,
        pos: tuple[int, int],
        challenge: genshin.models.HardChallengeChallenge,
        char: genshin.models.HardChallengeBestCharacter,
    ) -> None:
        is_strike = char.type is genshin.models.HardChallengeBestCharacterType.STRIKE

        stat_box_pos = (pos[0] + 873, pos[1] + 415 + (0 if is_strike else 245))
        stat_box = drawer.open_asset("stat_box.png")

        char_icon = next((c.icon for c in challenge.team if c.id == char.id), None)
        if char_icon:
            mask = drawer.open_asset("stat_char_mask.png")
            char_icon = drawer.open_static(char_icon, size=(126, 126), opacity=0.3)
            char_icon = drawer.mask_image_with_image(char_icon, mask)
            stat_box.alpha_composite(char_icon, (306, 75))

        im.paste(stat_box, stat_box_pos, stat_box)

        text = (
            LocaleStr(key="hard_challenge_strongest_strike")
            if is_strike
            else LocaleStr(key="hard_challenge_damage_dealt")
        )

        strike_tbox = drawer.write(
            text,
            size=32,
            style="medium",
            position=(pos[0] + 959, pos[1] + 468 + (0 if is_strike else 245)),
            color=LIGHT_PURPLE,
            anchor="lm",
            locale=self._locale,
            max_width=327,
            dynamic_fontsize=True,
        )

        icon = drawer.open_asset("zap.png" if is_strike else "target.png")
        icon_pos = (
            strike_tbox.left - 24 - icon.width,
            strike_tbox.top + strike_tbox.height // 2 - icon.height // 2 - 5,
        )
        im.paste(icon, icon_pos, icon)
        drawer.write(
            str(char.value),
            size=64,
            style="bold",
            position=(icon_pos[0], icon_pos[1] + icon.height + 64),
            color=WHITE,
            anchor="lm",
        )

    def _draw_enemy_weakness(
        self,
        drawer: Drawer,
        im: Image.Image,
        pos: tuple[int, int],
        tag: genshin.models.HardChallengeEnemyTag,
    ) -> None:
        is_advantage = tag.type is genshin.models.HardChallengeTagType.ADVANTAGE
        text = LocaleStr(
            key="hard_challenge_advantage" if is_advantage else "hard_challenge_disadvantage"
        )

        if is_advantage:
            pill_color = (45, 60, 85)
            pill_border = (42, 101, 88)
            text_color = (74, 222, 128)
        else:
            pill_color = (74, 35, 81)
            pill_border = (106, 41, 79)
            text_color = (248, 113, 113)

        tbox = drawer.write(
            text, size=24, style="medium", position=(0, 0), no_write=True, locale=self._locale
        )

        # Create a pill
        x_padding = 30
        y_padding = 10
        pill_width = tbox.width + x_padding * 2
        pill_height = tbox.height + y_padding * 2
        pill = Image.new("RGBA", (pill_width, pill_height))
        draw = ImageDraw.Draw(pill)
        draw.rounded_rectangle(
            [(0, 0), (pill_width, pill_height)],
            radius=20,
            fill=pill_color,
            outline=pill_border,
            width=2,
        )
        Drawer(draw, folder="hard-challenge", dark_mode=True).write(
            text,
            size=24,
            style="medium",
            position=(pill_width / 2, pill_height / 2),
            color=text_color,
            anchor="mm",
            locale=self._locale,
        )

        # Paste the pill onto the image
        pill_pos = (pos[0] + 48, pos[1] + (752 if is_advantage else 829))
        im.paste(pill, pill_pos, pill)

        elements = tag.elements
        for i, element in enumerate(elements):
            element_icon = drawer.open_asset(
                f"elements/{element.name}.png", size=(pill.height, pill.height)
            )
            element_pos = (
                pill_pos[0] + pill.width + 20 + i * (element_icon.width + 15),
                pill_pos[1] + (pill.height // 2 - element_icon.height // 2),
            )
            im.paste(element_icon, element_pos, element_icon)

    def _draw_enemy_weaknesses(
        self,
        drawer: Drawer,
        im: Image.Image,
        pos: tuple[int, int],
        challenge: genshin.models.HardChallengeChallenge,
    ) -> None:
        text = LocaleStr(key="hard_challenge_enemy_weakness")
        drawer.write(
            text,
            size=40,
            style="bold",
            position=(pos[0] + 48, pos[1] + 667),
            color=LIGHT_PURPLE,
            locale=self._locale,
        )

        for tag in challenge.enemy.tags:
            self._draw_enemy_weakness(drawer, im, pos, tag)

    def _draw_challenge_stats(
        self,
        drawer: Drawer,
        im: Image.Image,
        pos: tuple[int, int],
        challenge: genshin.models.HardChallengeChallenge,
    ) -> None:
        stats = LocaleStr(key="hard_challenge_combat_statistics")
        drawer.write(
            stats,
            size=40,
            style="bold",
            position=(pos[0] + 873, pos[1] + 328),
            color=LIGHT_PURPLE,
            locale=self._locale,
            max_width=404,
            dynamic_fontsize=True,
        )

        strike = next(
            (
                s
                for s in challenge.best_characters
                if s.type is genshin.models.HardChallengeBestCharacterType.STRIKE
            ),
            None,
        )
        if strike is not None:
            self._draw_challenge_stat_box(drawer, im, pos, challenge, strike)

        damage = next(
            (
                s
                for s in challenge.best_characters
                if s.type is genshin.models.HardChallengeBestCharacterType.DAMAGE
            ),
            None,
        )
        if damage is not None:
            self._draw_challenge_stat_box(drawer, im, pos, challenge, damage)

    def _draw_challenge(
        self,
        drawer: Drawer,
        im: Image.Image,
        pos: tuple[int, int],
        challenge: genshin.models.HardChallengeChallenge,
    ) -> None:
        bk = drawer.open_asset("monster_bk.png")
        im.paste(bk, pos, bk)

        monster_icon = drawer.open_static(challenge.enemy.icon, size=(769, 769))
        color1, color2 = drawer.extract_main_colors(monster_icon)

        mask = drawer.open_asset("monster_mask.png")
        gradient = drawer.draw_gradient_background(
            width=mask.width,
            height=mask.height,
            color1=color1,
            color2=color2,
            pos1=(0.0, 0.5),
            pos2=(1.0, 0.5),
        )
        gradient_masked = drawer.mask_image_with_image(gradient, mask)
        gradient_masked.paste(monster_icon, (-143, -214), monster_icon)
        im.paste(gradient_masked, pos, gradient_masked)

        time_used = f"{challenge.time_used}s"
        drawer.write(
            time_used,
            size=96,
            style="black",
            position=(pos[0] + 1308, pos[1] + 106),
            color=WHITE,
            anchor="rm",
        )

        text = LocaleStr(key="hard_challenge_completion_time")
        tbox = drawer.write(
            text,
            size=32,
            style="medium",
            position=(pos[0] + 1309, pos[1] + 193),
            color=WHITE,
            anchor="rm",
            locale=self._locale,
        )

        clock = drawer.open_asset("clock.png")
        im.paste(
            clock,
            (tbox.left - 20 - clock.width, tbox.top + tbox.height // 2 - clock.height // 2),
            clock,
        )

        self._draw_challenge_team(drawer, im, pos, challenge)
        self._draw_challenge_stats(drawer, im, pos, challenge)
        self._draw_enemy_weaknesses(drawer, im, pos, challenge)

    def draw(self) -> io.BytesIO:
        background = Drawer.open_image("hoyo-buddy-assets/assets/hard-challenge/bk.png")
        drawer = Drawer(
            ImageDraw.Draw(background), folder="hard-challenge", dark_mode=True, sans=True
        )

        self._write_period(drawer)
        self._write_uid(drawer)
        self._write_best_record(drawer, background)

        challenges = (
            self._data.single_player.challenges
            if self._mode == "single"
            else self._data.multi_player.challenges
        )
        for i, challenge in enumerate(challenges):
            self._draw_challenge(drawer, background, pos=(77, 492 + i * 1005), challenge=challenge)

        return drawer.save_image(background)
