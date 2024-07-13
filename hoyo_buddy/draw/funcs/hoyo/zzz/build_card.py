from io import BytesIO
from typing import Literal

import discord
import genshin
from discord import utils as dutils
from PIL import Image, ImageDraw
from PIL.Image import Transpose

from hoyo_buddy.draw.drawer import Drawer

STAT_ICONS = {
    genshin.models.ZZZPropertyType.ENGINE_HP: "HP.png",
    genshin.models.ZZZPropertyType.DISC_HP: "HP.png",
    genshin.models.ZZZPropertyType.ENGINE_BASE_ATK: "ATK.png",
    genshin.models.ZZZPropertyType.ENGINE_ATK: "ATK.png",
    genshin.models.ZZZPropertyType.DISC_ATK: "ATK.png",
    genshin.models.ZZZPropertyType.DISC_ANOMALY_PROFICIENCY: "ANOMALY_PRO.png",
    genshin.models.ZZZPropertyType.ENGINE_DEF: "DEF.png",
    genshin.models.ZZZPropertyType.DISC_DEF: "DEF.png",
    genshin.models.ZZZPropertyType.CRIT_DMG: "CRIT_DMG.png",
    genshin.models.ZZZPropertyType.CRIT_RATE: "CRIT_RATE.png",
    genshin.models.ZZZPropertyType.ENGINE_ENERGY_REGEN: "ENERGY_REGEN.png",
    genshin.models.ZZZPropertyType.ENGINE_PEN_RATIO: "PEN_RATIO.png",
    genshin.models.ZZZPropertyType.DISC_PEN: "PEN_RATIO.png",
    genshin.models.ZZZPropertyType.ENGINE_IMPACT: "IMPACT.png",
}


class ZZZAgentCard:
    def __init__(
        self,
        agent: genshin.models.ZZZFullAgent,
        en_agent: genshin.models.ZZZFullAgent,
        *,
        locale: str,
        level_data: dict[Literal["x", "y"], int],
        image_url: str,
        image_data: dict[Literal["width", "height", "x", "y"], int],
        disc_icons: dict[str, str],
    ) -> None:
        self._agent = agent
        self._en_agent = en_agent
        self._locale = locale
        self._level_data = level_data
        self._image_url = image_url
        self._image_data = image_data
        self._disc_icons = disc_icons

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
            position=(self._level_data["x"], self._level_data["y"]),
            size=250,
            color=(20, 20, 20),
            locale=discord.Locale.american_english,
            style="black_italic",
            sans=True,
        )

        # Agent image
        agent_image = drawer.open_static(
            self._image_url, size=(self._image_data["width"], self._image_data["height"])
        )
        if self._agent.id == 1121:  # Ben
            # Flip image horizontally
            agent_image = agent_image.transpose(Transpose.FLIP_LEFT_RIGHT)
        im.paste(agent_image, (self._image_data["x"], self._image_data["y"]), agent_image)

        # Equip section
        equip_section = drawer.open_asset("equip_section.png")
        im.paste(equip_section, (71, 244), equip_section)
        # W-engine
        engine = self._agent.w_engine
        if engine is not None:
            icon = drawer.open_static(engine.icon, size=(317, 317))
            im.paste(icon, (462, 249), icon)
            engine_level = drawer.open_asset("engine_level.png")
            im.paste(engine_level, (646, 511), engine_level)
            drawer.write(
                f"Lv.{engine.level}",
                size=36,
                position=(702, 538),
                color=(255, 255, 255),
                style="medium",
                sans=True,
                locale=discord.Locale.american_english,
                anchor="mm",
            )
            name_tbox = drawer.write(
                engine.name.upper(),
                size=64,
                position=(106, 280),
                max_width=392,
                max_lines=2,
                style="black",
                color=(20, 20, 20),
                sans=True,
            )
            bottom = name_tbox[3]

            stats = (engine.main_properties[0], engine.properties[0])
            stat_positions = {0: (106, bottom + 40), 1: (106, bottom + 40 + 60)}
            for i, stat in enumerate(stats):
                if isinstance(stat.type, genshin.models.ZZZPropertyType):
                    icon = drawer.open_asset(f"stat_icons/{STAT_ICONS[stat.type]}", size=(40, 40))
                    im.paste(icon, stat_positions[i], icon)
                tbox = drawer.write(
                    f"{stat.name}  {stat.value}",
                    size=28,
                    style="medium",
                    sans=True,
                    color=(20, 20, 20),
                    position=(0, 0),
                    no_write=True,
                )
                height = tbox[3] - tbox[1]
                drawer.write(
                    f"{stat.name}  {stat.value}",
                    size=28,
                    style="medium",
                    sans=True,
                    color=(20, 20, 20),
                    position=(106 + 50, stat_positions[i][1] + height),
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
            if isinstance(main_stat.type, genshin.models.ZZZPropertyType):
                main_stat_icon = drawer.open_asset(
                    f"stat_icons/{STAT_ICONS[main_stat.type]}", size=(35, 35)
                )
                im.paste(main_stat_icon, (start_pos[0] + 140, start_pos[1] + 15), main_stat_icon)
                drawer.write(
                    main_stat.value,
                    size=28,
                    position=(start_pos[0] + 185, start_pos[1] + 33),
                    style="medium",
                    sans=True,
                    anchor="lm",
                )

            sub_stat_pos = (start_pos[0] + 144, start_pos[1] + 70)
            for j, sub_stat in enumerate(disc.properties):
                if isinstance(sub_stat.type, genshin.models.ZZZPropertyType):
                    sub_stat_icon = drawer.open_asset(
                        f"stat_icons/{STAT_ICONS[sub_stat.type]}", size=(25, 25)
                    )
                    im.paste(sub_stat_icon, sub_stat_pos, sub_stat_icon)
                    drawer.write(
                        sub_stat.value,
                        size=18,
                        position=(sub_stat_pos[0] + 30, sub_stat_pos[1] + 11),
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
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_HP),
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_ATK),
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_DEF),
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_IMPACT),
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_CRIT_RATE),
            dutils.get(
                self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_ANOMALY_MASTERY
            ),
            dutils.get(
                self._agent.properties,
                type=genshin.models.ZZZPropertyType.AGENT_ANOMALY_PROFICIENCY,
            ),
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_PEN_RATIO),
            dutils.get(
                self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_ENERGY_GEN
            ),
            dutils.get(self._agent.properties, type=genshin.models.ZZZPropertyType.AGENT_CRIT_DMG),
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
