from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, Literal

import discord
from discord import utils as dutils
from genshin.models import ZZZFullAgent, ZZZSkillType
from genshin.models import ZZZPropertyType as PropType
from PIL import Image, ImageDraw
from PIL.Image import Transpose

from hoyo_buddy.constants import ZZZ_AGENT_CORE_SKILL_LVL_MAP, get_disc_substat_roll_num
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
        disc_icons: dict[int, str],
        name_data: AgentNameData | None,
        color: str | None,
        template: Literal[1, 2],
        show_substat_rolls: bool,
        agent_special_stats: list[int],
        hl_special_stats: bool,
    ) -> None:
        self._agent = agent
        self._locale = locale
        self._image_url = image_url
        self._card_data = card_data
        self._disc_icons = disc_icons
        self._name_data = name_data
        self._color = color
        self._template = template
        self._show_substat_rolls = show_substat_rolls
        self._agent_special_stats = agent_special_stats
        self._hl_special_stats = hl_special_stats

    def _draw_background(self) -> Image.Image:
        zzz_text = self._card_data.get("zzz_text", True)
        base_card_temp = 2 if not zzz_text else 1
        card = Drawer.open_image(
            f"hoyo-buddy-assets/assets/zzz-build-card/card_base{base_card_temp}.png"
        )
        draw = ImageDraw.Draw(card)
        drawer = Drawer(draw, folder="zzz-build-card", dark_mode=False, sans=True)

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
                self._name_data.short_name,
                size=460,
                style="black_italic",
                position=name_position,
                color=BLACK,
            )

        bangboo = drawer.open_asset("bangboo.png")
        card.alpha_composite(bangboo, (3113, 1168))

        return card

    def draw(self) -> BytesIO:
        im = self._draw_background()
        draw = ImageDraw.Draw(im)
        drawer = Drawer(draw, folder="zzz-build-card", dark_mode=False, sans=True)

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
        )

        # Media rank
        rank_text = drawer.open_asset(f"rank/M{self._agent.rank}.png")
        level_flip = self._card_data.get("level_flip", False)
        rank_text_pos = (
            (
                self._card_data["level_x"] + tbox.width - rank_text.width,
                self._card_data["level_y"] + 260,
            )
            if level_flip
            else (self._card_data["level_x"], self._card_data["level_y"] + 260)
        )
        im.paste(rank_text, rank_text_pos, rank_text)

        if not level_flip and self._name_data is not None and self._template == 1:
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
                )

        # Stats section
        stats_section = drawer.open_asset("stats_section.png")
        im.paste(stats_section, (2685, 360), stats_section)

        # Skill levels
        start_pos = (2809, 397)
        for i, skill_type in enumerate(SKILL_ORDER):
            skill = dutils.get(self._agent.skills, type=skill_type)
            if skill is None:
                continue

            text = (
                ZZZ_AGENT_CORE_SKILL_LVL_MAP[skill.level]
                if skill_type is ZZZSkillType.CORE_SKILL
                else str(skill.level)
            )
            drawer.write(
                text, size=55, position=start_pos, color=(20, 20, 20), style="bold", anchor="mm"
            )
            start_pos = (2809, 397 + 98) if i == 2 else (start_pos[0] + 205, start_pos[1])

        # Stats
        start_pos = (2720, 616)
        props = get_props(self._agent)
        agent_color = self._color or self._card_data["color"]
        spsecial_stat_names: set[str] = set()

        for i, prop in enumerate(props):
            if prop is None or not isinstance(prop.type, PropType):
                continue

            color = (20, 20, 20)
            if prop.type.value in self._agent_special_stats:
                spsecial_stat_names.add(prop.name)
                if self._hl_special_stats:
                    color = drawer.get_agent_special_stat_color(agent_color)

            prop_icon = drawer.open_asset(
                f"stat_icons/{STAT_ICONS[prop.type]}", size=(59, 59), mask_color=color
            )
            im.alpha_composite(prop_icon, start_pos)
            drawer.write(
                prop.final or prop.value,
                size=40,
                position=(
                    start_pos[0] + prop_icon.width + 17,
                    start_pos[1] + prop_icon.height // 2,
                ),
                color=color,
                style="bold",
                anchor="lm",
            )

            start_pos = (
                (2720, start_pos[1] + 106) if i % 2 != 0 else (start_pos[0] + 283, start_pos[1])
            )

        # Equip section
        equip_section = drawer.open_asset("equip_section.png")
        im.paste(equip_section, (51, 183), equip_section)

        # W-engine
        engine = self._agent.w_engine
        if engine is not None:
            # Engine icon
            icon = drawer.open_static(engine.icon, size=(317, 317))
            im.paste(icon, (460, 202), icon)

            # Engine level
            level_flair = drawer.open_asset("engine_level_flair.png")
            im.paste(level_flair, (617, 447), level_flair)
            drawer.write(
                f"Lv.{engine.level}",
                size=43,
                position=(685, 478),
                color=(255, 255, 255),
                style="bold",
                anchor="mm",
            )

            # Engine star
            star_flair = drawer.open_asset("engine_star_flair.png")
            im.paste(star_flair, (478, 223), star_flair)
            drawer.write(
                str(engine.refinement),
                size=46,
                position=(513, 258),
                color=(255, 255, 255),
                style="bold",
                anchor="mm",
            )

            # Engine name
            name_tbox = drawer.write(
                engine.name.upper().replace("-", " "),
                size=64,
                position=(74, 206),
                max_width=392,
                max_lines=2,
                style="black",
                color=(20, 20, 20),
                locale=discord.Locale(self._locale),
            )
            bottom = name_tbox[3]

            # Engine stats
            stats = (engine.main_properties[0], engine.properties[0])
            stat_positions = {0: (74, bottom + 40), 1: (74, bottom + 40 + 60)}
            for i, stat in enumerate(stats):
                if isinstance(stat.type, PropType):
                    icon = drawer.open_asset(f"stat_icons/{STAT_ICONS[stat.type]}", size=(40, 40))
                    im.paste(icon, stat_positions[i], icon)
                    drawer.write(
                        f"{stat.name}  {stat.value}",
                        size=28,
                        style="bold",
                        color=(20, 20, 20),
                        position=(
                            stat_positions[i][0] + 60,
                            stat_positions[i][1] + icon.height // 2,
                        ),
                        anchor="lm",
                        locale=discord.Locale(self._locale),
                    )

        # Discs
        start_pos = (50, 597)
        disc_mask = drawer.open_asset("disc_mask.png", size=(151, 184))
        disc_num_flair = drawer.open_asset("disc_num_flair.png")

        for i in range(6):
            disc = next((d for d in self._agent.discs if d.position == i + 1), None)

            if disc is not None:
                icon = drawer.open_static(self._disc_icons[disc.id], size=(184, 184))
                icon = drawer.middle_crop(icon, (151, 184))
                icon = drawer.mask_image_with_image(icon, disc_mask)
                im.alpha_composite(icon, start_pos)

                im.alpha_composite(disc_num_flair, (start_pos[0], start_pos[1] + 120))
                drawer.write(
                    str(i + 1),
                    size=36,
                    position=(start_pos[0] + 32, start_pos[1] + 151),
                    style="black",
                    anchor="mm",
                    color=(107, 107, 107),
                )

                drawer.write(
                    f"+{disc.level}",
                    size=24,
                    color=(255, 255, 255),
                    position=(start_pos[0] + 363, start_pos[1] + 37),
                    style="bold",
                    anchor="mm",
                )

                main_stat = disc.main_properties[0]
                if isinstance(main_stat.type, PropType):
                    main_stat_icon = drawer.open_asset(
                        f"stat_icons/{STAT_ICONS[main_stat.type]}", size=(37, 37)
                    )
                    im.paste(
                        main_stat_icon, (start_pos[0] + 168, start_pos[1] + 18), main_stat_icon
                    )
                    drawer.write(
                        main_stat.value,
                        size=34,
                        position=(
                            start_pos[0] + 210,
                            start_pos[1] + 18 + main_stat_icon.height // 2,
                        ),
                        style="bold",
                        anchor="lm",
                    )

                sub_stat_pos = (start_pos[0] + 170, start_pos[1] + 89)
                for j in range(4):
                    try:
                        sub_stat = disc.properties[j]
                    except IndexError:
                        pass
                    else:
                        color = (
                            drawer.get_agent_special_stat_color(agent_color)
                            if self._hl_special_stats and sub_stat.name in spsecial_stat_names
                            else (20, 20, 20)
                        )

                        if isinstance(sub_stat.type, PropType):
                            sub_stat_icon = drawer.open_asset(
                                f"stat_icons/{STAT_ICONS[sub_stat.type]}",
                                size=(28, 28),
                                mask_color=color,
                            )
                        else:
                            sub_stat_icon = drawer.open_asset(
                                "stat_icons/PLACEHOLDER.png", size=(28, 28)
                            )
                        im.paste(sub_stat_icon, sub_stat_pos, sub_stat_icon)

                        text = sub_stat.value
                        drawer.write(
                            text,
                            size=22,
                            position=(
                                sub_stat_pos[0] + 35,
                                sub_stat_pos[1] + sub_stat_icon.height // 2,
                            ),
                            style="bold",
                            anchor="lm",
                            color=color,
                        )

                        if self._show_substat_rolls:
                            roll_num = get_disc_substat_roll_num(disc.rarity, sub_stat)
                            roll_num_img = drawer.open_asset(
                                f"rolls/{roll_num}.png", size=(103, 2), mask_color=color
                            )
                            im.alpha_composite(
                                roll_num_img, (sub_stat_pos[0], sub_stat_pos[1] + 32)
                            )

                    if j == 1:
                        sub_stat_pos = (start_pos[0] + 170, start_pos[1] + 134)
                    else:
                        sub_stat_pos = (sub_stat_pos[0] + 117, sub_stat_pos[1])

            start_pos = (521, 597) if i == 2 else (start_pos[0], start_pos[1] + 233)

        buffer = BytesIO()
        im.save(buffer, "PNG")
        return buffer
