from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any

import discord
from discord import utils as dutils
from genshin.models import ZZZPropertyType as PropType
from PIL import Image, ImageDraw
from PIL.Image import Transpose

from hoyo_buddy.draw.drawer import Drawer

if TYPE_CHECKING:
    import genshin


def fill_zeros(s: str) -> str:
    number_part = float(s.replace("%", ""))

    if "%" in s:
        formatted_number = f"{number_part:.1f}"
        return f"{formatted_number}%"

    if number_part >= 1000 or number_part >= 100:
        formatted_number = f"{number_part:.0f}"
    elif number_part >= 10:
        formatted_number = f"{number_part:.1f}"
    else:
        formatted_number = f"{number_part:.2f}"
    return formatted_number


STAT_ICONS = {
    # Disc
    PropType.DISC_HP: "HP.png",
    PropType.DISC_ATK: "ATK.png",
    PropType.DISC_DEF: "DEF.png",
    PropType.DISC_PEN: "PEN_RATIO.png",
    PropType.DISC_BONUS_PHYSICAL_DMG: "PHYSICAL.png",
    PropType.DISC_BONUS_FIRE_DMG: "FIRE.png",
    PropType.DISC_BONUS_ICE_DMG: "ICE.png",
    PropType.DISC_BONUS_ELECTRIC_DMG: "ELECTRIC.png",
    PropType.DISC_BONUS_ETHER_DMG: "ETHER.png",
    # W-engine
    PropType.ENGINE_HP: "HP.png",
    PropType.ENGINE_BASE_ATK: "ATK.png",
    PropType.ENGINE_ATK: "ATK.png",
    PropType.ENGINE_DEF: "DEF.png",
    PropType.ENGINE_ENERGY_REGEN: "ENERGY_REGEN.png",
    # Common
    PropType.CRIT_DMG: "CRIT_DMG.png",
    PropType.CRIT_RATE: "CRIT_RATE.png",
    PropType.ANOMALY_PROFICIENCY: "ANOMALY_PRO.png",
    PropType.PEN_RATIO: "PEN_RATIO.png",
    PropType.IMPACT: "IMPACT.png",
}


class ZZZAgentCard:
    def __init__(
        self,
        agent: genshin.models.ZZZFullAgent,
        cn_agent: genshin.models.ZZZFullAgent,
        *,
        locale: str,
        image_url: str,
        agent_data: dict[str, Any],
        disc_icons: dict[str, str],
        agent_full_name: str,
    ) -> None:
        self._agent = agent
        self._en_agent = cn_agent
        self._locale = locale
        self._image_url = image_url
        self._agent_data = agent_data
        self._disc_icons = disc_icons
        self._agent_full_name = agent_full_name

    def draw(self) -> BytesIO:
        im = Image.open(f"hoyo-buddy-assets/assets/zzz-build-card/agents/{self._agent.id}.png")
        draw = ImageDraw.Draw(im)
        drawer = Drawer(
            draw, folder="zzz-build-card", dark_mode=False, locale=discord.Locale(self._locale)
        )

        # Level
        level_text = f"Lv.{self._agent.level}"
        drawer.write(
            level_text,
            position=(self._agent_data["level_x"], self._agent_data["level_y"]),
            size=250,
            color=(41, 41, 41),
            locale=discord.Locale.american_english,
            style="black_italic",
            sans=True,
        )

        # Media rank
        rank_text = drawer.open_asset(f"rank/M{self._agent.rank}.png")
        im.paste(
            rank_text, (self._agent_data["level_x"], self._agent_data["level_y"] + 260), rank_text
        )

        # Agent full name
        text = self._agent_full_name.split(" ", maxsplit=1)
        if len(text) > 1:
            drawer.write(
                "\n".join(text),
                position=(
                    self._agent_data["level_x"] + rank_text.width + 10,
                    self._agent_data["level_y"] + 290,
                ),
                size=72,
                color=(41, 41, 41),
                style="black_italic",
                sans=True,
                locale=discord.Locale.american_english,
            )

        # Agent image
        agent_image = drawer.open_static(
            self._image_url, size=(self._agent_data["image_w"], self._agent_data["image_h"])
        )
        if self._agent_data.get("flip", False):
            # Flip image horizontally
            agent_image = agent_image.transpose(Transpose.FLIP_LEFT_RIGHT)
        im.paste(
            agent_image, (self._agent_data["image_x"], self._agent_data["image_y"]), agent_image
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
                locale=discord.Locale.american_english,
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
                locale=discord.Locale.american_english,
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
                        f"{stat.name}  {fill_zeros(stat.value)}",
                        size=28,
                        style="medium",
                        sans=True,
                        color=(20, 20, 20),
                        position=(
                            stat_positions[i][0] + 60,
                            stat_positions[i][1] + icon.height // 2,
                        ),
                        anchor="lm",
                    )

        # Discs
        start_pos = (74, 670)
        disc_mask = drawer.open_asset("disc_mask.png", size=(125, 152))
        for i, disc in enumerate(self._en_agent.discs):
            icon = drawer.open_static(self._disc_icons[disc.set_effect.name])
            icon = drawer.middle_crop(icon, (125, 152))
            icon = drawer.crop_with_mask(icon, disc_mask)
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
                    fill_zeros(main_stat.value),
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
                    text = fill_zeros(sub_stat.value)

                im.paste(sub_stat_icon, sub_stat_pos, sub_stat_icon)
                drawer.write(
                    text,
                    size=18,
                    position=(sub_stat_pos[0] + 30, sub_stat_pos[1] + sub_stat_icon.height // 2),
                    sans=True,
                    anchor="lm",
                    locale=discord.Locale.american_english,
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
        for i, skill in enumerate(self._agent.skills):
            drawer.write(
                str(skill.level),
                size=48,
                position=start_pos,
                color=(20, 20, 20),
                style="medium",
                sans=True,
                anchor="mm",
                locale=discord.Locale.american_english,
            )
            start_pos = (2852, 554 + 86) if i == 2 else (start_pos[0] + 180, start_pos[1])
        # Stats
        start_pos = (2851, 769)
        props = (
            dutils.get(self._agent.properties, type=PropType.AGENT_HP),
            dutils.get(self._agent.properties, type=PropType.AGENT_ATK),
            dutils.get(self._agent.properties, type=PropType.AGENT_DEF),
            dutils.get(self._agent.properties, type=PropType.AGENT_IMPACT),
            dutils.get(self._agent.properties, type=PropType.AGENT_CRIT_RATE),
            dutils.get(self._agent.properties, type=PropType.AGENT_ANOMALY_MASTERY),
            dutils.get(
                self._agent.properties,
                type=PropType.AGENT_ANOMALY_PROFICIENCY,
            ),
            dutils.get(self._agent.properties, type=PropType.AGENT_PEN_RATIO),
            dutils.get(self._agent.properties, type=PropType.AGENT_ENERGY_GEN),
            dutils.get(self._agent.properties, type=PropType.AGENT_CRIT_DMG),
        )
        for i, prop in enumerate(props):
            if prop is None:
                continue
            drawer.write(
                prop.final if prop.final else prop.value,
                size=40,
                position=start_pos,
                color=(20, 20, 20),
                style="regular",
                sans=True,
                locale=discord.Locale.american_english,
            )
            start_pos = (3100, 769) if i == 4 else (start_pos[0], start_pos[1] + 93)

        buffer = BytesIO()
        im.save(buffer, "WEBP", loseless=True)
        return buffer
