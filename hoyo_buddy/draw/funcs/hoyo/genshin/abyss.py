from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import genshin


class SpiralAbyssCard:
    def __init__(
        self,
        data: genshin.models.SpiralAbyss,
        *,
        locale: str,
        character_icons: dict[str, str],
        character_ranks: dict[int, int],
    ) -> None:
        self._data = data
        self._locale = locale
        self._character_icons = character_icons
        self._character_ranks = character_ranks

        self.drawer: Drawer = None  # pyright: ignore[reportAttributeAccessIssue]
        self.im: Image.Image = None  # pyright: ignore[reportAttributeAccessIssue]

    def write_title(self) -> None:
        self.drawer.write(LocaleStr(key="abyss.overview"), size=154, style="bold", position=(3026, 188), anchor="rm")

    def write_damage_info(self) -> None:
        self.drawer.write(LocaleStr(key="abyss.damage"), size=82, style="bold", position=(193, 295), anchor="lm")

        try:
            damage_info: tuple[tuple[str, genshin.models.AbyssRankCharacter], ...] = (
                ("max_rout_count", self._data.ranks.most_kills[0]),
                ("powerful_attack", self._data.ranks.strongest_strike[0]),
                ("max_take_damage", self._data.ranks.most_damage_taken[0]),
                ("element_break_count", self._data.ranks.most_bursts_used[0]),
                ("element_skill_use_count", self._data.ranks.most_skills_used[0]),
            )
        except IndexError:
            return

        for i, (key, character) in enumerate(damage_info):
            position = (193, 381 + 108 * i)
            icon = self.drawer.open_static(self._character_icons[str(character.id)])
            icon = self.drawer.circular_crop(self.drawer.resize_crop(icon, (95, 88)))
            self.im.alpha_composite(icon, position)
            self.drawer.write(
                LocaleStr(key=key, mi18n_game=Game.GENSHIN, append=f": {character.value}"),
                size=48,
                position=(position[0] + icon.width + 23, position[1] + icon.width // 2),
                anchor="lm",
            )

    def write_stats(self) -> None:
        self.drawer.write(LocaleStr(key="abyss.stats"), size=82, style="bold", position=(2957, 460), anchor="rm")

        stats: tuple[LocaleStr | str, ...] = (
            f"{self._data.start_time.strftime("%Y/%m/%d")} ~ {self._data.end_time.strftime("%Y/%m/%d")}",
            LocaleStr(key="abyss.battles_won_fought", val1=self._data.total_wins, val2=self._data.total_battles),
            LocaleStr(key="abyss.deepest_descent", val=self._data.max_floor),
            LocaleStr(key="abyss.total_stars", val=self._data.total_stars),
        )

        for i, stat in enumerate(stats):
            self.drawer.write(stat, size=48, position=(2957, 540 + 110 * i), anchor="rt")

    def draw_character_block(self, character: genshin.models.AbyssCharacter | None) -> Image.Image:
        if character is None:
            return self.drawer.open_asset("block/placeholder.png")

        bk = self.drawer.open_asset(f"block/{character.rarity}_bk.png")
        flair = self.drawer.open_asset(f"block/{character.rarity}_flair.png")
        img = self.drawer.open_asset(f"block/{character.rarity}_img.png")
        img_mask = self.drawer.open_asset("block/img_mask.png")

        bk_drawer = Drawer(ImageDraw.Draw(bk), folder="abyss", dark_mode=True, locale=Locale(self._locale))

        icon = self.drawer.open_static(self._character_icons[str(character.id)], size=(116, 116))
        icon = self.drawer.mask_image_with_image(icon, img_mask)
        bk.alpha_composite(img, (0, 0))
        bk.alpha_composite(icon, (0, 0))

        rank = self._character_ranks.get(character.id, "?")
        bk.alpha_composite(flair, (87, 0))
        bk_drawer.write(f"C{rank}", size=18, style="bold", position=(102, 16), anchor="mm")
        bk_drawer.write(f"Lv.{character.level}", size=24, style="bold", position=(58, 132), anchor="mm")

        return bk

    def draw_floors(self) -> None:
        floor_pos: dict[int, tuple[int, int]] = {0: (193, 1143), 1: (1727, 1143), 2: (193, 2053), 3: (1727, 2053)}
        first_floor = self._data.floors[0]

        for f in range(2 if len(self._data.floors) <= 2 else 4):
            position = floor_pos[f]

            floor_num = f + first_floor.floor if len(self._data.floors) <= 2 else f + 9
            floor = next((floor for floor in self._data.floors if floor.floor == floor_num), None)

            self.drawer.write(
                LocaleStr(key="abyss.floor", val=floor_num),
                size=82,
                style="bold",
                position=(position[0], position[1] + 56),
                anchor="lm",
            )
            cleared = floor_num <= int(self._data.max_floor.split("-")[0])

            stars = (9 if cleared else 0) if floor is None else floor.stars
            self.drawer.write(
                f"{stars}/9", size=64, style="medium", position=(position[0] + 1132, position[1] + 56), anchor="lm"
            )

            for c in range(3):
                try:
                    chamber = floor.chambers[c] if floor is not None else None
                except IndexError:
                    chamber = None

                chamber_stars = (3 if cleared else 0) if chamber is None else chamber.stars

                self.drawer.write(
                    str(chamber_stars),
                    size=48,
                    style="medium",
                    position=(position[0] + 590, position[1] + 221 + 191 * c),
                    anchor="mm",
                )

                for b in range(2):
                    try:
                        battle = chamber.battles[b] if chamber is not None else None
                    except IndexError:
                        battle = None

                    for ch in range(4):
                        try:
                            character = battle.characters[ch] if battle is not None else None
                        except IndexError:
                            character = None

                        block = self.draw_character_block(character)
                        self.im.alpha_composite(
                            block, (position[0] + 8 + 696 * b + 132 * ch, position[1] + 147 + 191 * c)
                        )

    def draw(self) -> BytesIO:
        path = "abyss_bg.png" if len(self._data.floors) > 2 else "abyss_bg_2_floors.png"
        self.im = im = Drawer.open_image(f"hoyo-buddy-assets/assets/abyss/{path}")
        self.drawer = Drawer(ImageDraw.Draw(im), folder="abyss", dark_mode=True, locale=Locale(self._locale))

        self.write_title()
        self.write_damage_info()
        self.write_stats()
        self.draw_floors()

        buf = BytesIO()
        im.save(buf, format="PNG")
        return buf
