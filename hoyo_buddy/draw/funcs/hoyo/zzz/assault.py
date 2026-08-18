from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import ImageDraw

from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from io import BytesIO

    import genshin
    from PIL import Image


class AssaultCard:
    def __init__(
        self, data: genshin.models.DeadlyAssault, locale: str, uid: int | None = None
    ) -> None:
        self.data = data
        self.locale = Locale(locale)
        self.uid = uid

        self.text_color = (20, 20, 20)
        self.hard_color = (167, 58, 72)

    @property
    def has_hard(self) -> bool:
        return self.data.has_hard and bool(self.data.hard_challenges)

    def _draw_challenge(
        self,
        im: Image.Image,
        drawer: Drawer,
        challenge: genshin.models.DeadlyAssaultChallenge,
        start_pos: tuple[int, int],
        *,
        star_color: tuple[int, int, int] | None = None,
    ) -> None:
        monster_mask = drawer.open_asset("monster_mask.png")
        agent_mask = drawer.open_asset("agent_mask.png")
        level_flair = drawer.open_asset("level_flair.png")
        rank_flair = drawer.open_asset("rank_flair.png")

        boss_icon = drawer.open_static(challenge.boss.icon, size=(335, 414))
        boss_icon = drawer.mask_image_with_image(boss_icon, monster_mask)
        im.alpha_composite(boss_icon, (start_pos[0], start_pos[1] + 19))

        badge_icon = drawer.open_static(challenge.boss.badge_icon, size=(129, 129))
        im.alpha_composite(badge_icon, (start_pos[0] + 5, start_pos[1] + 296))

        if buffs := challenge.buffs:
            buff_icon = drawer.open_static(buffs[0].icon, size=(87, 87))
            buff_icon = drawer.mask_image_with_color(buff_icon, (220, 217, 217))
            im.alpha_composite(buff_icon, (start_pos[0] + 268, start_pos[1] + 6))

        drawer.write(
            challenge.boss.name,
            position=(start_pos[0] + 387, start_pos[1]),
            color=self.text_color,
            style="bold",
            size=70,
            max_width=744,
            locale=self.locale,
        )

        tbox = drawer.write(
            str(challenge.score),
            position=(start_pos[0] + 387, start_pos[1] + 105),
            color=self.text_color,
            style="black_italic",
            size=96,
        )
        star_icon = drawer.open_asset(f"star_{challenge.star}.png")
        if star_color is not None:
            star_icon = drawer.mask_image_with_color(star_icon, star_color)
        im.alpha_composite(star_icon, (tbox.right + 36, start_pos[1] + 138))

        char_start_pos = (start_pos[0] + 387, start_pos[1] + 270)

        for agent in challenge.agents:
            agent_icon = drawer.open_static(agent.icon)
            agent_icon = drawer.resize_crop(agent_icon, (160, 160))
            agent_icon = drawer.mask_image_with_image(agent_icon, agent_mask)
            im.alpha_composite(agent_icon, char_start_pos)

            im.alpha_composite(rank_flair, (char_start_pos[0] + 122, char_start_pos[1]))
            drawer.write(
                str(agent.mindscape),
                position=(char_start_pos[0] + 140, char_start_pos[1] + 20),
                color=WHITE,
                style="bold",
                size=30,
                anchor="mm",
            )

            im.alpha_composite(level_flair, (char_start_pos[0], char_start_pos[1] + 133))
            drawer.write(
                f"Lv.{agent.level}",
                position=(char_start_pos[0] + 36, char_start_pos[1] + 146),
                color=WHITE,
                style="bold",
                size=22,
                anchor="mm",
            )

            char_start_pos = (char_start_pos[0] + 195, char_start_pos[1])

        if challenge.bangboo is not None:
            bangboo_mask = drawer.open_asset("bangboo_mask.png")
            bangboo_level_flair = drawer.open_asset("bangboo_level_flair.png")

            if hasattr(challenge.bangboo, "icon"):
                bangboo_icon = drawer.open_static(challenge.bangboo.icon)
                bangboo_icon = drawer.middle_crop(bangboo_icon.resize((250, 250)), (160, 115))
                bangboo_icon = drawer.mask_image_with_image(bangboo_icon, bangboo_mask)
                im.alpha_composite(bangboo_icon, (start_pos[0] + 972, start_pos[1] + 316))

            im.alpha_composite(bangboo_level_flair, (start_pos[0] + 972, start_pos[1] + 404))
            drawer.write(
                f"Lv.{challenge.bangboo.level}",
                position=(start_pos[0] + 1008, start_pos[1] + 417),
                color=WHITE,
                style="bold",
                size=22,
                anchor="mm",
            )

    def draw(self) -> BytesIO:
        has_hard = self.has_hard
        background = "background_hard.png" if has_hard else "background.png"
        im = Drawer.open_image(f"hoyo-buddy-assets/assets/assault/{background}")
        drawer = Drawer(ImageDraw.Draw(im), folder="assault", dark_mode=False, sans=True)
        data = self.data

        # UID
        if self.uid is not None:
            drawer.write(
                f"UID: {self.uid}",
                position=(2513, 15),
                color=self.text_color,
                style="bold_italic",
                size=40,
                anchor="rt",
            )

        # Relevant season
        if data.start_time is not None and data.end_time is not None:
            drawer.write(
                LocaleStr(key="shiyu_relevant_season"),
                position=(91, 593),
                color=self.text_color,
                style="medium_italic",
                size=54,
                locale=self.locale,
            )
            drawer.write(
                f"{data.start_time.strftime('%m/%d/%y')} ~ {data.end_time.strftime('%m/%d/%y')}",
                position=(91, 678),
                color=self.text_color,
                style="bold_italic",
                size=62,
            )

        # Rank percent, total score, total stars
        y_offset = 595 if has_hard else 0
        drawer.write(
            data.rank_percent,
            position=(181, 1275 + y_offset),
            color=self.text_color,
            style="bold_italic",
            size=48,
            anchor="mm",
        )
        # In the hard layout the film strip reaches further right at the total's
        # position, so shrink long totals to keep the star count off the strip
        tbox = drawer.write(
            str(data.total_score),
            position=(110, 1283 + y_offset),
            color=self.text_color,
            style="black_italic",
            size=160,
            max_width=460 if has_hard else None,
            dynamic_fontsize=has_hard,
        )

        big_star = drawer.open_asset("big_star.png")
        im.alpha_composite(big_star, (tbox.right + 43, 1334 + y_offset))
        drawer.write(
            f"x{data.total_star}",
            position=(tbox.right + 173, 1368 + y_offset),
            color=self.text_color,
            style="bold_italic",
            size=68,
        )

        # Boss challenges
        for i, challenge in enumerate(data.challenges):
            self._draw_challenge(im, drawer, challenge, (1313, 61 + i * 487))

        if has_hard:
            if data.hard_rank_percent is not None:
                drawer.write(
                    data.hard_rank_percent,
                    position=(2322, 1561),
                    color=WHITE,
                    style="bold_italic",
                    size=48,
                    anchor="mm",
                )
            self._draw_challenge(
                im, drawer, data.hard_challenges[0], (1313, 1630), star_color=self.hard_color
            )

        return Drawer.save_image(im)
