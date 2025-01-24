from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Locale
from discord import utils as dutils
from genshin.models import ZZZFullAgent, ZZZSkillType
from genshin.models import ZZZPropertyType as PropType
from PIL import Image, ImageDraw

from hoyo_buddy.constants import ZZZ_AGENT_CORE_LEVEL_MAP, get_disc_substat_roll_num
from hoyo_buddy.draw.drawer import WHITE, Drawer
from hoyo_buddy.draw.funcs.hoyo.zzz.common import SKILL_ORDER, STAT_ICONS, get_props

if TYPE_CHECKING:
    from io import BytesIO

    from hoyo_buddy.models import AgentNameData


class ZZZAgentCard4:
    def __init__(
        self,
        agent: ZZZFullAgent,
        *,
        locale: str,
        image_url: str,
        disc_icons: dict[int, str],
        name_data: AgentNameData | None,
        color: str,
        show_substat_rolls: bool,
        agent_special_stats: list[int],
        hl_substats: list[int],
        hl_special_stats: bool,
    ) -> None:
        self._agent = agent
        self._locale = Locale(locale)
        self._image_url = image_url
        self._disc_icons = disc_icons
        self._name_data = name_data
        self._color = color
        self._show_substat_rolls = show_substat_rolls
        self._agent_special_stats = agent_special_stats
        self._hl_substats = hl_substats
        self._hl_special_stats = hl_special_stats

        self.im: Image.Image = None  # pyright: ignore[reportAttributeAccessIssue]
        self.drawer: Drawer = None  # pyright: ignore[reportAttributeAccessIssue]

    def _draw_card_base(self) -> None:
        im = self.im
        drawer = self.drawer

        # Open images
        pattern = drawer.open_asset("pattern.png")
        blob_1 = drawer.open_asset("blob_1.png")
        blob_2 = drawer.open_asset("blob_2.png")
        blob_3 = drawer.open_asset("blob_3.png")
        blob_4 = drawer.open_asset("blob_4.png")
        blob_5 = drawer.open_asset("blob_5.png")
        strip = drawer.open_asset("strip.png")

        agent_color = self._color
        blob_color = drawer.hex_to_rgb(agent_color)
        z_blob_color = drawer.blend_color(blob_color, (0, 0, 0), 0.85)

        # Draw patterns
        blob_1 = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_1
        )
        im.alpha_composite(blob_1, (-426, -385))
        blob_2 = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_2
        )
        im.alpha_composite(blob_2, (649, -802))
        blob_3 = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_3
        )
        im.alpha_composite(blob_3, (815, -223))
        blob_4 = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_4
        )
        im.alpha_composite(blob_4, (3132, -713))
        blob_5 = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=blob_5
        )
        im.alpha_composite(blob_5, (2911, 1000))

        strip = drawer.create_pattern_blob(
            color=z_blob_color, rotation=0, pattern=pattern, blob=strip
        )
        strip = drawer.resize_crop(strip, blob_1.size)
        strip = drawer.mask_image_with_image(strip, blob_1)
        im.alpha_composite(strip, (-426, -385))

        signature = drawer.open_asset("signature.png")
        im.alpha_composite(signature, (180, 1521))

    def _draw_img(self) -> None:
        im = self.im
        drawer = self.drawer

        img_mask = drawer.open_asset("img_mask.png")
        img_bk = drawer.open_asset("img_bk.png")
        img = drawer.open_static(self._image_url)
        img = drawer.ratio_resize(img, height=img_mask.height)
        img = drawer.resize_crop(img, img_mask.size)
        img = drawer.mask_image_with_image(img, img_mask)
        im.alpha_composite(img_bk, (190, 99))
        im.alpha_composite(img, (190, 99))

        m_flair = drawer.open_asset("m_flair.png")
        im.alpha_composite(m_flair, (885, 99))
        drawer.write(
            f"M{self._agent.rank}",
            size=72,
            style="bold",
            color=WHITE,
            position=(957, 163),
            anchor="mm",
        )

        level_flair = drawer.open_asset("level_flair.png")
        im.alpha_composite(level_flair, (774, 1195))
        drawer.write(
            f"Lv. {self._agent.level}",
            size=80,
            style="bold",
            color=WHITE,
            position=(902, 1256),
            anchor="mm",
        )

        if self._name_data is not None:
            name = self._name_data.short_name

            tbox = drawer.write(
                name,
                size=280,
                style="black_italic",
                color=(20, 20, 20),
                position=(190, 99 + img.height + 20),
                anchor="lt",
                locale=Locale.american_english,
                no_write=True,
                dynamic_fontsize=True,
                max_width=1233,
            )
            name_im = Image.new("RGBA", (tbox.width, tbox.height), (255, 255, 255, 0))
            name_drawer = Drawer(
                ImageDraw.Draw(name_im), folder="zzz-build-card4", dark_mode=False, sans=True
            )
            name_drawer.write(
                name,
                size=280,
                style="black_italic",
                color=(20, 20, 20),
                position=(0, 0),
                anchor="lt",
                locale=Locale.american_english,
                dynamic_fontsize=True,
                max_width=1233,
            )
            name_im = name_im.rotate(-90, expand=True)
            im.alpha_composite(name_im, (190 - name_im.width // 2, 73))

    def _draw_skills(self) -> None:
        im = self.im
        drawer = self.drawer
        im.alpha_composite(drawer.open_asset("skills.png"), (180, 1383))

        for i, skill_type in enumerate(SKILL_ORDER):
            skill = dutils.get(self._agent.skills, type=skill_type)
            if skill is None:
                continue

            text = (
                ZZZ_AGENT_CORE_LEVEL_MAP[skill.level]
                if skill_type is ZZZSkillType.CORE_SKILL
                else str(skill.level)
            )
            drawer.write(
                text,
                size=70,
                position=(339 + 310 * (i % 3), 1435 + 132 * (i // 3)),
                color=(20, 20, 20),
                style="bold",
                anchor="mm",
            )

    def _draw_stats(self) -> None:
        drawer = self.drawer
        im = self.im
        im.alpha_composite(drawer.open_asset("stats.png"), (1124, 103))

        props = get_props(self._agent)
        for i, prop in enumerate(props):
            if prop is None or not isinstance(prop.type, PropType):
                continue

            color = (
                drawer.get_agent_special_stat_color(self._color)
                if prop.type.value in self._agent_special_stats and self._hl_special_stats
                else (20, 20, 20)
            )

            prop_icon = drawer.open_asset(
                f"stat_icons/{STAT_ICONS[prop.type]}",
                size=(74, 74),
                mask_color=color,
                folder="zzz-build-card",
            )
            im.alpha_composite(prop_icon, (1173, 161 + 122 * i))

            drawer.write(
                prop.name,
                size=62,
                position=(1286, 198 + 122 * i),
                anchor="lm",
                color=color,
                locale=self._locale,
                style="bold",
                dynamic_fontsize=True,
                max_width=508,
            )
            drawer.write(
                prop.final or prop.value,
                size=62,
                position=(2046, 198 + 122 * i),
                anchor="rm",
                color=color,
                style="bold",
            )

    def _draw_weapon(self) -> None:
        drawer = self.drawer
        im = self.im
        im.alpha_composite(drawer.open_asset("weapon.png"), (2184, 103))

        if (engine := self._agent.w_engine) is None:
            return

        weapon_icon = drawer.open_static(engine.icon, size=(692, 692))
        weapon_icon = drawer.mask_image_with_image(
            weapon_icon, drawer.open_asset("weapon_mask.png")
        )
        im.alpha_composite(weapon_icon, (2602, 247))

        tbox = drawer.write(
            engine.name.upper(),
            size=80,
            position=(2222, 129),
            color=(20, 20, 20),
            style="black",
            locale=self._locale,
            max_width=719,
            max_lines=2,
        )

        level_flair = drawer.open_asset("engine_level_flair.png")
        im.alpha_composite(level_flair, (2222, tbox.bottom + 80))
        drawer.write(
            f"Lv. {engine.level}",
            size=60,
            position=(2222 + level_flair.width // 2, tbox.bottom + 80 + level_flair.height // 2),
            color=WHITE,
            style="bold",
            anchor="mm",
        )

        upgrade_flair = drawer.open_asset("upgrade_flair.png")
        im.alpha_composite(upgrade_flair, (2464, tbox.bottom + 80))
        drawer.write(
            f"U{engine.refinement}",
            size=60,
            position=(
                2464 + upgrade_flair.width // 2,
                tbox.bottom + 80 + upgrade_flair.height // 2,
            ),
            color=WHITE,
            style="bold",
            anchor="mm",
        )

        stats = (engine.main_properties[0], engine.properties[0])
        for i, stat in enumerate(stats):
            if isinstance(stat.type, PropType):
                position = (2222, 636 + 79 * i)
                icon = drawer.open_asset(
                    f"stat_icons/{STAT_ICONS[stat.type]}",
                    size=(55, 55),
                    mask_color=(20, 20, 20),
                    folder="zzz-build-card",
                )
                im.alpha_composite(icon, position)
                drawer.write(
                    stat.value,
                    size=46,
                    style="medium",
                    color=(20, 20, 20),
                    position=(position[0] + icon.width + 26, position[1] + icon.height // 2),
                    anchor="lm",
                    locale=self._locale,
                )

    def _draw_discs(self) -> None:
        im = self.im
        drawer = self.drawer
        im.alpha_composite(drawer.open_asset("discs.png"), (2182, 103))

        disc_mask = drawer.open_asset("disc_mask.png")
        disc_num_flair = drawer.open_asset("disc_num_flair.png")

        poses = {
            0: (2184, 904),
            1: (2184, 1304),
            2: (3027, 104),
            3: (3027, 504),
            4: (3027, 904),
            5: (3027, 1304),
        }

        for i in range(6):
            pos = poses[i]

            disc = next((d for d in self._agent.discs if d.position == i + 1), None)
            if disc is None:
                continue

            disc_icon = drawer.open_static(self._disc_icons[disc.id], size=(326, 326))
            disc_icon = drawer.middle_crop(disc_icon, disc_mask.size)
            disc_icon = drawer.mask_image_with_image(disc_icon, disc_mask)
            im.alpha_composite(disc_icon, pos)

            im.alpha_composite(disc_num_flair, (pos[0], pos[1] + 248))
            drawer.write(
                f"{i + 1}",
                size=48,
                position=(pos[0] + 39, pos[1] + 288),
                color=(107, 107, 107),
                style="bold",
                anchor="mm",
            )

            drawer.write(
                f"+{disc.level}",
                size=48,
                position=(pos[0] + 692, pos[1] + 61),
                color=WHITE,
                style="bold",
                anchor="mm",
            )

            main_stat = disc.main_properties[0]
            if isinstance(main_stat.type, PropType):
                main_stat_icon = drawer.open_asset(
                    f"stat_icons/{STAT_ICONS[main_stat.type]}",
                    size=(67, 67),
                    mask_color=(20, 20, 20),
                    folder="zzz-build-card",
                )
                im.alpha_composite(main_stat_icon, (pos[0] + 214, pos[1] + 26))
                drawer.write(
                    main_stat.value,
                    size=60,
                    position=(
                        pos[0] + 214 + main_stat_icon.width + 21,
                        pos[1] + 26 + main_stat_icon.height // 2,
                    ),
                    color=(20, 20, 20),
                    style="bold",
                    anchor="lm",
                )

            for s, substat in enumerate(disc.properties):
                substat_pos = (pos[0] + 214 + 280 * (s % 2), pos[1] + 131 + 92 * (s // 2))
                color = (
                    drawer.get_agent_special_stat_color(self._color)
                    if self._hl_special_stats and int(substat.type) in self._hl_substats
                    else (20, 20, 20)
                )

                if isinstance(substat.type, PropType):
                    substat_icon = drawer.open_asset(
                        f"stat_icons/{STAT_ICONS[substat.type]}",
                        size=(64, 64),
                        mask_color=color,
                        folder="zzz-build-card",
                    )
                    im.alpha_composite(substat_icon, substat_pos)
                    drawer.write(
                        substat.value,
                        size=54,
                        position=(
                            substat_pos[0] + substat_icon.width + 19,
                            substat_pos[1] + substat_icon.height // 2,
                        ),
                        color=color,
                        anchor="lm",
                        style="medium",
                    )

                if self._show_substat_rolls:
                    roll_num = get_disc_substat_roll_num(disc.rarity, substat)
                    roll_num_img = drawer.open_asset(
                        f"rolls/{roll_num}.png",
                        size=(239, 6),
                        folder="zzz-build-card",
                        mask_color=color,
                    )
                    im.alpha_composite(roll_num_img, (substat_pos[0], substat_pos[1] + 75))

    def draw(self) -> BytesIO:
        self.im = im = Drawer.open_image("hoyo-buddy-assets/assets/zzz-build-card4/card_base.png")
        self.drawer = Drawer(
            ImageDraw.Draw(im), folder="zzz-build-card4", dark_mode=False, sans=True
        )

        self._draw_card_base()
        self._draw_img()
        self._draw_skills()
        self._draw_stats()
        self._draw_weapon()
        self._draw_discs()

        return Drawer.save_image(im)
