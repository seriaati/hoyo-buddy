from io import BytesIO
from typing import TYPE_CHECKING, ClassVar

from discord import Locale
from PIL import Image, ImageDraw

from hoyo_buddy.bot.translator import LocaleStr, Translator
from hoyo_buddy.draw.drawer import Drawer

if TYPE_CHECKING:
    from genshin.models import Exploration, PartialGenshinUserStats


class ExplorationCard:
    _user: ClassVar["PartialGenshinUserStats"]
    _drawer: ClassVar[Drawer]
    _dark_mode: ClassVar[bool]
    _translator: ClassVar[Translator]
    _locale: ClassVar[Locale]
    _placeholder: ClassVar[str] = "? ? ?"

    @classmethod
    def _get_card(cls, name: str) -> Image.Image:
        return cls._drawer.open_asset(f"{name}_{'dark' if cls._dark_mode else 'light'}.png")

    @classmethod
    def _get_shadow(cls, name: str) -> Image.Image:
        return cls._drawer.open_asset(f"{name}_shadow.png")

    @classmethod
    def _write_title(
        cls, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(
            text,
            position=position,
            size=48,
            style="medium",
        )

    @classmethod
    def _write_small_text(
        cls, text: LocaleStr | str, *, position: tuple[int, int], drawer: Drawer
    ) -> None:
        drawer.write(
            text,
            position=position,
            size=26,
            style="regular",
            anchor="lm",
        )

    @classmethod
    def _get_exploration(cls, exploration_id: int) -> "Exploration | None":
        return next((e for e in cls._user.explorations if e.id == exploration_id), None)

    @classmethod
    def _get_offering_text(cls, exploration: "Exploration | None") -> str:
        level_str = LocaleStr(
            "Lv.{level}",
            key="level_str",
            level=0 if exploration is None else exploration.offerings[0].level,
        ).translate(cls._translator, cls._locale)
        if exploration is None:
            return f"{cls._placeholder}: {level_str}"
        return f"{exploration.offerings[0].name}: {level_str}"

    @classmethod
    def _draw_waypoint_card(cls) -> Image.Image:
        im = cls._get_card("waypoint")
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=cls._dark_mode,
            locale=cls._drawer.locale,
            translator=cls._drawer.translator,
        )
        cls._write_title(
            LocaleStr("Waypoints Unlocked", key="exploration.waypoints"),
            position=(35, 20),
            drawer=drawer,
        )

        texts: dict[str, tuple[int, int]] = {
            str(cls._user.stats.unlocked_waypoints): (75, 193),
            str(cls._user.stats.unlocked_domains): (200, 193),
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

    @classmethod
    def _draw_chest_card(cls) -> Image.Image:
        im = cls._get_card("chest")
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=cls._dark_mode,
            locale=cls._drawer.locale,
            translator=cls._drawer.translator,
        )
        cls._write_title(
            LocaleStr("Chests Unlocked", key="exploration.chests"),
            position=(21, 20),
            drawer=drawer,
        )

        chest_types: dict[LocaleStr, tuple[int, int]] = {
            LocaleStr("Common", key="exploration.common_chests"): (78, 167),
            LocaleStr("Exquisite", key="exploration.exquisite_chests"): (210, 167),
            LocaleStr("Precious", key="exploration.precious_chests"): (343, 167),
            LocaleStr("Luxurious", key="exploration.luxurious_chests"): (476, 167),
            LocaleStr("Remarkable", key="exploration.remarkable_chests"): (611, 167),
        }
        chest_nums: dict[int, tuple[int, int]] = {
            cls._user.stats.common_chests: (79, 196),
            cls._user.stats.exquisite_chests: (210, 196),
            cls._user.stats.precious_chests: (343, 196),
            cls._user.stats.luxurious_chests: (476, 196),
            cls._user.stats.remarkable_chests: (610, 196),
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

    @classmethod
    def _draw_exploration_card(
        cls,
        name: str,
        exploration: "Exploration | None",
        texts: dict[LocaleStr | str, tuple[int, int]],
    ) -> Image.Image:
        im = cls._get_card(name)
        drawer = Drawer(
            ImageDraw.Draw(im),
            folder="gi-exploration",
            dark_mode=cls._dark_mode,
            locale=cls._drawer.locale,
            translator=cls._drawer.translator,
        )
        cls._write_title(
            cls._placeholder if exploration is None else exploration.name,
            position=(34, 23),
            drawer=drawer,
        )
        for text, pos in texts.items():
            cls._write_small_text(text, position=pos, drawer=drawer)

        return im

    @classmethod
    def _draw_mondstadt_card(cls) -> Image.Image:
        exploration = cls._get_exploration(1)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 161),
            LocaleStr(
                "Anemoculi: {anemoculi}",
                key="exploration.anemoculi",
                anemoculi=cls._user.stats.anemoculi,
            ): (75, 207),
            LocaleStr(
                "Reputation: Lv.{reputation}",
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[0].level,
            ): (75, 253),
        }
        im = cls._draw_exploration_card("mondstadt", exploration, texts)
        return im

    @classmethod
    def _draw_liyue_card(cls) -> Image.Image:
        exploration = cls._get_exploration(2)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 161),
            LocaleStr(
                "Geoculi: {geoculi}",
                key="exploration.geoculi",
                geoculi=cls._user.stats.geoculi,
            ): (75, 207),
            LocaleStr(
                "Reputation: Lv.{reputation}",
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[0].level,
            ): (75, 253),
        }
        im = cls._draw_exploration_card("liyue", exploration, texts)
        return im

    @classmethod
    def _draw_inazuma_card(cls) -> Image.Image:
        exploration = cls._get_exploration(4)
        texts = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                "Electroculi: {electroculi}",
                key="exploration.electroculi",
                electroculi=cls._user.stats.electroculi,
            ): (75, 163),
            LocaleStr(
                "Reputation: Lv.{reputation}",
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[1].level,
            ): (75, 209),
            cls._get_offering_text(exploration): (75, 252),
        }
        im = cls._draw_exploration_card("inazuma", exploration, texts)
        return im

    @classmethod
    def _draw_sumeru_card(cls) -> Image.Image:
        exploration = cls._get_exploration(8)
        texts = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                "Electroculi: {electroculi}",
                key="exploration.electroculi",
                electroculi=cls._user.stats.electroculi,
            ): (75, 163),
            LocaleStr(
                "Reputation: Lv.{reputation}",
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[1].level,
            ): (75, 209),
            cls._get_offering_text(exploration): (75, 252),
        }
        im = cls._draw_exploration_card("sumeru", exploration, texts)
        return im

    @classmethod
    def _draw_fontaine_card(cls) -> Image.Image:
        exploration = cls._get_exploration(9)
        texts = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (75, 117),
            LocaleStr(
                "Hydroculi: {hydroculi}",
                key="exploration.hydroculi",
                hydroculi=cls._user.stats.hydroculi,
            ): (75, 163),
            LocaleStr(
                "Reputation: Lv.{reputation}",
                key="exploration.reputation",
                reputation=0 if exploration is None else exploration.offerings[1].level,
            ): (75, 209),
            cls._get_offering_text(exploration): (75, 252),
        }
        im = cls._draw_exploration_card("fontaine", exploration, texts)
        return im

    @classmethod
    def _draw_placeholder_card(cls) -> Image.Image:
        im = cls._get_card("placeholder")
        draw = ImageDraw.Draw(im)
        drawer = Drawer(
            draw,
            folder="gi-exploration",
            dark_mode=cls._dark_mode,
            locale=cls._locale,
            translator=cls._translator,
        )
        cls._write_title(cls._placeholder, position=(34, 23), drawer=drawer)
        cls._write_small_text(
            LocaleStr("Yet to be released", key="exploration.placeholder"),
            position=(35, 113),
            drawer=drawer,
        )
        cls._write_small_text(
            LocaleStr(
                '"Every journey has its final day.Don\'t rush."\n-Zhongli',
                key="exploration.placeholder_quote",
            ),
            position=(34, 181),
            drawer=drawer,
        )
        return im

    @classmethod
    def _draw_chenyu_value_card(cls) -> Image.Image:
        exploration = cls._get_exploration(10)
        upper_vale = cls._get_exploration(13)
        south_mountain = cls._get_exploration(12)
        mt_laxing = cls._get_exploration(11)

        areas = (upper_vale, south_mountain, mt_laxing)
        texts: dict[LocaleStr | str, tuple[int, int]] = {}
        for i, area in enumerate(areas):
            name = cls._placeholder if area is None else area.name
            progress = 0 if area is None else area.explored
            key = f"{name}: {progress}%"
            if key in texts:
                key = f"{name}: {progress}% "  # sus fix to avoid duplicate key

            texts[key] = (65, 134 + 45 * i)
        texts.update({cls._get_offering_text(exploration): (65, 271)})

        im = cls._draw_exploration_card("chenyuVale", exploration, texts)
        return im

    @classmethod
    def _draw_the_chasm_card(cls) -> Image.Image:
        exploration = cls._get_exploration(6)
        underground = cls._get_exploration(7)

        underground_name = cls._placeholder if underground is None else underground.name
        underground_progress = 0 if underground is None else underground.explored

        texts = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (65, 152),
            f"{underground_name}: {underground_progress}%": (65, 212),
            cls._get_offering_text(exploration): (65, 272),
        }

        im = cls._draw_exploration_card("theChasm", exploration, texts)
        return im

    @classmethod
    def _draw_dragonspine_card(cls) -> Image.Image:
        exploration = cls._get_exploration(3)
        texts = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (73, 120),
            cls._get_offering_text(exploration): (73, 184),
        }
        im = cls._draw_exploration_card("dragonspine", exploration, texts)
        return im

    @classmethod
    def _draw_enkanomiya_card(cls) -> Image.Image:
        exploration = cls._get_exploration(5)
        texts: dict[LocaleStr | str, tuple[int, int]] = {
            LocaleStr(
                "Exploration Progress: {progress}%",
                key="exploration.progress",
                progress=0 if exploration is None else exploration.explored,
            ): (73, 123),
        }
        im = cls._draw_exploration_card("enkanomiya", exploration, texts)
        return im

    @classmethod
    def draw(
        cls,
        user: "PartialGenshinUserStats",
        dark_mode: bool,
        locale: Locale,
        translator: Translator,
    ) -> BytesIO:
        im = Image.open(
            f"hoyo-buddy-assets/assets/gi-exploration/background_{'dark' if dark_mode else 'light'}.png"
        )
        draw = ImageDraw.Draw(im)

        cls._user = user
        cls._drawer = Drawer(
            draw, folder="gi-exploration", dark_mode=dark_mode, locale=locale, translator=translator
        )
        cls._dark_mode = dark_mode
        cls._translator = translator
        cls._locale = locale

        cls._drawer.write(
            LocaleStr("World Exploration", key="exploration.title"),
            position=(114, 81),
            size=72,
            style="bold",
        )
        shadow_offset = 5

        waypoint = cls._draw_waypoint_card()
        shadow = cls._get_shadow("waypoint")
        im.paste(shadow, (114 - shadow_offset, 249 - shadow_offset), shadow)
        im.paste(waypoint, (114, 249), waypoint)

        chest = cls._draw_chest_card()
        shadow = cls._get_shadow("chest")
        im.paste(shadow, (868 - shadow_offset, 249 - shadow_offset), shadow)
        im.paste(chest, (868, 249), chest)

        mondstadt = cls._draw_mondstadt_card()
        shadow = cls._get_shadow("mondstadt")
        im.paste(shadow, (114 - shadow_offset, 547 - shadow_offset), shadow)
        im.paste(mondstadt, (114, 547), mondstadt)

        liyue = cls._draw_liyue_card()
        shadow = cls._get_shadow("liyue")
        im.paste(shadow, (868 - shadow_offset, 547 - shadow_offset), shadow)
        im.paste(liyue, (868, 547), liyue)

        inazuma = cls._draw_inazuma_card()
        shadow = cls._get_shadow("inazuma")
        im.paste(shadow, (114 - shadow_offset, 865 - shadow_offset), shadow)
        im.paste(inazuma, (114, 865), inazuma)

        sumeru = cls._draw_sumeru_card()
        shadow = cls._get_shadow("sumeru")
        im.paste(shadow, (868 - shadow_offset, 865 - shadow_offset), shadow)
        im.paste(sumeru, (868, 865), sumeru)

        fontaine = cls._draw_fontaine_card()
        shadow = cls._get_shadow("fontaine")
        im.paste(shadow, (114 - shadow_offset, 1183 - shadow_offset), shadow)
        im.paste(fontaine, (114, 1183), fontaine)

        placeholder = cls._draw_placeholder_card()
        shadow = cls._get_shadow("placeholder")
        im.paste(shadow, (868 - shadow_offset, 1183 - shadow_offset), shadow)
        im.paste(placeholder, (868, 1183), placeholder)

        chenyu_vale = cls._draw_chenyu_value_card()
        shadow = cls._get_shadow("chenyuVale")
        im.paste(shadow, (114 - shadow_offset, 1533 - shadow_offset), shadow)
        im.paste(chenyu_vale, (114, 1533), chenyu_vale)

        chasm = cls._draw_the_chasm_card()
        shadow = cls._get_shadow("theChasm")
        im.paste(shadow, (868 - shadow_offset, 1533 - shadow_offset), shadow)
        im.paste(chasm, (868, 1533), chasm)

        dragonspine = cls._draw_dragonspine_card()
        shadow = cls._get_shadow("dragonspine")
        im.paste(shadow, (114 - shadow_offset, 1884 - shadow_offset), shadow)
        im.paste(dragonspine, (114, 1884), dragonspine)

        enka = cls._draw_enkanomiya_card()
        shadow = cls._get_shadow("enkanomiya")
        im.paste(shadow, (868 - shadow_offset, 1884 - shadow_offset), shadow)
        im.paste(enka, (868, 1884), enka)

        buffer = BytesIO()
        im.save(buffer, format="WEBP", loseless=True)
        return buffer
