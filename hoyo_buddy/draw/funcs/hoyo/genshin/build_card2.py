from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer

from .common import ADD_HURT_ELEMENTS, ELEMENT_BG_COLORS, STATS_ORDER

if TYPE_CHECKING:
    import enka

__all__ = ("GITempTwoBuildCard",)


class GITempTwoBuildCard:
    def __init__(
        self,
        *,
        locale: str,
        dark_mode: bool,
        character: enka.gi.Character,
        character_image: str,
        english_name: str,
        top_crop: bool,
        zoom: float = 1.0,
    ) -> None:
        self._locale = locale
        self._dark_mode = dark_mode
        self._character = character
        self._character_image = character_image
        self._english_name = english_name
        self._theme = "dark" if dark_mode else "light"
        self._zoom = zoom
        self._top_crop = top_crop

    def draw(self) -> BytesIO:
        character = self._character
        color_1 = (230, 230, 230) if self._dark_mode else (94, 94, 94)
        color_2 = (141, 141, 141) if self._dark_mode else (206, 206, 206)
        color_3 = (243, 243, 243) if self._dark_mode else (156, 156, 156)

        im = Drawer.open_image(f"hoyo-buddy-assets/assets/gi-build-card2/{self._theme}_card.png")
        drawer = Drawer(ImageDraw.Draw(im), folder="gi-build-card2", dark_mode=self._dark_mode)

        # Character image
        element_color = drawer.hex_to_rgb(ELEMENT_BG_COLORS[self._dark_mode][character.element])
        img_mask = drawer.open_asset("img_mask.png")
        img = drawer.open_static(self._character_image)
        img = drawer.modify_image_for_build_card(
            img,
            target_width=img_mask.width,
            target_height=img_mask.height,
            mask=img_mask,
            background_color=element_color,
            zoom=self._zoom,
            top_crop=self._top_crop,
        )
        img = drawer.mask_image_with_image(img, img_mask)
        im.alpha_composite(img, (79, 66))

        # Character level
        tbox = drawer.write(
            f"Lv.{character.level}",
            size=104,
            style="regular",
            position=(0, 0),
            gothic=True,
            no_write=True,
        )
        text_im = Image.new("RGBA", (tbox.width, tbox.height * 2))
        text_im_drawer = Drawer(
            ImageDraw.Draw(text_im), folder="gi-build-card2", dark_mode=self._dark_mode
        )
        text_im_drawer.write(
            f"Lv.{character.level}",
            size=104,
            style="regular",
            position=(0, 0),
            gothic=True,
            color=color_1,
        )
        text_im = text_im.rotate(-90, expand=True)
        im.alpha_composite(text_im, (2414, 83))

        # Stars
        stars = drawer.open_asset(f"stars_{character.rarity}.png")
        stars = drawer.mask_image_with_color(stars, color_3)
        im.alpha_composite(stars, (2426, 378))

        # Name
        size = drawer.calc_dynamic_fontsize(
            self._english_name, 935, 251, drawer._get_font(251, "light", gothic=True)
        )
        tbox = drawer.write(
            self._english_name,
            size=size,
            style="light",
            position=(0, 0),
            gothic=True,
            no_write=True,
        )
        text_im = Image.new("RGBA", (tbox.width, tbox.height))
        text_im_drawer = Drawer(
            ImageDraw.Draw(text_im), folder="gi-build-card2", dark_mode=self._dark_mode
        )
        text_im_drawer.write(
            self._english_name,
            size=size,
            style="light",
            position=(0, 0),
            gothic=True,
            color=color_1,
            anchor="lt",
        )
        text_im = text_im.rotate(-90, expand=True)
        im.alpha_composite(text_im, (2685 - text_im.width // 2, 66))

        # Consts
        start_pos = (104, 1110)
        y_diff = 119
        for i, const in enumerate(character.constellations):
            icon = drawer.open_static(const.icon, mask_color=color_1 if const.unlocked else color_2)
            im.alpha_composite(icon, (start_pos[0], start_pos[1] + y_diff * i))

        # Weapon
        weapon = character.weapon
        weapon_mask = drawer.open_asset("weapon_mask.png")
        icon = drawer.open_static(weapon.icon)
        icon = drawer.resize_crop(icon, weapon_mask.size)
        icon = drawer.mask_image_with_image(icon, weapon_mask)
        im.alpha_composite(icon, (320, 1351))

        # Weapon rarity
        stars = drawer.open_asset(f"stars_{weapon.rarity}.png", mask_color=color_3, size=(28, 139))
        im.alpha_composite(stars, (278, 1353))

        # Weapon name
        texts = drawer._wrap_text(
            weapon.name,
            187,
            2,
            drawer._get_font(46, "medium", locale=Locale(self._locale), gothic=True),
        ).split("\n")
        start_pos = (707, 1375)
        line_height = 50
        for text in texts:
            drawer.write(
                text,
                size=46,
                style="medium",
                position=start_pos,
                gothic=True,
                color=color_1,
                anchor="rt",
            )
            start_pos = start_pos[0], start_pos[1] + line_height

        # Weapon level
        level_tbox = drawer.write(
            f"Lv.{weapon.level} R{weapon.refinement}",
            size=35,
            style="medium",
            position=(0, 0),
            no_write=True,
        )
        level_tbox = drawer.write(
            f"Lv.{weapon.level} R{weapon.refinement}",
            size=35,
            style="medium",
            position=(start_pos[0] - level_tbox.width, start_pos[1] + 5),
            color=color_1,
        )

        # Weapon stats
        stat1 = weapon.stats[1] if len(weapon.stats) > 1 else weapon.stats[0]
        stat1_tbox = drawer.write(
            f"{stat1.formatted_value}",
            size=35,
            style="medium",
            position=(0, 0),
            no_write=True,
        )
        stat1_tbox = drawer.write(
            f"{stat1.formatted_value}",
            size=35,
            style="medium",
            position=(level_tbox.right - stat1_tbox.width, 1537),
            color=color_1,
        )
        stat1_icon = drawer.open_asset(f"stats/{stat1.type}.png", mask_color=color_1, size=(35, 35))
        stat1_icon_x = stat1_tbox.left - stat1_icon.width - 31
        stat1_icon_y = stat1_tbox.top + (stat1_tbox.height - stat1_icon.height) // 2
        im.alpha_composite(stat1_icon, (stat1_icon_x, stat1_icon_y))

        if len(weapon.stats) > 1:
            stat2 = weapon.stats[0]
            stat2_tbox = drawer.write(
                f"{stat2.formatted_value}",
                size=35,
                style="medium",
                position=(0, 0),
                no_write=True,
            )
            stat2_tbox = drawer.write(
                f"{stat2.formatted_value}",
                size=35,
                style="medium",
                position=(stat1_icon_x - stat2_tbox.width - 50, 1537),
                color=color_1,
            )
            stat2_icon = drawer.open_asset(
                f"stats/{stat2.type}.png", mask_color=color_1, size=(35, 35)
            )
            stat2_icon_x = stat2_tbox.left - 50
            stat2_icon_y = stat2_tbox.top + (stat2_tbox.height - stat2_icon.height) // 2
            im.alpha_composite(stat2_icon, (stat2_icon_x, stat2_icon_y))

        # Talents
        start_pos = (316, 1679)
        x_diff = 150
        talents = character.talents
        if character.id == 10000002:  # Ayaka
            talents.pop(0)
        elif character.id == 10000041:  # Mona
            talents.pop(2)

        for i, talent in enumerate(talents):
            icon = drawer.open_static(talent.icon, size=(98, 98), mask_color=color_1)
            im.alpha_composite(icon, (start_pos[0] + x_diff * i, start_pos[1]))
            drawer.write(
                str(talent.level),
                size=39,
                style="medium",
                position=(
                    start_pos[0] + x_diff * i + icon.width // 2,
                    start_pos[1] + icon.height + 30,
                ),
                color=color_1,
                anchor="mm",
            )

        # Stats
        stats_layer = drawer.open_asset("stats_layer.png", mask_color=color_1)
        im.alpha_composite(stats_layer, (851, 1504))

        start_pos = (919, 1504)
        for i, stat_type in enumerate(STATS_ORDER):
            stat = character.stats.get(stat_type)
            drawer.write(
                stat.formatted_value if stat is not None else "0",
                size=42,
                style="medium",
                color=color_1,
                position=start_pos,
            )
            start_pos = (1223, 1504) if i == 3 else (start_pos[0], start_pos[1] + 79)

        dmg_stat = character.highest_dmg_bonus_stat
        if dmg_stat.type not in ADD_HURT_ELEMENTS:
            icon_path = character.element.name.title()
        else:
            icon_path = ADD_HURT_ELEMENTS[dmg_stat.type]
        dmg_icon = drawer.open_asset(f"elements/{icon_path}.png", size=(55, 55), mask_color=color_1)
        im.alpha_composite(dmg_icon, (1145, 1743))
        drawer.write(
            dmg_stat.formatted_value,
            size=42,
            style="medium",
            color=color_1,
            position=start_pos,
        )

        # Artifacts
        start_pos = (1938, 1046)
        x_diff = 438
        for i, artifact in enumerate(character.artifacts):
            icon = drawer.open_static(artifact.icon, size=(148, 148))
            im.alpha_composite(icon, (start_pos[0] + 2, start_pos[1]))
            drawer.write(
                f"+{artifact.level}",
                size=42,
                style="medium",
                color=color_1,
                position=(start_pos[0] + 347, start_pos[1] + 39),
                anchor="mm",
            )

            stat = artifact.main_stat
            icon = drawer.open_asset(f"stats/{stat.type}.png", size=(42, 42), mask_color=color_1)
            tbox = drawer.write(
                stat.formatted_value,
                size=42,
                style="medium",
                color=color_1,
                position=(start_pos[0] + 369, start_pos[1] + 125 + icon.height // 2),
                anchor="rm",
            )
            im.alpha_composite(icon, (tbox.left - icon.width - 10, start_pos[1] + 125))

            ss_start_pos = (start_pos[0] + 39, start_pos[1] + 212)
            for j, sub_stat in enumerate(artifact.sub_stats):
                icon = drawer.open_asset(
                    f"stats/{sub_stat.type}.png", size=(35, 35), mask_color=color_3
                )
                im.alpha_composite(icon, ss_start_pos)
                drawer.write(
                    sub_stat.formatted_value,
                    size=35,
                    style="medium",
                    color=color_3,
                    position=(
                        ss_start_pos[0] + icon.width + 20,
                        ss_start_pos[1] + icon.height // 2,
                    ),
                    anchor="lm",
                )
                ss_start_pos = (
                    (start_pos[0] + 39, start_pos[1] + 291)
                    if j == 1
                    else (ss_start_pos[0] + 181, ss_start_pos[1])
                )

            start_pos = (1500, 1470) if i == 1 else (start_pos[0] + x_diff, start_pos[1])

        buffer = BytesIO()
        im.save(buffer, format="WEBP", lossless=True)
        return buffer
