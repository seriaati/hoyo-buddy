from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

import discord
from discord import utils as dutils
from genshin.models import ZZZFullAgent
from genshin.models import ZZZPropertyType as PropType
from PIL import Image, ImageDraw
from PIL.Image import Transpose

from hoyo_buddy.draw.drawer import BLACK, Drawer

from .common import SKILL_ORDER, STAT_ICONS, get_props

if TYPE_CHECKING:
    from hoyo_buddy.models import AgentNameData


class ZZZAgentCard:
    def __init__(
        self,
        agent: ZZZFullAgent,
        *,
        locale: str,
        image_url: str,
        card_data: dict[str, Any],
        disc_icons: dict[str, str],
        name_data: AgentNameData | None,
        color: str | None,
    ) -> None:
        self._agent = agent
        self._locale = locale
        self._image_url = image_url
        self._card_data = card_data
        self._disc_icons = disc_icons
        self._name_data = name_data
        self._color = color

    def _draw_background(self) -> Image.Image:
        card = Drawer.open_image("hoyo-buddy-assets/assets/zzz-build-card/card_base.png")
        draw = ImageDraw.Draw(card)
        drawer = Drawer(draw, folder="zzz-build-card", dark_mode=False)

        # Open images
        pattern = drawer.open_asset("pattern.png")
        blob_left = drawer.open_asset("blob_left.png")
        blob_mid = drawer.open_asset("blob_mid.png")
        blob_rb = drawer.open_asset("blob_rb.png")
        blob_rt = drawer.open_asset("blob_rt.png")
        z_blob = drawer.open_asset("z_blob.png")

        agent_color = self._color or self._card_data["color"]
        blob_color = drawer.hex_to_rgb(agent_color)
        z_blob_color = drawer.blend_color(blob_color, (0, 0, 0), 0.85)

        blob_left = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_left
        )
        card.alpha_composite(blob_left, (-345, -351))
        blob_mid = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_mid
        )
        card.alpha_composite(blob_mid, (947, 176))
        blob_rb = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_rb
        )
        card.alpha_composite(blob_rb, (2534, 709))
        blob_rt = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_rt
        )
        card.alpha_composite(blob_rt, (3004, -174))
        z_blob = drawer.create_pattern_blob(
            color=z_blob_color, rotation=0, pattern=pattern, blob=z_blob
        )
        z_blob = drawer.resize_crop(z_blob, blob_left.size)
        z_blob = drawer.mask_image_with_image(z_blob, blob_left)
        card.alpha_composite(z_blob, (-345, -350))

        logo = drawer.open_asset("logo.png")
        card.alpha_composite(logo, (24, 18))

        if self._name_data is not None:
            name_position = (
                self._card_data.get("name_x", 2234),
                self._card_data.get("name_y", -64),
            )
            drawer.write(
                self._name_data.full_name,
                size=460,
                style="black_italic",
                position=name_position,
                color=BLACK,
                sans=True,
            )

        bangboo = drawer.open_asset("bangboo.png")
        card.alpha_composite(bangboo, (3113, 1168))

        return card

    def draw(self) -> BytesIO:
        im = self._draw_background()
        draw = ImageDraw.Draw(im)
        drawer = Drawer(draw, folder="zzz-build-card", dark_mode=False)

        # Agent image
        agent_image = drawer.open_static(self._image_url)
        agent_image = drawer.resize_crop(
            agent_image, (self._card_data["image_w"], self._card_data["image_h"])
        )
        if self._card_data.get("flip", False):
            # Flip image horizontally
            agent_image = agent_image.transpose(Transpose.FLIP_LEFT_RIGHT)
        im.paste(agent_image, (self._card_data["image_x"], self._card_data["image_y"]), agent_image)

        # Level
        level_text = f"Lv.{self._agent.level}"
        tbox = drawer.write(
            level_text,
            position=(self._card_data["level_x"], self._card_data["level_y"]),
            size=250,
            color=(41, 41, 41),
            style="black_italic",
            sans=True,
        )

        # Media rank
        rank_text = drawer.open_asset(f"rank/M{self._agent.rank}.png")
        if self._card_data.get("level_flip", False):
            im.paste(
                rank_text,
                (
                    self._card_data["level_x"] + tbox.width - rank_text.width,
                    self._card_data["level_y"] + 260,
                ),
                rank_text,
            )
        else:
            im.paste(
                rank_text, (self._card_data["level_x"], self._card_data["level_y"] + 260), rank_text
            )

        if self._name_data is not None:
            # Agent full name
            text = self._name_data.full_name.split(" ", maxsplit=1)
            if len(text) > 1:
                drawer.write(
                    "\n".join(text),
                    position=(
                        self._card_data["level_x"] + rank_text.width + 10,
                        self._card_data["level_y"] + 290,
                    ),
                    size=72,
                    color=(41, 41, 41),
                    style="black_italic",
                    sans=True,
                )

        # Equip section
        equip_section = drawer.open_asset("equip_section.png")
        im.paste(equip_section, (71, 244), equip_section)
        # W-engine
        engine = self._agent.w_engine
        if engine is not None:
            # Engine icon
            icon = drawer.open_static(engine.icon, size=(317, 317))
            im.paste(icon, (480, 263), icon)

            # Engine level
            level_flair = drawer.open_asset("engine_level_flair.png")
            im.paste(level_flair, (663, 510), level_flair)
            drawer.write(
                f"Lv.{engine.level}",
                size=36,
                position=(720, 536),
                color=(255, 255, 255),
                style="medium",
                sans=True,
                anchor="mm",
            )

            # Engine star
            star_flair = drawer.open_asset("engine_star_flair.png")
            im.paste(star_flair, (498, 284), star_flair)
            drawer.write(
                str(engine.refinement),
                size=46,
                position=(533, 318),
                color=(255, 255, 255),
                style="medium",
                sans=True,
                anchor="mm",
            )

            # Engine name
            name_tbox = drawer.write(
                engine.name.upper(),
                size=64,
                position=(94, 267),
                max_width=392,
                max_lines=2,
                style="black",
                color=(20, 20, 20),
                sans=True,
                locale=discord.Locale(self._locale),
            )
            bottom = name_tbox[3]

            # Engine stats
            stats = (engine.main_properties[0], engine.properties[0])
            stat_positions = {0: (94, bottom + 40), 1: (94, bottom + 40 + 60)}
            for i, stat in enumerate(stats):
                if isinstance(stat.type, PropType):
                    icon = drawer.open_asset(f"stat_icons/{STAT_ICONS[stat.type]}", size=(40, 40))
                    im.paste(icon, stat_positions[i], icon)
                    drawer.write(
                        f"{stat.name}  {stat.value}",
                        size=28,
                        style="medium",
                        sans=True,
                        color=(20, 20, 20),
                        position=(
                            stat_positions[i][0] + 60,
                            stat_positions[i][1] + icon.height // 2,
                        ),
                        anchor="lm",
                        locale=discord.Locale(self._locale),
                    )

        # Discs
        start_pos = (74, 670)
        disc_mask = drawer.open_asset("disc_mask.png", size=(125, 152))
        for i, disc in enumerate(self._agent.discs):
            icon = drawer.open_static(self._disc_icons[str(disc.id)])
            icon = drawer.middle_crop(icon, (125, 152))
            icon = drawer.mask_image_with_image(icon, disc_mask)
            im.paste(icon, start_pos, icon)

            drawer.write(
                f"+{disc.level}",
                size=20,
                color=(255, 255, 255),
                position=(start_pos[0] + 301, start_pos[1] + 30),
                anchor="mm",
            )

            main_stat = disc.main_properties[0]
            if isinstance(main_stat.type, PropType):
                main_stat_icon = drawer.open_asset(
                    f"stat_icons/{STAT_ICONS[main_stat.type]}", size=(35, 35)
                )
                im.paste(main_stat_icon, (start_pos[0] + 140, start_pos[1] + 15), main_stat_icon)
                drawer.write(
                    main_stat.value,
                    size=28,
                    position=(start_pos[0] + 185, start_pos[1] + 15 + main_stat_icon.height // 2),
                    style="medium",
                    sans=True,
                    anchor="lm",
                )

            sub_stat_pos = (start_pos[0] + 144, start_pos[1] + 70)
            for j in range(4):
                try:
                    sub_stat = disc.properties[j]
                except IndexError:
                    sub_stat_icon = drawer.open_asset("stat_icons/PLACEHOLDER.png", size=(25, 25))
                    text = "N/A"
                else:
                    if isinstance(sub_stat.type, PropType):
                        sub_stat_icon = drawer.open_asset(
                            f"stat_icons/{STAT_ICONS[sub_stat.type]}", size=(25, 25)
                        )
                    else:
                        sub_stat_icon = drawer.open_asset(
                            "stat_icons/PLACEHOLDER.png", size=(25, 25)
                        )
                    text = sub_stat.value

                im.paste(sub_stat_icon, sub_stat_pos, sub_stat_icon)
                drawer.write(
                    text,
                    size=18,
                    position=(sub_stat_pos[0] + 30, sub_stat_pos[1] + sub_stat_icon.height // 2),
                    sans=True,
                    anchor="lm",
                )

                if j == 1:
                    sub_stat_pos = (start_pos[0] + 144, start_pos[1] + 115)
                else:
                    sub_stat_pos = (sub_stat_pos[0] + 102, sub_stat_pos[1])

            start_pos = (461, 670) if i == 2 else (start_pos[0], start_pos[1] + 193)

        # Stats section
        stats_section = drawer.open_asset("stats_section.png")
        im.paste(stats_section, (2743, 519), stats_section)
        # Skill levels
        start_pos = (2852, 554)
        for i, skill_type in enumerate(SKILL_ORDER):
            skill = dutils.get(self._agent.skills, type=skill_type)
            if skill is None:
                continue
            drawer.write(
                str(skill.level),
                size=48,
                position=start_pos,
                color=(20, 20, 20),
                style="medium",
                sans=True,
                anchor="mm",
            )
            start_pos = (2852, 554 + 86) if i == 2 else (start_pos[0] + 180, start_pos[1])
        # Stats
        start_pos = (2851, 769)
        props = get_props(self._agent)
        for i, prop in enumerate(props):
            if prop is None:
                continue
            drawer.write(
                prop.final or prop.value,
                size=40,
                position=start_pos,
                color=(20, 20, 20),
                style="regular",
                sans=True,
            )
            start_pos = (3100, 769) if i == 4 else (start_pos[0], start_pos[1] + 93)

        buffer = BytesIO()
        im.save(buffer, "WEBP", loseless=True)
        return buffer
