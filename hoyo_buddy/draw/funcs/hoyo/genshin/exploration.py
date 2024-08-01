from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.draw.drawer import Drawer
from hoyo_buddy.l10n import LevelStr, LocaleStr, Translator

if TYPE_CHECKING:
    from genshin.models import Exploration, PartialGenshinUserStats


class ExplorationCard:
    def __init__(
        self,
        user: PartialGenshinUserStats,
        dark_mode: bool,
        locale: str,
        translator: Translator,
    ) -> None:
        self._user = user
        self._dark_mode = dark_mode
        self._translator = translator
        self._locale = locale
        self._placeholder = "? ? ?"

    @property
    def locale(self) -> Locale:
        return Locale(self._locale)

    def _get_card(self, name: str) -> Image.Image:
        return self._drawer.open_asset(f"{name}_{'dark' if self._dark_mode else 'light'}.png")

    def _get_shadow(self, name: str) -> Image.Image:
        return self._drawer.open_asset(f"{name}_shadow.png")

    def _write_title(
        self, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(
            text,
            position=position,
            size=48,
            style="medium",
        )

    def _write_small_text(
        self, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(
            text,
            position=position,
            size=26,
            style="regular",
            anchor="lm",
        )

    def _get_exploration(self, exploration_id: int) -> Exploration | None:
        return next((e for e in self._user.explorations if e.id == exploration_id), None)

    def _get_offering_text(self, exploration: Exploration | None) -> str:
        level_str = LevelStr(
            0 if exploration is None else exploration.offerings[0].level
        ).translate(self._translator, self.locale)
        if exploration is None:
            return f"{self._placeholder}: {level_str}"
        return f"{exploration.offerings[0].name}: {level_str}"

    def _draw_waypoint_card(self) -> Image.Image:
        im = self._get_card("waypoint")
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=self._dark_mode,
            locale=self._drawer.locale,
            translator=self._drawer.translator,
        )
        self._write_title(
            LocaleStr(key="exploration.waypoints"),
            position=(35, 20),
            drawer=drawer,
        )

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
            translator=self._drawer.translator,
        )
        self._write_title(
            LocaleStr(key="exploration.chests"),
            position=(21, 20),
            drawer=drawer,
        )

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
            translator=self._drawer.translator,
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
                key="exploration.anemoculi",
                anemoculi=self._user.stats.anemoculi,
            ): (75, 207),
            LocaleStr(
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[0].level,
            ): (75, 253),
        }
        im = self._draw_exploration_card("mondstadt", exploration, texts)
        return im

    def _draw_liyue_card(self) -> Image.Image:
        exploration = self._get_exploration(2)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 161),
            LocaleStr(
                key="exploration.geoculi",
                geoculi=self._user.stats.geoculi,
            ): (75, 207),
            LocaleStr(
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[0].level,
            ): (75, 253),
        }
        im = self._draw_exploration_card("liyue", exploration, texts)
        return im

    def _draw_inazuma_card(self) -> Image.Image:
        exploration = self._get_exploration(4)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="exploration.electroculi",
                electroculi=self._user.stats.electroculi,
            ): (75, 163),
            LocaleStr(
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[1].level,
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        im = self._draw_exploration_card("inazuma", exploration, texts)
        return im

    def _draw_sumeru_card(self) -> Image.Image:
        exploration = self._get_exploration(8)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="exploration.dendroculi",
                dendroculi=self._user.stats.dendroculi,
            ): (75, 163),
            LocaleStr(
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[1].level,
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        im = self._draw_exploration_card("sumeru", exploration, texts)
        return im

    def _draw_fontaine_card(self) -> Image.Image:
        exploration = self._get_exploration(9)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                key="exploration.hydroculi",
                hydroculi=self._user.stats.hydroculi,
            ): (75, 163),
            LocaleStr(
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[1].level,
            ): (75, 209),
            self._get_offering_text(exploration): (75, 252),
        }
        im = self._draw_exploration_card("fontaine", exploration, texts)
        return im

    def _draw_placeholder_card(self) -> Image.Image:
        im = self._get_card("placeholder")
        draw = ImageDraw.Draw(im)
        drawer = Drawer(
            draw,
            folder="gi-exploration",
            dark_mode=self._dark_mode,
            locale=self.locale,
            translator=self._translator,
        )
        self._write_title(self._placeholder, position=(34, 23), drawer=drawer)
        self._write_small_text(
            LocaleStr(key="exploration.placeholder"),
            position=(35, 113),
            drawer=drawer,
        )
        self._write_small_text(
            LocaleStr(key="exploration.placeholder_quote"),
            position=(34, 181),
            drawer=drawer,
        )
        return im

    def _draw_sea_of_bygone_eras_card(self) -> Image.Image:
        exploration = self._get_exploration(14)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
        }
        im = self._draw_exploration_card("seaOfBygoneEras", exploration, texts)
        return im

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

        im = self._draw_exploration_card("chenyuVale", exploration, texts)
        return im

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

        im = self._draw_exploration_card("theChasm", exploration, texts)
        return im

    def _draw_dragonspine_card(self) -> Image.Image:
        exploration = self._get_exploration(3)
        texts = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (73, 120),
            self._get_offering_text(exploration): (73, 184),
        }
        im = self._draw_exploration_card("dragonspine", exploration, texts)
        return im

    def _draw_enkanomiya_card(self) -> Image.Image:
        exploration = self._get_exploration(5)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (73, 123),
        }
        im = self._draw_exploration_card("enkanomiya", exploration, texts)
        return im

    def draw(self) -> BytesIO:
        mode_str = "dark" if self._dark_mode else "light"
        self._im = Drawer.open_image(f"hoyo-buddy-assets/assets/gi-exploration/background_{mode_str}.png")
        draw = ImageDraw.Draw(self._im)
        self._drawer = Drawer(
            draw,
            folder="gi-exploration",
            dark_mode=self._dark_mode,
            locale=self.locale,
            translator=self._translator,
        )

        self._drawer.write(
            LocaleStr(key="exploration.title"),
            position=(114, 81),
            size=72,
            style="bold",
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

        sea_of_bygone_eras = self._draw_sea_of_bygone_eras_card()
        shadow = self._get_shadow("seaOfBygoneEras")
        self._im.paste(shadow, (868 - shadow_offset, 1183 - shadow_offset), shadow)
        self._im.paste(sea_of_bygone_eras, (868, 1183), sea_of_bygone_eras)

        # placeholder = self._draw_placeholder_card()
        # shadow = self._get_shadow("placeholder")
        # self._im.paste(shadow, (868 - shadow_offset, 1183 - shadow_offset), shadow)
        # self._im.paste(placeholder, (868, 1183), placeholder)

        chenyu_vale = self._draw_chenyu_value_card()
        shadow = self._get_shadow("chenyuVale")
        self._im.paste(shadow, (114 - shadow_offset, 1533 - shadow_offset), shadow)
        self._im.paste(chenyu_vale, (114, 1533), chenyu_vale)

        chasm = self._draw_the_chasm_card()
        shadow = self._get_shadow("theChasm")
        self._im.paste(shadow, (868 - shadow_offset, 1533 - shadow_offset), shadow)
        self._im.paste(chasm, (868, 1533), chasm)

        dragonspine = self._draw_dragonspine_card()
        shadow = self._get_shadow("dragonspine")
        self._im.paste(shadow, (114 - shadow_offset, 1884 - shadow_offset), shadow)
        self._im.paste(dragonspine, (114, 1884), dragonspine)

        enka = self._draw_enkanomiya_card()
        shadow = self._get_shadow("enkanomiya")
        self._im.paste(shadow, (868 - shadow_offset, 1884 - shadow_offset), shadow)
        self._im.paste(enka, (868, 1884), enka)

        buffer = BytesIO()
        self._im.save(buffer, format="WEBP", loseless=True)
        return buffer
