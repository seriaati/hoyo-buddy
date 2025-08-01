from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import LevelStr, LocaleStr

if TYPE_CHECKING:
    from io import BytesIO

    from genshin.models import Exploration, PartialGenshinUserStats


class ExplorationCard:
    def __init__(self, user: PartialGenshinUserStats, dark_mode: bool, locale: str) -> None:
        self._user = user
        self._dark_mode = dark_mode

        self._locale = locale
        self._placeholder = "? ? ?"

    @property
    def locale(self) -> Locale:
        return Locale(self._locale)

    @staticmethod
    def _get_reputation_level(exploration: Exploration | None) -> str:
        return str(0 if exploration is None else exploration.level)

    @staticmethod
    def _get_tribe_levels(exploration: Exploration | None) -> str:
        if exploration is None or exploration.natlan_reputation is None:
            return "0"
        return "/".join(f"Lv.{t.level}" for t in exploration.natlan_reputation.tribes)

    def _get_card(self, name: str) -> Image.Image:
        return self._drawer.open_asset(f"{name}_{'dark' if self._dark_mode else 'light'}.png")

    def _get_shadow(self, name: str) -> Image.Image:
        return self._drawer.open_asset(f"{name}_shadow.png")

    def _write_title(
        self, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(text, position=position, size=48, style="medium")

    def _write_small_text(
        self, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(text, position=position, size=26, style="regular", anchor="lm")

    def _get_exploration(self, exploration_id: int) -> Exploration | None:
        return next((e for e in self._user.explorations if e.id == exploration_id), None)

    def _get_offering_text(self, exploration: Exploration | None) -> str:
        if exploration is None or not exploration.offerings:
            offering_name = self._placeholder
            level = 0
        else:
            offering = exploration.offerings[0]
            offering_name = offering.name
            level = offering.level

        level_str = LevelStr(level).translate(self.locale)
        return f"{offering_name}: {level_str}"

    def _draw_waypoint_card(self) -> Image.Image:
        im = self._get_card("waypoint")
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=self._dark_mode,
            locale=self._drawer.locale,
        )
        self._write_title(LocaleStr(key="exploration.waypoints"), position=(35, 20), drawer=drawer)

        texts: dict[str, tuple[int, int]] = {
            str(self._user.stats.unlocked_waypoints): (75, 193),
            str(self._user.stats.unlocked_domains): (200, 193),
        }
        for text, pos in texts.items():
            drawer.write(
                text,
                position=pos,
                size=24,
                style="regular",
                anchor="mm",
                locale=Locale.american_english,
            )

        return im

    def _draw_chest_card(self) -> Image.Image:
        im = self._get_card("chest")
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=self._dark_mode,
            locale=self._drawer.locale,
        )
        self._write_title(LocaleStr(key="exploration.chests"), position=(21, 20), drawer=drawer)

        chest_types: dict[LocaleStr, tuple[int, int]] = {
            LocaleStr(key="exploration.common_chests"): (78, 167),
            LocaleStr(key="exploration.exquisite_chests"): (210, 167),
            LocaleStr(key="exploration.precious_chests"): (343, 167),
            LocaleStr(key="exploration.luxurious_chests"): (476, 167),
            LocaleStr(key="exploration.remarkable_chests"): (611, 167),
        }
        chest_nums: dict[int, tuple[int, int]] = {
            self._user.stats.common_chests: (79, 196),
            self._user.stats.exquisite_chests: (210, 196),
            self._user.stats.precious_chests: (343, 196),
            self._user.stats.luxurious_chests: (476, 196),
            self._user.stats.remarkable_chests: (610, 196),
        }
        for text, pos in chest_types.items():
            drawer.write(
                text,
                position=pos,
                size=18,
                style="light",
                anchor="mm",
                locale=Locale.american_english,
            )
        for text, pos in chest_nums.items():
            drawer.write(
                str(text),
                position=pos,
                size=24,
                style="regular",
                anchor="mm",
                locale=Locale.american_english,
            )

        return im

    def _draw_exploration_card(
        self,
        name: str,
        exploration: Exploration | None,
        texts: dict[LocaleStr | str, tuple[int, int]],
    ) -> Image.Image:
        im = self._get_card(name)
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=self._dark_mode,
            locale=self._drawer.locale,
        )
        self._write_title(
            self._placeholder if exploration is None else exploration.name,
            position=(34, 23),
            drawer=drawer,
        )
        for text, pos in texts.items():
            self._write_small_text(text, position=pos, drawer=drawer)

        return im

    def _draw_mondstadt_card(self) -> Image.Image:
        exploration = self._get_exploration(1)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 161),
            LocaleStr(
                key="wind_god", mi18n_game=Game.GENSHIN, append=f": {self._user.stats.anemoculi}"
            ): (75, 207),
            LocaleStr(
                key="reputation_level",
                mi18n_game=Game.GENSHIN,
                append=self._get_reputation_level(exploration),
            ): (75, 253),
        }
        return self._draw_exploration_card("mondstadt", exploration, texts)

    def _draw_liyue_card(self) -> Image.Image:
        exploration = self._get_exploration(2)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 161),
            LocaleStr(
                key="geoculus", mi18n_game=Game.GENSHIN, append=f": {self._user.stats.geoculi}"
            ): (75, 207),
            LocaleStr(
                key="reputation_level",
                mi18n_game=Game.GENSHIN,
                append=self._get_reputation_level(exploration),
            ): (75, 253),
        }
        return self._draw_exploration_card("liyue", exploration, texts)

    def _draw_inazuma_card(self) -> Image.Image:
        exploration = self._get_exploration(4)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="electroculus",
                mi18n_game=Game.GENSHIN,
                append=f": {self._user.stats.electroculi}",
            ): (75, 163),
            LocaleStr(
                key="reputation_level",
                mi18n_game=Game.GENSHIN,
                append=self._get_reputation_level(exploration),
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        return self._draw_exploration_card("inazuma", exploration, texts)

    def _draw_sumeru_card(self) -> Image.Image:
        exploration = self._get_exploration(8)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="dendro_culus",
                mi18n_game=Game.GENSHIN,
                append=f": {self._user.stats.dendroculi}",
            ): (75, 163),
            LocaleStr(
                key="reputation_level",
                mi18n_game=Game.GENSHIN,
                append=self._get_reputation_level(exploration),
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        return self._draw_exploration_card("sumeru", exploration, texts)

    def _draw_fontaine_card(self) -> Image.Image:
        exploration = self._get_exploration(9)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="hydro_god", mi18n_game=Game.GENSHIN, append=f": {self._user.stats.hydroculi}"
            ): (75, 163),
            LocaleStr(
                key="reputation_level",
                mi18n_game=Game.GENSHIN,
                append=self._get_reputation_level(exploration),
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        return self._draw_exploration_card("fontaine", exploration, texts)

    def _draw_placeholder_card(self) -> Image.Image:
        im = self._get_card("placeholder")
        draw = ImageDraw.Draw(im)
        drawer = Drawer(
            draw, folder="gi-exploration", dark_mode=self._dark_mode, locale=self.locale
        )
        self._write_title(self._placeholder, position=(34, 23), drawer=drawer)
        self._write_small_text(
            LocaleStr(key="exploration.placeholder"), position=(35, 113), drawer=drawer
        )
        self._write_small_text(
            LocaleStr(key="exploration.placeholder_quote"), position=(34, 181), drawer=drawer
        )
        return im

    def _draw_sea_of_bygone_eras_card(self) -> Image.Image:
        exploration = self._get_exploration(14)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117)
        }
        return self._draw_exploration_card("seaOfBygoneEras", exploration, texts)

    def _draw_chenyu_value_card(self) -> Image.Image:
        exploration = self._get_exploration(10)
        upper_vale = self._get_exploration(13)
        south_mountain = self._get_exploration(12)
        mt_laxing = self._get_exploration(11)

        areas = (upper_vale, south_mountain, mt_laxing)
        texts: dict[LocaleStr | str, tuple[int, int]] = {}
        for i, area in enumerate(areas):
            name = self._placeholder if area is None else area.name
            progress = 0 if area is None else area.explored
            key = f"{name}: {progress}%"
            if key in texts:
                key = f"{name}: {progress}% "  # sus fix to avoid duplicate key

            texts[key] = (65, 134 + 45 * i)
        texts.update({self._get_offering_text(exploration): (65, 271)})

        return self._draw_exploration_card("chenyuVale", exploration, texts)

    def _draw_the_chasm_card(self) -> Image.Image:
        exploration = self._get_exploration(6)
        underground = self._get_exploration(7)

        underground_name = self._placeholder if underground is None else underground.name
        underground_progress = 0 if underground is None else underground.explored

        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (65, 152),
            f"{underground_name}: {underground_progress}%": (65, 212),
            self._get_offering_text(exploration): (65, 272),
        }

        return self._draw_exploration_card("theChasm", exploration, texts)

    def _draw_dragonspine_card(self) -> Image.Image:
        exploration = self._get_exploration(3)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (73, 120),
            self._get_offering_text(exploration): (73, 184),
        }
        return self._draw_exploration_card("dragonspine", exploration, texts)

    def _draw_enkanomiya_card(self) -> Image.Image:
        exploration = self._get_exploration(5)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (73, 123)
        }
        return self._draw_exploration_card("enkanomiya", exploration, texts)

    def _draw_natlan_card(self) -> Image.Image:
        exploration = self._get_exploration(15)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="pyroculus_number",
                mi18n_game=Game.GENSHIN,
                append=f": {self._user.stats.pyroculi}",
            ): (75, 163),
            LocaleStr(
                key="natlan_reputation",
                reputation=self._get_reputation_level(exploration),
                tribes=self._get_tribe_levels(exploration),
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        return self._draw_exploration_card("natlan", exploration, texts)

    def draw(self) -> BytesIO:
        mode_str = "dark" if self._dark_mode else "light"
        self._im = Drawer.open_image(
            f"hoyo-buddy-assets/assets/gi-exploration/background_{mode_str}.png"
        )
        draw = ImageDraw.Draw(self._im)
        self._drawer = Drawer(
            draw, folder="gi-exploration", dark_mode=self._dark_mode, locale=self.locale
        )

        self._drawer.write(
            LocaleStr(key="exploration.title"), position=(114, 81), size=72, style="bold"
        )
        shadow_offset = 5

        waypoint = self._draw_waypoint_card()
        shadow = self._get_shadow("waypoint")
        self._im.paste(shadow, (114 - shadow_offset, 249 - shadow_offset), shadow)
        self._im.paste(waypoint, (114, 249), waypoint)

        chest = self._draw_chest_card()
        shadow = self._get_shadow("chest")
        self._im.paste(shadow, (868 - shadow_offset, 249 - shadow_offset), shadow)
        self._im.paste(chest, (868, 249), chest)

        mondstadt = self._draw_mondstadt_card()
        shadow = self._get_shadow("mondstadt")
        self._im.paste(shadow, (114 - shadow_offset, 547 - shadow_offset), shadow)
        self._im.paste(mondstadt, (114, 547), mondstadt)

        liyue = self._draw_liyue_card()
        shadow = self._get_shadow("liyue")
        self._im.paste(shadow, (868 - shadow_offset, 547 - shadow_offset), shadow)
        self._im.paste(liyue, (868, 547), liyue)

        inazuma = self._draw_inazuma_card()
        shadow = self._get_shadow("inazuma")
        self._im.paste(shadow, (114 - shadow_offset, 865 - shadow_offset), shadow)
        self._im.paste(inazuma, (114, 865), inazuma)

        sumeru = self._draw_sumeru_card()
        shadow = self._get_shadow("sumeru")
        self._im.paste(shadow, (868 - shadow_offset, 865 - shadow_offset), shadow)
        self._im.paste(sumeru, (868, 865), sumeru)

        fontaine = self._draw_fontaine_card()
        shadow = self._get_shadow("fontaine")
        self._im.paste(shadow, (114 - shadow_offset, 1183 - shadow_offset), shadow)
        self._im.paste(fontaine, (114, 1183), fontaine)

        natlan = self._draw_natlan_card()
        shadow = self._get_shadow("natlan")
        self._im.paste(shadow, (868 - shadow_offset, 1183 - shadow_offset), shadow)
        self._im.paste(natlan, (868, 1183), natlan)

        placeholder = self._draw_placeholder_card()
        shadow = self._get_shadow("placeholder")
        self._im.paste(shadow, (114 - shadow_offset, 1501 - shadow_offset), shadow)
        self._im.paste(placeholder, (114, 1501), placeholder)

        sea_of_bygone_eras = self._draw_sea_of_bygone_eras_card()
        shadow = self._get_shadow("seaOfBygoneEras")
        self._im.paste(shadow, (868 - shadow_offset, 1501 - shadow_offset), shadow)
        self._im.paste(sea_of_bygone_eras, (868, 1501), sea_of_bygone_eras)

        chenyu_vale = self._draw_chenyu_value_card()
        shadow = self._get_shadow("chenyuVale")
        self._im.paste(shadow, (114 - shadow_offset, 1819 - shadow_offset), shadow)
        self._im.paste(chenyu_vale, (114, 1819), chenyu_vale)

        chasm = self._draw_the_chasm_card()
        shadow = self._get_shadow("theChasm")
        self._im.paste(shadow, (868 - shadow_offset, 1819 - shadow_offset), shadow)
        self._im.paste(chasm, (868, 1819), chasm)

        dragonspine = self._draw_dragonspine_card()
        shadow = self._get_shadow("dragonspine")
        self._im.paste(shadow, (114 - shadow_offset, 2170 - shadow_offset), shadow)
        self._im.paste(dragonspine, (114, 2170), dragonspine)

        enka = self._draw_enkanomiya_card()
        shadow = self._get_shadow("enkanomiya")
        self._im.paste(shadow, (868 - shadow_offset, 2170 - shadow_offset), shadow)
        self._im.paste(enka, (868, 2170), enka)

        return Drawer.save_image(self._im)
