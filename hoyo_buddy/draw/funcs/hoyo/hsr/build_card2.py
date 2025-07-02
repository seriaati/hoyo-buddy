from __future__ import annotations

from typing import TYPE_CHECKING

import enka
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.draw.funcs.hoyo.hsr.common import get_character_skills, get_character_stats
from hoyo_buddy.enums import Locale

if TYPE_CHECKING:
    from io import BytesIO

    from hoyo_buddy.models import HoyolabHSRCharacter


class HSRBuildCard2:
    def __init__(
        self,
        character: enka.hsr.Character | HoyolabHSRCharacter,
        *,
        locale: str,
        dark_mode: bool,
        image_url: str,
        en_name: str,
    ) -> None:
        self.character = character
        self.locale = Locale(locale)
        self.dark_mode = dark_mode
        self.image_url = image_url
        self.en_name = en_name

        self.color1 = (232, 232, 232) if dark_mode else (94, 94, 94)
        self.color2 = (199, 199, 199) if dark_mode else (156, 156, 156)
        self.color3 = (92, 92, 92) if dark_mode else (131, 131, 131)
        self.color4 = (230, 230, 230) if dark_mode else WHITE
        self.color5 = (128, 128, 128) if dark_mode else (160, 160, 160)
        self.color6 = (204, 204, 204) if dark_mode else (109, 109, 109)

    def draw(self) -> BytesIO:
        character = self.character
        mode = "dark" if self.dark_mode else "light"
        im = Drawer.open_image(f"hoyo-buddy-assets/assets/hsr-build-card2/{mode}.png")
        drawer = Drawer(ImageDraw.Draw(im), folder="hsr-build-card2", dark_mode=self.dark_mode)

        # Character image
        image_mask = drawer.open_asset("image_mask.png")
        image = drawer.open_static(self.image_url)
        image = drawer.resize_crop(image, image_mask.size)
        image = drawer.mask_image_with_image(image, image_mask)
        im.alpha_composite(image, (61, 65))

        # Character name
        tbox = drawer.write(
            self.en_name,
            size=251,
            style="light",
            position=(0, 0),
            gothic=True,
            anchor="lt",
            max_width=915,
            dynamic_fontsize=True,
            no_write=True,
        )
        text_im = Image.new("RGBA", tbox.size)
        text_im_drawer = Drawer(
            ImageDraw.Draw(text_im), folder="gi-build-card2", dark_mode=self.dark_mode
        )
        text_im_drawer.write(
            self.en_name,
            size=251,
            style="light",
            position=(0, 0),
            gothic=True,
            color=self.color1,
            anchor="lt",
            max_width=915,
            dynamic_fontsize=True,
        )
        text_im = text_im.rotate(-90, expand=True)
        im.alpha_composite(text_im, (2780 - text_im.width // 2, 60))

        # Character level
        level_text = f"Lv.{character.level}"
        tbox = drawer.write(
            level_text,
            size=104,
            style="regular",
            position=(0, 0),
            gothic=True,
            no_write=True,
            anchor="lt",
        )
        text_im = Image.new("RGBA", tbox.size)
        text_im_drawer = Drawer(
            ImageDraw.Draw(text_im), folder="gi-build-card2", dark_mode=self.dark_mode
        )
        text_im_drawer.write(
            level_text,
            size=104,
            style="regular",
            position=(0, 0),
            gothic=True,
            color=self.color1,
            anchor="lt",
        )
        text_im = text_im.rotate(-90, expand=True)
        im.alpha_composite(text_im, (2550 - text_im.width // 2, 65))

        # Character rarity
        rarity = character.rarity
        star_im = drawer.open_asset(
            f"stars_{rarity}.png", folder="gi-build-card2", mask_color=self.color2
        )
        im.alpha_composite(star_im, (2501, 378))

        # Eidolons
        start_pos = (81, 1060)
        for eidolon in character.eidolons:
            icon = drawer.open_static(
                eidolon.icon,
                size=(110, 110),
                mask_color=self.color4 if eidolon.unlocked else self.color5,
            )
            im.alpha_composite(icon, start_pos)
            start_pos = (start_pos[0], start_pos[1] + 130)

        # Light cone
        lc = character.light_cone
        if lc is not None:
            icon = drawer.open_static(lc.icon.item, size=(181, 212))
            im.alpha_composite(icon, (289, 1126))

            # Rarity
            stars_im = drawer.open_asset(f"lc_{lc.rarity}_stars.png", mask_color=self.color2)
            im.alpha_composite(stars_im, (279, 1126))

            # Name
            text = lc.name
            lines = drawer.wrap_text(
                text,
                max_width=425,
                max_lines=2,
                font=drawer.get_font(46, "medium", locale=self.locale, gothic=True),
                locale=self.locale,
            ).split("\n")

            start_pos = (786, 1101 if len(lines) == 1 else 1060)
            for line in lines:
                tbox = drawer.write(
                    line,
                    size=46,
                    style="medium",
                    position=start_pos,
                    gothic=True,
                    anchor="rt",
                    color=self.color1,
                    locale=self.locale,
                )
                start_pos = (start_pos[0], start_pos[1] + tbox.height + 10)

            # Level
            text = f"Lv.{lc.level}"
            drawer.write(text, size=36, style="medium", position=(645, 1195), color=self.color1)

            # Superimpose
            text = f"S{lc.superimpose}"
            drawer.write(text, size=30, style="medium", position=(747, 1200), color=self.color1)

            # Stats
            if isinstance(lc, enka.hsr.LightCone):
                start_pos = (786, 1271)

                for stat in lc.stats[:2]:
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=34,
                        style="medium",
                        position=start_pos,
                        color=self.color1,
                        anchor="ra",
                    )
                    icon = drawer.open_static(stat.icon, size=(66, 66), mask_color=self.color1)
                    im.alpha_composite(icon, (tbox.left - 75, start_pos[1] - 12))

                    start_pos = (tbox.left - 101, start_pos[1])

        # Traces
        traces, main_bubbles, sub_bubbles = get_character_skills(character)
        start_pos = (293, 1445)

        for trace_id, trace in traces.items():
            if trace is None:
                continue

            # Main trace
            icon = drawer.open_static(trace.icon, size=(68, 68), mask_color=self.color4)
            im.alpha_composite(icon, start_pos)
            drawer.write(
                str(trace.level),
                size=49,
                style="medium",
                position=(start_pos[0] + 110, start_pos[1] + 33),
                anchor="mm",
                color=self.color4,
            )

            # Main bubble
            circle_height = 72
            circle_x = start_pos[0] + 215
            circle_y = start_pos[1] - 4
            main_bubble = main_bubbles[trace_id]

            if main_bubble is not None:
                icon = drawer.open_static(main_bubble.icon, size=(63, 63), mask_color=self.color4)
                drawer.draw.ellipse(
                    (circle_x, circle_y, circle_x + circle_height, circle_y + circle_height),
                    fill=self.color3,
                )
                im.alpha_composite(
                    icon,
                    (
                        circle_x + circle_height // 2 - icon.width // 2,
                        circle_y + circle_height // 2 - icon.height // 2,
                    ),
                )

            # Sub bubbles
            circle_x += circle_height + 14
            sub_circle_height = 50
            sub_circle_y = circle_y + (circle_height - sub_circle_height) // 2
            sub_bubbles_ = sub_bubbles[trace_id]

            for sub_bubble in sub_bubbles_:
                if sub_bubble is None:
                    continue

                # draw a line in the middle of the circle
                width = 10
                drawer.draw.line(
                    (
                        circle_x - 15,
                        circle_y + circle_height // 2,
                        circle_x + width,
                        circle_y + circle_height // 2,
                    ),
                    fill=self.color3,
                    width=width,
                )
                drawer.draw.ellipse(
                    (
                        circle_x,
                        sub_circle_y,
                        circle_x + sub_circle_height,
                        sub_circle_y + sub_circle_height,
                    ),
                    fill=self.color3,
                )

                icon = drawer.open_static(sub_bubble.icon, size=(50, 50), mask_color=self.color4)
                # place the icon in the middle of the circle
                icon_x = circle_x + (sub_circle_height - icon.width) // 2
                icon_y = sub_circle_y + (sub_circle_height - icon.height) // 2
                im.paste(icon, (icon_x, icon_y), icon)

                circle_x += 64

            start_pos = (start_pos[0], start_pos[1] + 92)

        # Character stats
        start_pos = (900, 1079)
        attributes, _ = get_character_stats(character)

        for index, (icon, value) in enumerate(attributes.items()):
            icon_ = drawer.open_static(icon, size=(85, 85), mask_color=self.color1)
            im.paste(icon_, start_pos, icon_)

            drawer.write(
                value,
                position=(start_pos[0] + icon_.width + 15, icon_.height / 2 + start_pos[1] - 1),
                size=40,
                color=self.color1,
                style="medium",
                anchor="lm",
            )

            start_pos = (1192, 1079) if index == 5 else (start_pos[0], start_pos[1] + 125)

        # Relics
        start_pos = (1577, 1045)

        for index, relic in enumerate(character.relics):
            icon = drawer.open_static(relic.icon, size=(149, 149))
            im.alpha_composite(icon, start_pos)

            # Relic level
            drawer.write(
                f"+{relic.level}",
                size=42,
                position=(start_pos[0] + 346, start_pos[1] + 39),
                anchor="mm",
                color=self.color1,
            )

            # Relic main stat
            main_stat = relic.main_stat
            main_stat_icon = drawer.open_static(
                main_stat.icon, size=(80, 80), mask_color=self.color1
            )
            im.alpha_composite(main_stat_icon, (start_pos[0] + 180, start_pos[1] + 108))
            drawer.write(
                main_stat.formatted_value,
                position=(
                    start_pos[0] + 180 + main_stat_icon.width,
                    start_pos[1] + 108 + main_stat_icon.width // 2,
                ),
                size=42,
                color=self.color1,
                style="medium",
                anchor="lm",
            )

            # Relic sub stats
            sub_stats = relic.sub_stats
            sub_pos = (start_pos[0] + 21, start_pos[1] + 207)

            for sub_index, sub_stat in enumerate(sub_stats):
                sub_stat_icon = drawer.open_static(
                    sub_stat.icon, size=(55, 55), mask_color=self.color6
                )
                im.alpha_composite(sub_stat_icon, sub_pos)
                drawer.write(
                    sub_stat.formatted_value,
                    position=(sub_pos[0] + 60, sub_pos[1] + 27),
                    size=36,
                    color=self.color6,
                    style="medium",
                    anchor="lm",
                )

                if sub_index == 1:
                    sub_pos = (start_pos[0] + 21, sub_pos[1] + 80)
                else:
                    sub_pos = (sub_pos[0] + 181, sub_pos[1])

            if index in {1, 3}:
                start_pos = (start_pos[0] + 438, 1045)
            else:
                start_pos = (start_pos[0], start_pos[1] + 425)

        return Drawer.save_image(im)
