from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.constants import (
    ANIMATED_TEAM_CARD_METHOD,
    ANIMATED_TEAM_CARD_SCALE,
    MAX_SUBSTAT_ROLLS,
    convert_gi_element_to_enka,
)
from hoyo_buddy.draw.drawer import BLACK, AnimatedArea, Drawer
from hoyo_buddy.enums import GenshinElement, Locale
from hoyo_buddy.ui.hoyo.profile.image_settings import get_default_art

from .common import (
    ADD_HURT_ELEMENTS,
    ELEMENT_BG_COLORS,
    ELEMENT_COLORS,
    STATS_ORDER,
    get_substat_rolls,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from io import BytesIO
    from pathlib import Path

    import enka
    from enka.gi import Talent

    from hoyo_buddy.models import HoyolabGICharacter, HoyolabGITalent

__all__ = ("GITeamCard",)

IMAGE_POS = (37, 44)
CARD_SIZE = (971, 809)
MASK_PATH = "hoyo-buddy-assets/assets/gi-team-card/img_mask.png"


class GITeamCard:
    def __init__(
        self,
        *,
        locale: str,
        dark_mode: bool,
        characters: Sequence[enka.gi.Character | HoyolabGICharacter],
        character_images: dict[str, str],
        show_substat_rolls: dict[str, bool],
    ) -> None:
        self._locale = locale
        self._dark_mode = dark_mode
        self._characters = characters
        self._character_images = character_images
        self._show_substat_rolls = show_substat_rolls
        self._theme = "dark" if dark_mode else "light"

    def _open_card(self) -> Image.Image:
        return Drawer.open_image(f"hoyo-buddy-assets/assets/gi-team-card/{self._theme}_card.png")

    @staticmethod
    def _get_element(character: enka.gi.Character | HoyolabGICharacter) -> enka.gi.Element:
        return (
            convert_gi_element_to_enka(character.element)
            if isinstance(character.element, GenshinElement)
            else character.element
        )

    def _element_color(
        self, character: enka.gi.Character | HoyolabGICharacter
    ) -> tuple[int, int, int]:
        element = self._get_element(character)
        return Drawer.hex_to_rgb(ELEMENT_BG_COLORS[self._dark_mode][element])

    def _draw_character_card(
        self, character: enka.gi.Character | HoyolabGICharacter
    ) -> Image.Image:
        im = self._open_card()
        drawer = Drawer(ImageDraw.Draw(im), folder="gi-team-card", dark_mode=self._dark_mode)

        # Character image
        img_mask = drawer.open_asset("img_mask.png")
        img_url = self._character_images[str(character.id)]
        img = drawer.open_static(img_url)
        img = drawer.modify_image_for_build_card(
            img,
            target_width=img_mask.width,
            target_height=img_mask.height,
            mask=img_mask,
            background_color=self._element_color(character),
            zoom=0.7 if img_url == get_default_art(character, is_team=False) else 1.0,
        )
        img = drawer.mask_image_with_image(img, img_mask)
        im.alpha_composite(img, IMAGE_POS)

        self._draw_character_foreground(im, character)
        return im

    def _draw_character_foreground(
        self, im: Image.Image, character: enka.gi.Character | HoyolabGICharacter
    ) -> None:
        # Colors
        color_1 = (237, 237, 237) if self._dark_mode else (95, 95, 95)
        color_2 = (237, 237, 237) if self._dark_mode else (131, 131, 131)
        color_3 = (255, 255, 255) if self._dark_mode else (104, 104, 104)
        color_4 = (110, 110, 110) if self._dark_mode else (237, 237, 237)

        drawer = Drawer(ImageDraw.Draw(im), folder="gi-team-card", dark_mode=self._dark_mode)
        element = self._get_element(character)

        # Character element
        if character.element.name != "NONE":
            element_icon = drawer.open_asset(f"elements/{character.element.name.title()}.png")
            element_icon = drawer.mask_image_with_color(
                element_icon, drawer.hex_to_rgb(ELEMENT_COLORS[element])
            )
            im.alpha_composite(element_icon, (34, 36))

        # Character level
        tbox = drawer.write(
            f"Lv.{character.level}", size=47, style="medium", position=(0, 0), no_write=True
        )
        text_im = Image.new("RGBA", (tbox.width, tbox.height))
        text_im_drawer = Drawer(
            ImageDraw.Draw(text_im), folder="gi-team-card", dark_mode=self._dark_mode
        )
        text_im_drawer.write(
            f"Lv.{character.level}",
            size=47,
            style="medium",
            position=(0, 0),
            color=color_2,
            anchor="lt",
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
        talent_order = character.talent_order
        talents: list[Talent | HoyolabGITalent] = []
        for talent_id in talent_order:
            talent = next((t for t in character.talents if t.id == talent_id), None)
            if talent is None:
                continue
            talents.append(talent)

        for talent in talents:
            icon = drawer.open_static(talent.icon, size=(40, 40), mask_color=color_3)
            im.alpha_composite(icon, start_pos)
            tbox = drawer.write(
                str(talent.level),
                size=25,
                style="medium",
                color=color_1,
                position=(start_pos[0] + 45, start_pos[1] + icon.width / 2),
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
        icon_path = ADD_HURT_ELEMENTS.get(int(dmg_stat.type), character.element.name.title())
        dmg_icon = drawer.open_asset(f"elements/{icon_path}.png", size=(30, 30), mask_color=color_1)
        im.alpha_composite(dmg_icon, (768, 718))
        drawer.write(
            dmg_stat.formatted_value, size=25, style="medium", color=color_1, position=start_pos
        )

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
                texts = drawer.wrap_text(
                    weapon.name, max_width=74, max_lines=2, font=font, locale=Locale(self._locale)
                ).split("\n")
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
                stars = drawer.open_asset(
                    f"stars/weapon_stars_{weapon.rarity}.png", mask_color=color_2
                )
                im.alpha_composite(stars, (start_pos[0] + 105, text_pos[1] + 5))

                # Stats
                stat = weapon.stats[len(weapon.stats) - 1]
                tbox = drawer.write(
                    stat.formatted_value, size=16, style="medium", position=(0, 0), no_write=True
                )
                tbox = drawer.write(
                    stat.formatted_value,
                    size=16,
                    style="medium",
                    position=(start_pos[0] + 165 - tbox.width, start_pos[1] + 130),
                    color=color_2,
                    anchor="lm",
                )
                icon = drawer.open_asset(
                    f"stats/{stat.type.name}.png", size=(16, 16), mask_color=color_2
                )
                icon_x = tbox.left - icon.width - 7
                im.alpha_composite(icon, (icon_x, start_pos[1] + 123))

                if len(weapon.stats) > 1:
                    stat = weapon.stats[0]
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=16,
                        style="medium",
                        position=(0, 0),
                        no_write=True,
                    )
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=16,
                        style="medium",
                        position=(icon_x - tbox.width - 20, start_pos[1] + 130),
                        color=color_2,
                        anchor="lm",
                    )
                    icon = drawer.open_asset(
                        f"stats/{stat.type.name}.png", size=(16, 16), mask_color=color_2
                    )
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
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=19,
                        style="medium",
                        position=(0, 0),
                        no_write=True,
                    )
                    tbox = drawer.write(
                        stat.formatted_value,
                        size=19,
                        style="medium",
                        position=(start_pos[0] + 170 - tbox.width, start_pos[1] + 56),
                        anchor="lm",
                        color=color_1,
                    )
                    icon = drawer.open_asset(
                        f"stats/{stat.type.name}.png", size=(19, 19), mask_color=color_1
                    )
                    im.alpha_composite(icon, (tbox.left - icon.width - 5, start_pos[1] + 47))

                    # Sub stats
                    sub_stat_start_pos = (start_pos[0] + 17, start_pos[1] + 82)
                    sub_stat_rolls = get_substat_rolls(artifact)
                    for j, sub_stat in enumerate(artifact.sub_stats):
                        icon = drawer.open_asset(
                            f"stats/{sub_stat.type.name}.png", size=(16, 16), mask_color=color_2
                        )
                        im.alpha_composite(icon, sub_stat_start_pos)
                        drawer.write(
                            sub_stat.formatted_value,
                            size=16,
                            style="medium",
                            position=(
                                sub_stat_start_pos[0] + icon.width + 7,
                                sub_stat_start_pos[1] + icon.height // 2,
                            ),
                            color=color_2,
                            anchor="lm",
                        )
                        if self._show_substat_rolls[str(character.id)]:
                            drawer.draw_roll_track(
                                im,
                                (sub_stat_start_pos[0], sub_stat_start_pos[1] + 22),
                                (66, 2),
                                rolls=sub_stat_rolls[j],
                                max_rolls=MAX_SUBSTAT_ROLLS[artifact.rarity],
                                color=color_2,
                                empty_color=color_2,
                                gap=2,
                            )

                        sub_stat_start_pos = (
                            (start_pos[0] + 17, sub_stat_start_pos[1] + 34)
                            if j == 1
                            else (sub_stat_start_pos[0] + 78, sub_stat_start_pos[1])
                        )

            start_pos = (564 + x_diff, 35) if i == 2 else (start_pos[0], start_pos[1] + y_diff)

    def _open_background(self) -> Image.Image:
        im = Drawer.open_image(f"hoyo-buddy-assets/assets/gi-team-card/{self._theme}_bg.png")
        if len(self._characters) < 3:
            im = im.crop((0, 0, im.width, 922))
        return im

    @staticmethod
    def _card_pos(index: int) -> tuple[int, int]:
        return (50 + index % 2 * 1025, 60 + index // 2 * 865)

    def draw(self) -> BytesIO:
        im = self._open_background()
        for i, character in enumerate(self._characters):
            im.alpha_composite(self._draw_character_card(character), self._card_pos(i))
        return Drawer.save_image(im)

    def draw_animated(self, animations: Mapping[str, tuple[Path, tuple[int, int]]]) -> BytesIO:
        """Draw the card with animated images for the characters that have them.

        Args:
            animations: Paths of the animations framed in the image mask and their uncropped
                top-lefts in it, by character ID.

        Returns:
            The animated WEBP, or the static card if the animation doesn't fit Discord's limit.
        """
        mask = Drawer.open_image(MASK_PATH)
        background = self._open_background()
        areas: list[AnimatedArea] = []
        animated: list[tuple[enka.gi.Character | HoyolabGICharacter, tuple[int, int]]] = []

        for i, character in enumerate(self._characters):
            pos = self._card_pos(i)
            animation = animations.get(str(character.id))
            if animation is None:
                background.alpha_composite(self._draw_character_card(character), pos)
                continue

            card = self._open_card()
            card.alpha_composite(
                Drawer.mask_image_with_image(
                    Image.new("RGBA", mask.size, self._element_color(character)), mask
                ),
                IMAGE_POS,
            )
            background.alpha_composite(card, pos)
            img_pos = (pos[0] + IMAGE_POS[0], pos[1] + IMAGE_POS[1])
            areas.append(AnimatedArea(*animation, img_pos, mask))
            animated.append((character, pos))

        def draw_foreground(im: Image.Image) -> None:
            for character, pos in animated:
                card = im.crop((*pos, pos[0] + CARD_SIZE[0], pos[1] + CARD_SIZE[1]))
                # Static images are darkened by Drawer.modify_image_for_build_card
                if self._dark_mode:
                    overlay = Image.new("RGBA", mask.size, Drawer.apply_color_opacity(BLACK, 0.1))
                    card.alpha_composite(Drawer.mask_image_with_image(overlay, mask), IMAGE_POS)
                self._draw_character_foreground(card, character)
                im.paste(card, pos)

        return Drawer.draw_animated_areas(
            background,
            draw_foreground,
            areas,
            fallback=self.draw,
            scale=ANIMATED_TEAM_CARD_SCALE,
            method=ANIMATED_TEAM_CARD_METHOD,
        )
