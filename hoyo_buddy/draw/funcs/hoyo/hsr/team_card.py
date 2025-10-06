from __future__ import annotations

from typing import TYPE_CHECKING, Any

import enka
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.draw.funcs.hoyo.hsr.common import (
    get_character_skills,
    get_character_stats,
    get_stat_icon,
)
from hoyo_buddy.enums import Locale

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

    from hoyo_buddy.models import HoyolabHSRCharacter as HSRCharacter

__all__ = ("HSRTeamCard",)


class HSRTeamCard:
    def __init__(
        self,
        *,
        locale: str,
        characters: Sequence[HSRCharacter | enka.hsr.Character],
        character_images: dict[str, str],
        character_colors: dict[str, Any],
    ) -> None:
        self._locale = locale
        self._characters = characters
        self._character_images = character_images
        self._character_colors = character_colors

    def _draw_character_card(self, character: HSRCharacter | enka.hsr.Character) -> Image.Image:
        im = Drawer.open_image("hoyo-buddy-assets/assets/hsr-team-card/card.png")
        drawer = Drawer(ImageDraw.Draw(im), folder="hsr-team-card", dark_mode=True, sans=True)

        primary = drawer.hex_to_rgb(self._character_colors[str(character.id)])

        img_mask = drawer.open_asset("img_mask.png")
        img = drawer.open_static(self._character_images[str(character.id)])
        img = drawer.modify_image_for_build_card(
            img,
            target_width=img_mask.width,
            target_height=img_mask.height,
            mask=img_mask,
            background_color=primary,
        )
        im.alpha_composite(img, (0, 39))

        level_block = drawer.open_asset("level_block.png", mask_color=primary)
        im.alpha_composite(level_block, (100, 16))
        drawer.write(
            f"Lv.{character.level}", size=32, position=(161, 39), style="medium", anchor="mm"
        )

        eidolon_block = drawer.open_asset("eidolon_block.png", mask_color=primary)
        im.alpha_composite(eidolon_block, (231, 16))
        drawer.write(
            f"E{character.eidolons_unlocked}",
            size=32,
            position=(258, 39),
            style="medium",
            anchor="mm",
        )

        drawer.write(
            character.name,
            size=52,
            position=(307, 65),
            style="bold",
            anchor="lm",
            locale=Locale(self._locale),
            max_width=363,
        )

        stats_layer = drawer.open_asset("stats_layer.png")
        im.alpha_composite(stats_layer, (330, 120))

        stats, max_dmg_add = get_character_stats(character)

        start_pos = (387, 143)
        x_diff = 164
        y_diff = 57

        for i, stat in enumerate(stats.values()):
            if i == len(stats.values()) - 1 and max_dmg_add is not None:
                icon = get_stat_icon(max_dmg_add, size=(52, 48), mask_color=WHITE)
                im.alpha_composite(icon, (494, 402))

            drawer.write(stat, size=26, position=start_pos, style="regular", anchor="lm")

            start_pos = (387 + x_diff, 143) if i == 5 else (start_pos[0], start_pos[1] + y_diff)

        if character.light_cone is not None:
            self._draw_light_cone(character, im, drawer, primary)

        traces, main_bubbles, sub_bubbles = get_character_skills(character)

        # Traces
        trace_block = drawer.open_asset("trace_block.png", mask_color=primary)
        start_pos = (369, 503)
        for trace in traces.values():
            if trace is None:
                continue
            im.alpha_composite(trace_block, start_pos)
            icon = drawer.open_static(trace.icon, size=(36, 36), mask_color=WHITE)
            im.alpha_composite(icon, (start_pos[0] + 4, start_pos[1] + 2))

            drawer.write(
                str(trace.level),
                size=26,
                position=(start_pos[0] + icon.width + 24, start_pos[1] + 2 + icon.height / 2),
                style="medium",
                anchor="mm",
            )

            start_pos = (start_pos[0], start_pos[1] + 49)

        # Main bubbles
        main_bubble = drawer.open_asset("main_bubble.png", mask_color=primary)
        sub_bubble = drawer.open_asset("sub_bubble.png", mask_color=primary)
        line = drawer.open_asset("line.png", mask_color=primary)
        start_pos = (484, 503)
        for trace_id, bubble in main_bubbles.items():
            if bubble is None:
                continue
            im.alpha_composite(main_bubble, start_pos)
            icon = drawer.open_static(bubble.icon, size=(36, 36), mask_color=WHITE)
            im.alpha_composite(
                icon,
                (
                    start_pos[0] + main_bubble.width // 2 - icon.width // 2,
                    start_pos[1] + main_bubble.height // 2 - icon.height // 2,
                ),
            )

            # Sub bubbles
            diff = line.width + sub_bubble.width - 4
            for i, s_bubble in enumerate(sub_bubbles[trace_id]):
                if s_bubble is None:
                    continue

                line_x = start_pos[0] + main_bubble.width + diff * i
                im.alpha_composite(
                    line, (line_x, start_pos[1] + main_bubble.height // 2 - line.height // 2)
                )
                sub_bubble_x = line_x + line.width
                sub_bubble_y = start_pos[1] + 5
                im.alpha_composite(sub_bubble, (sub_bubble_x, sub_bubble_y))
                icon = drawer.open_static(s_bubble.icon, size=(25, 25), mask_color=WHITE)
                im.alpha_composite(
                    icon,
                    (
                        sub_bubble_x + sub_bubble.width // 2 - icon.width // 2,
                        sub_bubble_y + sub_bubble.height // 2 - icon.height // 2,
                    ),
                )

            start_pos = (start_pos[0], start_pos[1] + 49)

        # Relics
        self._draw_relics(character, im, drawer, primary)

        return im

    def _draw_relics(
        self,
        character: HSRCharacter | enka.hsr.Character,
        im: Image.Image,
        drawer: Drawer,
        primary: tuple[int, int, int],
    ) -> None:
        relic_level = drawer.open_asset("relic_level.png", mask_color=primary)
        start_pos = (146, 739)

        for i in range(6):
            relic = next((r for r in character.relics if r.type.value == i + 1), None)

            if relic is not None:
                icon = drawer.open_static(relic.icon, size=(72, 72))
                im.alpha_composite(icon, start_pos)

                # Relic level
                text = f"+{relic.level}"
                level_pos = (start_pos[0] + 42, start_pos[1] - 3)
                im.alpha_composite(relic_level, level_pos)
                drawer.write(
                    text,
                    size=11,
                    position=(
                        level_pos[0] + relic_level.width // 2,
                        level_pos[1] + relic_level.height // 2,
                    ),
                    style="medium",
                    anchor="mm",
                )

                # Relic main stat
                main_stat = relic.main_stat
                main_stat_icon = get_stat_icon(main_stat, size=(30, 30))
                main_stat_pos = (start_pos[0] - 133, start_pos[1] - 11)
                im.alpha_composite(main_stat_icon, main_stat_pos)
                drawer.write(
                    main_stat.formatted_value,
                    size=20,
                    position=(
                        main_stat_pos[0] + main_stat_icon.width + 3,
                        main_stat_pos[1] + main_stat_icon.height // 2,
                    ),
                    style="medium",
                    anchor="lm",
                )

                # Relic sub stats
                sub_start_pos = (start_pos[0] - 133, start_pos[1] + 27)
                for j, sub_stat in enumerate(relic.sub_stats):
                    icon = get_stat_icon(sub_stat, size=(20, 20))
                    im.alpha_composite(icon, sub_start_pos)
                    drawer.write(
                        sub_stat.formatted_value,
                        size=13,
                        position=(
                            sub_start_pos[0] + icon.width + 3,
                            sub_start_pos[1] + icon.height // 2,
                        ),
                        style="regular",
                        anchor="lm",
                    )

                    sub_start_pos = (
                        (start_pos[0] - 133, sub_start_pos[1] + 25)
                        if j == 1
                        else (sub_start_pos[0] + 70, sub_start_pos[1])
                    )

            start_pos = (146, 844) if i == 2 else (start_pos[0] + 226, start_pos[1])

    def _draw_light_cone(
        self,
        character: HSRCharacter | enka.hsr.Character,
        im: Image.Image,
        drawer: Drawer,
        primary: tuple[int, int, int],
    ) -> None:
        lc = character.light_cone
        assert lc is not None
        lc_mask = drawer.open_asset("lc_mask.png")
        lc_icon = drawer.open_static(lc.icon.image)
        border_width = 15
        lc_icon = lc_icon.crop(
            (
                border_width,
                border_width,
                lc_icon.width - border_width,
                lc_icon.height - border_width,
            )
        )
        lc_icon = drawer.resize_crop(lc_icon, (128, 178))
        lc_icon = drawer.mask_image_with_image(lc_icon, lc_mask)
        im.alpha_composite(lc_icon, (19, 503))

        lc_super = drawer.open_asset("lc_super.png", mask_color=primary)
        im.alpha_composite(lc_super, (121, 632))
        drawer.write(
            f"S{lc.superimpose}", size=19, position=(138, 645), style="medium", anchor="mm"
        )

        lc_level = drawer.open_asset("lc_level.png", mask_color=primary)
        im.alpha_composite(lc_level, (89, 663))
        drawer.write(f"Lv.{lc.level}", size=19, position=(122, 676), style="medium", anchor="mm")

        # Light cone name
        drawer.write(
            lc.name,
            size=26,
            position=(168, 500),
            style="bold",
            max_width=180,
            max_lines=3,
            locale=Locale(self._locale),
        )

        # Light cone stats
        start_pos = (168, 620)
        for i, stat in enumerate(lc.stats):
            stat_icon = get_stat_icon(stat, size=(30, 30))
            im.alpha_composite(stat_icon, start_pos)
            tbox = drawer.write(
                stat.formatted_value,
                size=16,
                position=(start_pos[0] + stat_icon.width + 5, start_pos[1] + stat_icon.height // 2),
                style="regular",
                anchor="lm",
            )
            start_pos = (168, 655) if i == 1 else (tbox.right + 20, start_pos[1])

    def draw(self) -> BytesIO:
        im = Drawer.open_image("hoyo-buddy-assets/assets/hsr-team-card/background.png")
        if len(self._characters) < 3:
            im = im.crop((0, 0, im.width, 1068))

        start_pos = (51, 58)
        x_diff = 745
        y_diff = 1010
        for i, character in enumerate(self._characters):
            card = self._draw_character_card(character)
            im.alpha_composite(card, start_pos)
            start_pos = (51, 58 + y_diff) if i == 1 else (start_pos[0] + x_diff, start_pos[1])

        return Drawer.save_image(im)
