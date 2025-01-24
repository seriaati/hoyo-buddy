from __future__ import annotations

from typing import TYPE_CHECKING

from discord import Locale
from discord import utils as dutils
from genshin.models import ZZZPropertyType as PropType
from genshin.models import ZZZSkillType
from PIL import Image, ImageDraw

from hoyo_buddy.constants import ZZZ_AGENT_CORE_LEVEL_MAP, get_disc_substat_roll_num
from hoyo_buddy.draw.drawer import BLACK, WHITE, Drawer

from .common import SKILL_ORDER, STAT_ICONS, get_props

if TYPE_CHECKING:
    from collections.abc import Sequence
    from io import BytesIO

    from genshin.models import ZZZFullAgent

    from hoyo_buddy.models import AgentNameData


class ZZZTeamCard:
    def __init__(
        self,
        *,
        locale: str,
        agents: Sequence[ZZZFullAgent],
        agent_colors: dict[int, str],
        agent_images: dict[int, str],
        name_datas: dict[int, AgentNameData],
        disc_icons: dict[int, str],
        show_substat_rolls: dict[int, bool],
        agent_special_stat_map: dict[str, list[int]],
        agent_hl_substat_map: dict[int, list[int]],
        hl_special_stats: dict[int, bool],
    ) -> None:
        self._locale = locale
        self._dark_mode = False
        self._agents = agents
        self._agent_colors = agent_colors
        self._agent_images = agent_images
        self._name_datas = name_datas
        self._disc_icons = disc_icons
        self._show_substat_rolls = show_substat_rolls
        self._agent_special_stat_map = agent_special_stat_map
        self._agent_hl_substat_map = agent_hl_substat_map
        self._hl_special_stats = hl_special_stats

    def _draw_card(self, *, image_url: str, blob_color: tuple[int, int, int]) -> Image.Image:
        card = Drawer.open_image("hoyo-buddy-assets/assets/zzz-team-card/card.png")
        draw = ImageDraw.Draw(card)
        drawer = Drawer(draw, folder="zzz-team-card", dark_mode=self._dark_mode, sans=True)

        # Open images
        pattern = drawer.open_asset("pattern.png")
        right_blob = drawer.open_asset("right_blob.png")
        middle_blob = drawer.open_asset("middle_blob.png")
        left_blob = drawer.open_asset("left_blob.png")

        right_blob = drawer.create_pattern_blob(
            color=blob_color, rotation=30, pattern=pattern, blob=right_blob
        )
        card.alpha_composite(right_blob, (880, -100))
        middle_blob = drawer.create_pattern_blob(
            color=blob_color, rotation=90, pattern=pattern, blob=middle_blob
        )
        card.alpha_composite(middle_blob, (570, -100))
        left_blob = drawer.create_pattern_blob(
            color=blob_color, rotation=0, pattern=pattern, blob=left_blob
        )
        card.alpha_composite(left_blob, (13, -30))

        chara_img_bg = drawer.open_asset("chara_img.png")
        chara_img = drawer.open_static(image_url)
        chara_img = drawer.resize_crop(chara_img, chara_img_bg.size)
        chara_img = drawer.mask_image_with_image(chara_img, chara_img_bg)
        chara_img_bg.alpha_composite(chara_img)
        card.alpha_composite(chara_img_bg)

        top_layer = drawer.open_asset("top_layer.png")
        card.alpha_composite(top_layer, (268, 19))

        return card

    def _draw_agent_card(self, agent: ZZZFullAgent) -> Image.Image:
        im = self._draw_card(
            image_url=self._agent_images[agent.id],
            blob_color=Drawer.hex_to_rgb(self._agent_colors[agent.id]),
        )
        drawer = Drawer(
            ImageDraw.Draw(im), folder="zzz-team-card", dark_mode=self._dark_mode, sans=True
        )

        # Agent long name
        name_data = self._name_datas.get(agent.id)
        if name_data is not None:
            text_im = self._render_rotated_text(drawer, name_data)
            offset = {
                1251: -10  # Qingyi
            }
            im.alpha_composite(text_im, (188 + offset.get(agent.id, 0), 9))

        # Agent level and rank
        text = f"Lv.{agent.level} M{agent.rank}"
        drawer.write(
            text,
            size=32,
            position=(12, 267),
            style="black_italic",
            stroke_color=WHITE,
            stroke_width=3,
        )

        # Stats
        self._draw_stats(agent, im, drawer)

        # W-engine
        if agent.w_engine is not None:
            self._draw_w_engine(agent, im, drawer)

        # Skill levels
        self._draw_skill_levels(agent, drawer)

        # Disc drives
        self._draw_disc_drives(agent, im, drawer)

        return im

    def _draw_disc_drives(self, agent: ZZZFullAgent, im: Image.Image, drawer: Drawer) -> None:
        start_pos = (926, 21)
        y_diff = 94
        disc_mask = drawer.open_asset("disc_mask.png")
        disc_num_flair = drawer.open_asset("disc_num_flair.png")

        for i in range(6):
            try:
                disc = next(d for d in agent.discs if d.position == i + 1)
            except StopIteration:
                pass
            else:
                icon = drawer.open_static(self._disc_icons[disc.id])
                icon = drawer.resize_crop(icon, disc_mask.size)
                icon = drawer.mask_image_with_image(icon, disc_mask)
                im.alpha_composite(icon, start_pos)

                im.alpha_composite(disc_num_flair, (start_pos[0], start_pos[1] + 61))
                drawer.write(
                    str(i + 1),
                    size=12,
                    position=(start_pos[0] + 8, start_pos[1] + 70),
                    style="medium",
                    anchor="mm",
                    color=(107, 107, 107),
                )

                main_stat = disc.main_properties[0]
                if isinstance(main_stat.type, PropType):
                    icon = drawer.open_asset(
                        f"stat_icons/{STAT_ICONS[main_stat.type]}",
                        folder="zzz-build-card",
                        size=(16, 16),
                    )
                else:
                    icon = drawer.open_asset(
                        "stat_icons/PLACEHOLDER.png", folder="zzz-build-card", size=(16, 16)
                    )

                im.alpha_composite(icon, (start_pos[0] + 65, start_pos[1] + 6))
                text = main_stat.value
                drawer.write(
                    text,
                    size=14,
                    position=(start_pos[0] + 65 + 20, icon.height // 2 + start_pos[1] + 6),
                    style="bold",
                    anchor="lm",
                )

                text = f"+{disc.level}"
                drawer.write(
                    text,
                    size=12,
                    position=(start_pos[0] + 167, start_pos[1] + 14),
                    style="medium",
                    anchor="mm",
                    color=WHITE,
                )

                stat_start_pos = (start_pos[0] + 65, start_pos[1] + 30)
                for j in range(4):
                    try:
                        stat = disc.properties[j]
                    except IndexError:
                        pass
                    else:
                        color = (
                            drawer.get_agent_special_stat_color(self._agent_colors[agent.id])
                            if self._hl_special_stats[agent.id]
                            and int(stat.type) in self._agent_hl_substat_map[agent.id]
                            else (20, 20, 20)
                        )

                        if isinstance(stat.type, PropType):
                            stat_icon = drawer.open_asset(
                                f"stat_icons/{STAT_ICONS[stat.type]}",
                                folder="zzz-build-card",
                                size=(16, 16),
                                mask_color=color,
                            )
                        else:
                            stat_icon = drawer.open_asset(
                                "stat_icons/PLACEHOLDER.png", folder="zzz-build-card", size=(16, 16)
                            )
                        im.alpha_composite(stat_icon, stat_start_pos)

                        text = stat.value
                        drawer.write(
                            text,
                            size=12,
                            position=(stat_start_pos[0] + 20, icon.height // 2 + stat_start_pos[1]),
                            style="bold",
                            anchor="lm",
                            color=color,
                        )

                        if self._show_substat_rolls[agent.id]:
                            roll_num = get_disc_substat_roll_num(disc.rarity, stat)
                            roll_num_img = drawer.open_asset(
                                f"rolls/{roll_num}.png",
                                size=(55, 1),
                                folder="zzz-build-card",
                                mask_color=color,
                            )
                            im.alpha_composite(
                                roll_num_img, (stat_start_pos[0], stat_start_pos[1] + 18)
                            )

                    if j == 1:
                        stat_start_pos = (start_pos[0] + 65 + 60, start_pos[1] + 30)
                    else:
                        stat_start_pos = (stat_start_pos[0], stat_start_pos[1] + 25)

            start_pos = (1132, 21) if i == 2 else (start_pos[0], start_pos[1] + y_diff)

    def _draw_skill_levels(self, agent: ZZZFullAgent, drawer: Drawer) -> None:
        start_pos = (669, 214)
        for i, skill_type in enumerate(SKILL_ORDER):
            skill = dutils.get(agent.skills, type=skill_type)
            if skill is None:
                continue

            text = (
                ZZZ_AGENT_CORE_LEVEL_MAP[skill.level]
                if skill_type is ZZZSkillType.CORE_SKILL
                else str(skill.level)
            )
            drawer.write(text, size=26, position=start_pos, style="bold", anchor="mm")
            start_pos = (669, 214 + 53) if i == 2 else (start_pos[0] + 99, start_pos[1])

    def _draw_w_engine(self, agent: ZZZFullAgent, im: Image.Image, drawer: Drawer) -> None:
        engine = agent.w_engine
        assert engine is not None

        icon = drawer.open_static(engine.icon, size=(107, 107))
        im.alpha_composite(icon, (777, 50))

        text = engine.name.upper()
        drawer.write(
            text,
            size=22,
            position=(621, 30),
            style="black_italic",
            max_width=158,
            max_lines=2,
            locale=Locale(self._locale),
        )

        stats = (engine.main_properties[0], engine.properties[0])
        start_pos = (621, 100)
        y_diff = 35
        for stat in stats:
            if not isinstance(stat.type, PropType):
                continue
            icon = drawer.open_asset(
                f"stat_icons/{STAT_ICONS[stat.type]}", folder="zzz-build-card", size=(23, 23)
            )
            im.alpha_composite(icon, start_pos)
            text = stat.value
            drawer.write(
                text,
                size=20,
                position=(start_pos[0] + 30, start_pos[1] + icon.height // 2),
                anchor="lm",
            )
            start_pos = (start_pos[0], start_pos[1] + y_diff)

        engine_rank = drawer.open_asset("engine_rank.png")
        im.alpha_composite(engine_rank, (785, 58))
        engine_level = drawer.open_asset("engine_level.png")
        im.alpha_composite(engine_level, (822, 129))

        text = str(engine.refinement)
        drawer.write(
            text, size=16, position=(796, 69), anchor="mm", style="bold_italic", color=WHITE
        )
        text = f"Lv.{engine.level}"
        drawer.write(
            text, size=16, position=(849, 140), anchor="mm", style="bold_italic", color=WHITE
        )

    def _draw_stats(self, agent: ZZZFullAgent, im: Image.Image, drawer: Drawer) -> None:
        props = get_props(agent)
        start_pos = (299, 31)
        agent_color = self._agent_colors[agent.id]

        for i, prop in enumerate(props):
            if prop is None or not isinstance(prop.type, PropType):
                continue

            color = (
                drawer.get_agent_special_stat_color(agent_color)
                if (
                    prop.type.value in self._agent_special_stat_map.get(str(agent.id), [])
                    and self._hl_special_stats[agent.id]
                )
                else (20, 20, 20)
            )

            prop_icon = drawer.open_asset(
                f"stat_icons/{STAT_ICONS[prop.type]}",
                folder="zzz-build-card",
                size=(25, 25),
                mask_color=color,
            )
            im.alpha_composite(prop_icon, start_pos)
            text = prop.final or prop.value
            drawer.write(
                text,
                size=19,
                position=(
                    start_pos[0] + prop_icon.width + 10,
                    start_pos[1] + prop_icon.height // 2,
                ),
                color=color,
                anchor="lm",
                style="bold",
            )

            start_pos = (
                (299, start_pos[1] + 44) if i % 2 != 0 else (start_pos[0] + 134, start_pos[1])
            )

    def _render_rotated_text(self, drawer: Drawer, name_data: AgentNameData) -> Image.Image:
        text = name_data.full_name.upper()
        textbbox = drawer.write(
            text, size=42, position=(0, 0), style="black_italic", no_write=True, anchor="lt"
        )
        if text == "..." or textbbox.width > 280:
            text = name_data.short_name.upper()
            textbbox = drawer.write(
                text, size=42, position=(0, 0), style="black_italic", no_write=True, anchor="lt"
            )
        text_im = Image.new(
            "RGBA", (textbbox.right - textbbox.left, textbbox.bottom - textbbox.top)
        )
        text_drawer = Drawer(
            ImageDraw.Draw(text_im), folder="zzz-team-card", dark_mode=self._dark_mode, sans=True
        )
        text_drawer.write(
            text, size=42, position=(0, 0), style="black_italic", color=BLACK, anchor="lt"
        )
        return text_im.rotate(-90, expand=True, resample=Image.Resampling.BICUBIC)

    def draw(self) -> BytesIO:
        im = Drawer.open_image("hoyo-buddy-assets/assets/zzz-team-card/background.png")
        if len(self._agents) == 2:
            im = im.crop((0, 0, im.width, im.height - 349))

        start_pos = (54, 48)
        y_diff = 347
        for agent in self._agents:
            agent_im = self._draw_agent_card(agent)
            im.paste(agent_im, start_pos, agent_im)
            start_pos = (start_pos[0], start_pos[1] + y_diff)

        if len(self._agents) == 1:
            # Template 3
            im = im.crop((54, 48, 1395, 357))

        return Drawer.save_image(im)
