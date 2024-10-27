from __future__ import annotations

import contextlib
from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.constants import convert_gi_element_to_enka
from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import GenshinElement
from hoyo_buddy.ui.hoyo.profile.image_settings import get_default_art

from .common import ADD_HURT_ELEMENTS, ELEMENT_BG_COLORS, ELEMENT_COLORS, STATS_ORDER

if TYPE_CHECKING:
    from collections.abc import Sequence

    import enka

    from hoyo_buddy.models import HoyolabGICharacter

__all__ = ("GITeamCard",)


class GITeamCard:
    def __init__(
        self,
        *,
        locale: str,
        dark_mode: bool,
        characters: Sequence[enka.gi.Character | HoyolabGICharacter],
        character_images: dict[str, str],
    ) -> None:
        self._locale = locale
        self._dark_mode = dark_mode
        self._characters = characters
        self._character_images = character_images
        self._theme = "dark" if dark_mode else "light"

    def _draw_character_card(self, character: enka.gi.Character | HoyolabGICharacter) -> Image.Image:
        # Colors
        color_1 = (237, 237, 237) if self._dark_mode else (95, 95, 95)
        color_2 = (237, 237, 237) if self._dark_mode else (131, 131, 131)
        color_3 = (255, 255, 255) if self._dark_mode else (104, 104, 104)
        color_4 = (110, 110, 110) if self._dark_mode else (237, 237, 237)

        im = Drawer.open_image(f"hoyo-buddy-assets/assets/gi-team-card/{self._theme}_card.png")
        drawer = Drawer(ImageDraw.Draw(im), folder="gi-team-card", dark_mode=self._dark_mode)

        element = (
            convert_gi_element_to_enka(character.element)
            if isinstance(character.element, GenshinElement)
            else character.element
        )
        element_color = drawer.hex_to_rgb(ELEMENT_BG_COLORS[self._dark_mode][element])

        # Character image
        img_mask = drawer.open_asset("img_mask.png")
        img_url = self._character_images[str(character.id)]
        img = drawer.open_static(img_url)
        img = drawer.modify_image_for_build_card(
            img,
            target_width=img_mask.width,
            target_height=img_mask.height,
            mask=img_mask,
            background_color=element_color,
            zoom=0.7 if img_url == get_default_art(character, is_team=False) else 1.0,
        )
        img = drawer.mask_image_with_image(img, img_mask)
        im.alpha_composite(img, (37, 44))

        # Character element
        element_icon = drawer.open_asset(f"elements/{character.element.name.title()}.png")
        element_icon = drawer.mask_image_with_color(element_icon, drawer.hex_to_rgb(ELEMENT_COLORS[element]))
        im.alpha_composite(element_icon, (34, 36))

        # Character level
        tbox = drawer.write(f"Lv.{character.level}", size=47, style="medium", position=(0, 0), no_write=True)
        text_im = Image.new("RGBA", (tbox.width, tbox.height))
        text_im_drawer = Drawer(ImageDraw.Draw(text_im), folder="gi-team-card", dark_mode=self._dark_mode)
        text_im_drawer.write(
            f"Lv.{character.level}", size=47, style="medium", position=(0, 0), color=color_2, anchor="lt"
        )
        text_im = text_im.rotate(90, expand=True)
        im.alpha_composite(text_im, (38, 644))

        # Stars
        stars = drawer.open_asset(f"stars/stars_{character.rarity}.png", mask_color=color_2)
        im.alpha_composite(stars, (482, 47))

        # Contellations
        const_bg = drawer.open_asset("const_bg.png", mask_color=color_4)
        im.alpha_composite(const_bg, (477, 449))
        start_pos = (488, 465)
        no_unlock_color = (141, 141, 141) if self._dark_mode else (217, 217, 217)
        for const in character.constellations:
            icon = drawer.open_static(
                const.icon, size=(42, 42), mask_color=color_3 if const.unlocked else no_unlock_color
            )
            im.alpha_composite(icon, start_pos)
            start_pos = (start_pos[0], start_pos[1] + 50)

        # Talents
        skill_bg = drawer.open_asset("skill_bg.png", mask_color=color_4)
        im.alpha_composite(skill_bg, (96, 719))
        start_pos = (133, 726)
        talents = character.talents
        if character.id == 10000002:  # Ayaka
            talents.pop(0)
        elif character.id == 10000041:  # Mona
            talents.pop(2)

        for talent in character.talents:
            icon = drawer.open_static(talent.icon, size=(40, 40), mask_color=color_3)
            im.alpha_composite(icon, start_pos)
            tbox = drawer.write(
                str(talent.level),
                size=25,
                style="medium",
                color=color_1,
                position=(start_pos[0] + 45, start_pos[1] + icon.width // 2),
                anchor="lm",
            )
            start_pos = (tbox.right + 40, start_pos[1])

        # Stats
        stats_bg = drawer.open_asset("stats_bg.png", mask_color=color_4)
        im.alpha_composite(stats_bg, (564, 552))
        stats_layer = drawer.open_asset("stats_layer.png", mask_color=color_1)
        im.alpha_composite(stats_layer, (602, 574))

        start_pos = (639, 572)
        for i, stat_type in enumerate(STATS_ORDER):
            stat = character.stats.get(stat_type)
            drawer.write(
                stat.formatted_value if stat is not None else "0",
                size=25,
                style="medium",
                color=color_1,
                position=start_pos,
            )
            start_pos = (808, 572) if i == 3 else (start_pos[0], start_pos[1] + 48)

        dmg_stat = character.highest_dmg_bonus_stat
        if dmg_stat.type not in ADD_HURT_ELEMENTS:
            icon_path = character.element.name.title()
        else:
            icon_path = ADD_HURT_ELEMENTS[dmg_stat.type]
        dmg_icon = drawer.open_asset(f"elements/{icon_path}.png", size=(30, 30), mask_color=color_1)
        im.alpha_composite(dmg_icon, (768, 718))
        drawer.write(dmg_stat.formatted_value, size=25, style="medium", color=color_1, position=start_pos)

        # Artifacts and weapon
        artifact_layer = drawer.open_asset("artifact_layer.png", mask_color=color_4)
        weapon_layer = drawer.open_asset("weapon_layer.png", mask_color=color_4)
        start_pos = (564, 35)
        x_diff = 199
        y_diff = 173
        for i in range(6):
            if i == 2:  # Weapon
                weapon = character.weapon
                im.alpha_composite(weapon_layer, start_pos)
                icon = drawer.open_static(weapon.icon, size=(60, 60))
                im.alpha_composite(icon, (start_pos[0], start_pos[1] + 5))
                drawer.write(
                    f"Lv.{weapon.level}",
                    size=16,
                    style="medium",
                    position=(start_pos[0] + 112, start_pos[1] + 12),
                    color=color_1,
                    anchor="mm",
                )
                drawer.write(
                    f"R{weapon.refinement}",
                    size=16,
                    style="medium",
                    position=(start_pos[0] + 159, start_pos[1] + 12),
                    color=color_1,
                    anchor="mm",
                )

                # Weapon name
                font = drawer.get_font(19, "medium", locale=Locale(self._locale))
                texts = drawer.wrap_text(weapon.name, max_width=74, max_lines=2, font=font).split("\n")
                if len(texts) == 1 and font.getlength(texts[0]) > 74:
                    # Split the text into two lines
                    texts = [texts[0][: len(texts[0]) // 2], texts[0][len(texts[0]) // 2 :]]

                text_pos = (start_pos[0] + 167, start_pos[1] + 43)
                line_height = 25
                for text in texts:
                    drawer.write(
                        text,
                        size=19,
                        style="medium",
                        position=text_pos,
                        color=color_1,
                        anchor="rt",
                        locale=Locale(self._locale),
                    )
                    text_pos = (text_pos[0], text_pos[1] + line_height)

                # Stars
                stars = drawer.open_asset(f"stars/weapon_stars_{weapon.rarity}.png", mask_color=color_2)
                im.alpha_composite(stars, (start_pos[0] + 105, text_pos[1] + 5))

                # Stats
                stat = weapon.stats[len(weapon.stats) - 1]
                tbox = drawer.write(stat.formatted_value, size=16, style="medium", position=(0, 0), no_write=True)
                tbox = drawer.write(
                    stat.formatted_value,
                    size=16,
                    style="medium",
                    position=(start_pos[0] + 165 - tbox.width, start_pos[1] + 130),
                    color=color_2,
                    anchor="lm",
                )
                icon = drawer.open_asset(f"stats/{stat.type.name}.png", size=(16, 16), mask_color=color_2)
                icon_x = tbox.left - icon.width - 7
                im.alpha_composite(icon, (icon_x, start_pos[1] + 123))

                if len(weapon.stats) > 1:
                    stat = weapon.stats[0]
                    tbox = drawer.write(stat.formatted_value, size=16, style="medium", position=(0, 0), no_write=True)
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=16,
                        style="medium",
                        position=(icon_x - tbox.width - 20, start_pos[1] + 130),
                        color=color_2,
                        anchor="lm",
                    )
                    icon = drawer.open_asset(f"stats/{stat.type.name}.png", size=(16, 16), mask_color=color_2)
                    im.alpha_composite(icon, (tbox.left - icon.width - 7, start_pos[1] + 123))
            else:
                im.alpha_composite(artifact_layer, start_pos)
                artifact = None
                with contextlib.suppress(IndexError):
                    pos_offset = {0: 0, 1: 1, 3: 2, 4: 3, 5: 4}
                    artifact = character.artifacts[pos_offset[i]]
                if artifact is not None:
                    icon = drawer.open_static(artifact.icon, size=(60, 60))
                    im.alpha_composite(icon, (start_pos[0], start_pos[1] + 5))
                    drawer.write(
                        f"+{artifact.level}",
                        size=16,
                        style="medium",
                        position=(start_pos[0] + 154, start_pos[1] + 12),
                        color=color_1,
                        anchor="mm",
                    )

                    # Main stat
                    stat = artifact.main_stat
                    tbox = drawer.write(stat.formatted_value, size=19, style="medium", position=(0, 0), no_write=True)
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=19,
                        style="medium",
                        position=(start_pos[0] + 170 - tbox.width, start_pos[1] + 56),
                        anchor="lm",
                        color=color_1,
                    )
                    icon = drawer.open_asset(f"stats/{stat.type.name}.png", size=(19, 19), mask_color=color_1)
                    im.alpha_composite(icon, (tbox.left - icon.width - 5, start_pos[1] + 47))

                    # Sub stats
                    sub_stat_start_pos = (start_pos[0] + 17, start_pos[1] + 90)
                    for j, sub_stat in enumerate(artifact.sub_stats):
                        icon = drawer.open_asset(f"stats/{sub_stat.type.name}.png", size=(16, 16), mask_color=color_2)
                        im.alpha_composite(icon, sub_stat_start_pos)
                        drawer.write(
                            sub_stat.formatted_value,
                            size=16,
                            style="medium",
                            position=(sub_stat_start_pos[0] + icon.width + 7, sub_stat_start_pos[1] + icon.height // 2),
                            color=color_2,
                            anchor="lm",
                        )

                        sub_stat_start_pos = (
                            (start_pos[0] + 17, sub_stat_start_pos[1] + 34)
                            if j == 1
                            else (sub_stat_start_pos[0] + 78, sub_stat_start_pos[1])
                        )

            start_pos = (564 + x_diff, 35) if i == 2 else (start_pos[0], start_pos[1] + y_diff)

        return im

    def draw(self) -> BytesIO:
        im = Drawer.open_image(f"hoyo-buddy-assets/assets/gi-team-card/{self._theme}_bg.png")
        if len(self._characters) < 3:
            im = im.crop((0, 0, im.width, 922))

        start_pos = (50, 60)
        x_diff = 1025
        y_diff = 865
        for i, character in enumerate(self._characters):
            card = self._draw_character_card(character)
            im.alpha_composite(card, start_pos)
            start_pos = (50, 60 + y_diff) if i == 1 else (start_pos[0] + x_diff, start_pos[1])

        buffer = BytesIO()
        im.save(buffer, format="PNG")
        return buffer
