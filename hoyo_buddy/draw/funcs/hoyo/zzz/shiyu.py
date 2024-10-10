from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import genshin
from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.utils import format_time

if TYPE_CHECKING:
    from collections.abc import Sequence


class ShiyuDefenseCard:
    def __init__(
        self,
        data: genshin.models.ShiyuDefense,
        agent_ranks: dict[int, int],
        uid: int | None,
        *,
        translator: Translator,
        locale: str,
    ) -> None:
        self.data = data
        self.agent_ranks = agent_ranks
        self.uid = uid
        self.translator = translator
        self.locale = Locale(locale)

        self.text_color = (20, 20, 20)
        self.white = (255, 255, 255)

    def get_element(
        self, elements: Sequence[genshin.models.ZZZElementType], index: int
    ) -> genshin.models.ZZZElementType | None:
        try:
            return elements[index]
        except IndexError:
            return None

    def write_stats(self, drawer: Drawer) -> None:
        if self.uid is not None:
            drawer.write(
                f"UID: {self.uid}",
                size=40,
                position=(1970, 3387),
                color=self.text_color,
                style="medium_italic",
            )

        drawer.write(
            LocaleStr(key="shiyu_overview"),
            size=70,
            position=(126, 665),
            color=self.text_color,
            style="bold",
            locale=self.locale,
        )

        ratings = {
            202: self.data.ratings.get("S", 0),
            425: self.data.ratings.get("A", 0),
            643: self.data.ratings.get("B", 0),
        }
        y = 803

        for x, rating_count in ratings.items():
            tbox = drawer.write(
                "x", size=50, position=(x, y), color=self.text_color, style="bold_italic", sans=True
            )
            drawer.write(
                f" {rating_count}",
                size=58,
                position=(tbox.right, y - 5),
                color=self.text_color,
                style="black_italic",
            )

        stats = {
            "shiyu_fastest_clear_time": format_time(self.data.fastest_clear_time),
            "shiyu_highest_frontier": LocaleStr(
                key=f"shiyu_{self.data.max_floor}_frontier"
            ).translate(self.translator, self.locale),
            "shiyu_relevant_season": f"{self.data.begin_time:%Y-%m-%d} ~ {self.data.end_time:%Y-%m-%d}",
        }
        start_pos = (126, 907)

        for title_key, value in stats.items():
            tbox = drawer.write(
                LocaleStr(key=title_key),
                size=44,
                position=start_pos,
                color=self.text_color,
                style="medium_italic",
                locale=self.locale,
            )
            drawer.write(
                value,
                size=55,
                position=(start_pos[0], tbox.bottom + 5),
                color=self.text_color,
                style="bold",
                locale=self.locale,
            )

            start_pos = (126, start_pos[1] + 160)

    def draw_frontiers(self, im: Image.Image, drawer: Drawer) -> None:
        positions = {
            1: (1229, 774),
            2: (126, 1425),
            3: (1229, 1425),
            4: (126, 2076),
            5: (1229, 2076),
            6: (126, 2727),
            7: (1229, 2727),
        }

        for frontier in self.data.floors:
            pos = positions[frontier.index]

            tbox = drawer.write(
                LocaleStr(key=f"shiyu_{frontier.index}_frontier"),
                size=90,
                position=(pos[0], pos[1] + 13),
                color=self.text_color,
                style="bold",
                locale=self.locale,
            )

            elements = (
                self.get_element(frontier.node_1.recommended_elements, 0),
                self.get_element(frontier.node_1.recommended_elements, 1),
                self.get_element(frontier.node_2.recommended_elements, 0),
                self.get_element(frontier.node_2.recommended_elements, 1),
            )
            element_icons = {
                genshin.models.ZZZElementType.ELECTRIC: "Electric.png",
                genshin.models.ZZZElementType.ETHER: "Ether.png",
                genshin.models.ZZZElementType.FIRE: "Fire.png",
                genshin.models.ZZZElementType.ICE: "Ice.png",
                genshin.models.ZZZElementType.PHYSICAL: "Physical.png",
                None: "None.png",
            }
            icon_start_pos = (tbox.right + 34, tbox.top + tbox.height // 2 - 50)

            for i, element in enumerate(elements):
                icon = drawer.open_asset(f"{element_icons[element]}", size=(45, 45))
                im.alpha_composite(icon, icon_start_pos)

                if i == 1:
                    icon_start_pos = (tbox.right + 34, icon_start_pos[1] + icon.height + 10)
                else:
                    icon_start_pos = (icon_start_pos[0] + icon.width + 10, icon_start_pos[1])

            drawer.draw.line(
                (
                    icon_start_pos[0] + 24,
                    icon_start_pos[1] - 55,
                    icon_start_pos[0] + 24,
                    icon_start_pos[1] + 45,
                ),
                fill=self.text_color,
                width=5,
            )

            drawer.write(
                frontier.rating,
                size=110,
                position=(icon_start_pos[0] + 54, tbox.top + tbox.height // 2),
                color=self.text_color,
                style="black_italic",
                anchor="lm",
            )

            bangboo_block = drawer.open_asset("bangboo_block.png")
            bangboo_level_flair = drawer.open_asset("bangboo_level_flair.png")
            bangboo_mask = drawer.open_asset("bangboo_mask.png")

            mask = drawer.open_asset("mask.png")
            level_flair = drawer.open_asset("level_flair.png")
            mind_flair = drawer.open_asset("mind_flair.png")
            block = drawer.open_asset("chara_block.png")

            start_pos = (pos[0], pos[1] + 192)

            for node_index, node in enumerate((frontier.node_1, frontier.node_2)):
                bangboo = node.bangboo
                bangboo_pos = (pos[0] + 795, pos[1] + (252 if node_index == 0 else 476))
                im.alpha_composite(bangboo_block, bangboo_pos)

                bangboo_icon = drawer.open_static(bangboo.icon)
                bangboo_icon = drawer.resize_crop(bangboo_icon, (180, 120))
                bangboo_icon = drawer.mask_image_with_image(bangboo_icon, bangboo_mask)
                im.alpha_composite(bangboo_icon, bangboo_pos)
                im.alpha_composite(bangboo_level_flair, (bangboo_pos[0], bangboo_pos[1] + 86))

                drawer.write(
                    f"Lv.{bangboo.level}",
                    size=28,
                    position=(bangboo_pos[0] + 51, bangboo_pos[1] + 103),
                    color=self.white,
                    style="bold",
                    anchor="mm",
                )

                for i in range(3):
                    try:
                        agent = node.characters[i]
                    except IndexError:
                        agent = None

                    im.alpha_composite(block, start_pos)

                    if agent is not None:
                        agent_icon = drawer.open_static(agent.icon)
                        agent_icon = drawer.resize_crop(agent_icon, (180, 180))
                        agent_icon = drawer.mask_image_with_image(agent_icon, mask)
                        im.alpha_composite(agent_icon, (start_pos[0], start_pos[1]))

                        im.alpha_composite(level_flair, (start_pos[0], start_pos[1] + 146))
                        im.alpha_composite(mind_flair, (start_pos[0] + 135, start_pos[1]))

                        drawer.write(
                            f"Lv.{agent.level}",
                            size=28,
                            position=(start_pos[0] + 51, start_pos[1] + 163),
                            color=self.white,
                            style="bold",
                            anchor="mm",
                        )
                        drawer.write(
                            str(self.agent_ranks.get(agent.id, 0)),
                            size=36,
                            position=(start_pos[0] + 158, start_pos[1] + 22),
                            color=self.white,
                            style="bold",
                            anchor="mm",
                        )

                    start_pos = (start_pos[0] + 265, start_pos[1])

                start_pos = (pos[0], start_pos[1] + 224)

    def draw(self) -> BytesIO:
        im = Drawer.open_image("hoyo-buddy-assets/assets/shiyu/background.png")
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="shiyu",
            dark_mode=False,
            translator=self.translator,
            sans=True,
        )
        self.write_stats(drawer)
        self.draw_frontiers(im, drawer)

        buffer = BytesIO()
        im.save(buffer, format="PNG")
        return buffer
