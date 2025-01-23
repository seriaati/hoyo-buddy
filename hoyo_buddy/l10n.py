from __future__ import annotations

import contextlib
import datetime
import pathlib
import random
import re
from asyncio import TaskGroup
from typing import TYPE_CHECKING, Any, Literal, Self, TypeAlias

import aiofiles
import ambr
import genshin
import orjson
import yatta
from discord import app_commands
from loguru import logger
from seria.utils import read_json, read_yaml

from hoyo_buddy.emojis import INFO
from hoyo_buddy.enums import Game

from .constants import (
    AMBR_ELEMENT_TO_ELEMENT,
    GPY_LANG_TO_LOCALE,
    HAKUSHIN_GI_ELEMENT_TO_ELEMENT,
    HAKUSHIN_HSR_ELEMENT_TO_ELEMENT,
    WEEKDAYS,
    YATTA_COMBAT_TYPE_TO_ELEMENT,
    ZENLESS_DATA_LANG_TO_LOCALE,
    ZENLESS_DATA_LANGS,
    get_docs_url,
)
from .utils import capitalize_first_word as capitalize_first_word_
from .utils import convert_to_title_case

if TYPE_CHECKING:
    from enum import StrEnum
    from types import TracebackType

    import hakushin
    from discord.app_commands.translator import TranslationContextTypes
    from discord.enums import Locale


__all__ = ("AppCommandTranslator", "LocaleStr", "Translator")

Mi18nGame: TypeAlias = Literal["mimo"] | Game

COMMAND_REGEX = r"</[^>]+>"
DOCS_REGEX = r":docs/[^:\s]+:"
SOURCE_LANG = "en_US"
L10N_PATH = pathlib.Path("./l10n")
BOT_DATA_PATH = pathlib.Path("./hoyo_buddy/bot/data")
GAME_MI18N_FILES: dict[Mi18nGame, tuple[str, str]] = {
    Game.GENSHIN: ("https://fastcdn.hoyoverse.com/mi18n/bbs_oversea", "m11241040191111"),
    Game.STARRAIL: (
        "https://webstatic.hoyoverse.com/admin/mi18n/bbs_oversea",
        "m20230509hy150knmyo",
    ),
    Game.ZZZ: ("https://fastcdn.hoyoverse.com/mi18n/nap_global", "m20240410hy38foxb7k"),
    Game.HONKAI: ("https://fastcdn.hoyoverse.com/mi18n/bbs_oversea", "m20240627hy298aaccg"),
    "mimo": ("https://webstatic.hoyoverse.com/admin/mi18n/bbs_oversea", "m20230908hy169078qo"),
}
FILENAME_TO_GAME: dict[str, Mi18nGame] = {v[1]: k for k, v in GAME_MI18N_FILES.items()}


def gen_string_key(string: str) -> str:
    return string.replace(" ", "_").replace(",", "").replace(".", "").replace("-", "_").lower()


class LocaleStr:
    def __init__(
        self,
        *,
        custom_str: str | None = None,
        key: str | None = None,
        translate: bool = True,
        mi18n_game: Mi18nGame | None = None,
        data_game: Game | None = None,
        append: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.custom_str = custom_str
        self.key = key
        self.translate_ = translate
        self.append = append
        self.mi18n_game = mi18n_game
        self.game = data_game
        self.extras: dict[str, Any] = kwargs

    @property
    def identifier(self) -> str:
        return self.custom_str or self.key or ""

    def translate(self, locale: Locale) -> str:
        return translator.translate(self, locale)


class EnumStr(LocaleStr):
    def __init__(self, enum: StrEnum) -> None:
        super().__init__(key=gen_string_key(enum.value))


class LevelStr(LocaleStr):
    def __init__(self, level: int) -> None:
        super().__init__(key="level_str", level=level)


class WeekdayStr(LocaleStr):
    def __init__(self, weekday: int) -> None:
        super().__init__(key=WEEKDAYS[weekday].lower())


class TimeRemainingStr(LocaleStr):
    def __init__(self, timedelta: int | datetime.timedelta) -> None:
        if isinstance(timedelta, int):
            timedelta = datetime.timedelta(seconds=timedelta)
        super().__init__(key="time_remaining_str", time=timedelta)


class UnlocksInStr(LocaleStr):
    def __init__(self, timedelta: datetime.timedelta) -> None:
        super().__init__(key="unlocks_in_str", time=timedelta)


class RarityStr(LocaleStr):
    def __init__(self, rarity: int) -> None:
        super().__init__(key="rarity_str", rarity=rarity)


class Translator:
    def __init__(self) -> None:
        super().__init__()

        self._synced_commands: dict[str, int] = {}
        self._l10n: dict[str, dict[str, str]] = {}
        self._mi18n: dict[tuple[str, Mi18nGame], dict[str, str]] = {}
        self._game_textmaps: dict[tuple[str, Game], dict[str, str]] = {}

    async def __aenter__(self) -> Self:
        await self.load()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        pass

    async def load(self) -> None:
        await self.load_l10n_files()
        await self.load_synced_commands_json()
        await self.load_mi18n_files()
        await self.load_game_textmaps()

        logger.info("Translator loaded")

    async def load_l10n_files(self) -> None:
        for file_path in L10N_PATH.glob("*.yaml"):
            if not file_path.exists():
                continue

            lang = file_path.stem
            self._l10n[lang] = await read_yaml(file_path.as_posix())
            logger.info(f"Loaded {lang} lang file")

    async def _fetch_mi18n_task(
        self, client: genshin.Client, *, lang: str, filename: str, url: str
    ) -> None:
        locale = GPY_LANG_TO_LOCALE.get(lang)
        if locale is None:
            logger.warning(f"Failed to convert gpy lang {lang!r} to locale")
            return

        mi18n = await client.fetch_mi18n(url, filename, lang=lang)
        async with aiofiles.open(
            f"{BOT_DATA_PATH}/mi18n_{filename}_{lang}.json", "w", encoding="utf-8"
        ) as f:
            await f.write(orjson.dumps(mi18n).decode())

    async def fetch_mi18n_files(self) -> None:
        client = genshin.Client()

        async with TaskGroup() as tg:
            for file_ in GAME_MI18N_FILES.values():
                url, filename = file_
                for lang in genshin.constants.LANGS:
                    tg.create_task(
                        self._fetch_mi18n_task(client, lang=lang, url=url, filename=filename)
                    )

        logger.info("Fetched mi18n files")

    async def load_mi18n_files(self) -> None:
        for file_path in BOT_DATA_PATH.glob("mi18n_*.json"):
            if not file_path.exists():
                continue

            filename, lang = file_path.stem.split("_")[1:]
            game = FILENAME_TO_GAME[filename]
            self._mi18n[GPY_LANG_TO_LOCALE[lang].value.replace("-", "_"), game] = await read_json(
                file_path.as_posix()
            )
            logger.info(f"Loaded {lang} mi18n file for {game}")

    async def load_game_textmaps(self) -> None:
        # ZZZ
        for lang in ZENLESS_DATA_LANGS:
            self._game_textmaps[
                ZENLESS_DATA_LANG_TO_LOCALE[lang].value.replace("-", "_"), Game.ZZZ
            ] = await read_json(f"{BOT_DATA_PATH}/zzz_text_map_{lang}.json")
        logger.info("Loaded ZZZ game textmaps")

    async def load_synced_commands_json(self) -> None:
        self._synced_commands = await read_json(f"{BOT_DATA_PATH}/synced_commands.json")

    def get_dyks(self, locale: Locale) -> list[tuple[str, bool]]:
        keys: set[str] = set()
        for key in self._l10n[SOURCE_LANG]:
            if key.startswith("dyk_"):
                keys.add(key)

        return [
            (self.translate(LocaleStr(key=key), locale), key.endswith("_no_title")) for key in keys
        ]

    def get_dyk(self, locale: Locale) -> str:
        title = self.translate(LocaleStr(key="title_dyk"), locale)
        dyks = self.get_dyks(locale)
        dyk, no_title = random.choice(dyks)
        if no_title:
            return f"-# {INFO} {dyk}"
        return f"-# {INFO} {title} {dyk}"

    def _replace_command_with_mentions(self, message: str) -> str:
        command_occurences: list[str] = re.findall(COMMAND_REGEX, message)
        for command_occurence in command_occurences:
            command_name = command_occurence[2:-1]
            if " " in command_name:
                # is subcommand
                command_name = command_name.split(" ")[0]
            command_id = self._synced_commands.get(command_name)

            # after geting the command_id, change command_name back to the original command name
            command_name = command_occurence[2:-1]
            if command_id is not None:
                message = message.replace(command_occurence, f"</{command_name}:{command_id}>")
        return message

    def _replace_docs_urls(self, message: str, *, locale: Locale) -> str:
        docs_occurences: list[str] = re.findall(DOCS_REGEX, message)
        for docs_occurence in docs_occurences:
            page = docs_occurence.split("docs/")[-1].split(":")[0]
            message = message.replace(docs_occurence, get_docs_url(page, locale=locale))
        return message

    def translate(
        self,
        string: LocaleStr | str,
        locale: Locale,
        *,
        title_case: bool = False,
        capitalize_first_word: bool = False,
    ) -> str:
        if isinstance(string, str):
            # It's intentional that we don't apply any modifiers when string is not LocaleStr
            return string

        extras = self._translate_extras(string.extras, locale)
        string_key = self._get_string_key(string)

        if string.mi18n_game is not None:
            source_string = self._mi18n[SOURCE_LANG, string.mi18n_game][string_key]  # pyright: ignore[reportArgumentType]
        elif string.game is not None:
            source_string = self._game_textmaps[SOURCE_LANG, string.game][string_key]
        else:
            source_string = self._l10n[SOURCE_LANG].get(string_key)

        if string.translate_ and source_string is None and string.custom_str is None:
            logger.warning(f"String {string_key!r} is missing in source lang file")

        lang = locale.value.replace("-", "_")
        if string.mi18n_game is not None:
            translation = self._mi18n.get((lang, string.mi18n_game), {}).get(string_key)  # pyright: ignore[reportArgumentType, reportCallIssue]
        elif string.game is not None:
            translation = self._game_textmaps.get((lang, string.game), {}).get(string_key)
        else:
            translation = self._l10n.get(lang, {}).get(string_key)

        translation = translation or source_string or string.custom_str or string_key

        with contextlib.suppress(KeyError):
            translation = translation.format(**extras)

        if title_case:
            translation = convert_to_title_case(translation)
        elif capitalize_first_word:
            translation = capitalize_first_word_(translation)

        translation = self._replace_command_with_mentions(translation)
        translation = self._replace_docs_urls(translation, locale=locale)
        if string.append:
            translation += string.append
        return translation

    def _translate_extras(self, extras: dict[str, Any], locale: Locale) -> dict[str, Any]:
        extras_: dict[str, Any] = {}
        for k, v in extras.items():
            if isinstance(v, LocaleStr):
                extras_[k] = self.translate(v, locale)
            elif isinstance(v, list) and isinstance(v[0], LocaleStr):
                extras_[k] = "/".join([self.translate(i, locale) for i in v])
            elif isinstance(v, datetime.timedelta):
                extras_[k] = self.display_timedelta(v, locale)
            else:
                extras_[k] = v
        return extras_

    @staticmethod
    def _get_string_key(string: LocaleStr) -> str:
        if string.key is None:
            if string.custom_str is None:
                msg = "Either key or custom_str must be provided"
                raise ValueError(msg)
            return gen_string_key(string.custom_str)
        return string.key

    def get_traveler_name(
        self,
        character: ambr.Character | hakushin.gi.Character,
        locale: Locale,
        *,
        gender_symbol: bool = True,
    ) -> str:
        if isinstance(character, ambr.Character):
            element = AMBR_ELEMENT_TO_ELEMENT[character.element]
        elif character.element is not None:  # hakushin.gi.Character
            element = HAKUSHIN_GI_ELEMENT_TO_ELEMENT[character.element]
        else:
            element = None

        element_str = "" if element is None else self.translate(EnumStr(element), locale)
        gender_str = ("♂" if "5" in character.id else "♀") if gender_symbol else ""
        return (
            f"{character.name} ({element_str}) ({gender_str})"
            if gender_str
            else f"{character.name} ({element_str})"
        )

    def get_trailblazer_name(
        self,
        character: yatta.Character | hakushin.hsr.Character,
        locale: Locale,
        *,
        gender_symbol: bool = True,
    ) -> str:
        if isinstance(character, yatta.Character):
            element_str = self.translate(
                EnumStr(YATTA_COMBAT_TYPE_TO_ELEMENT[character.types.combat_type]), locale
            )
        else:
            element_str = self.translate(
                EnumStr(HAKUSHIN_HSR_ELEMENT_TO_ELEMENT[character.element]), locale
            )

        # Only gender_str if is trailblazer
        # constants.TRAILBAZER_IDS may contain characters that are not trailblazers (like March 7th)
        gender_str = (
            ("♂" if character.id % 2 != 0 else "♀")
            if gender_symbol and str(character.id)[0] == "8"
            else ""
        )

        return (
            f"{character.name} ({element_str}) ({gender_str})"
            if gender_str
            else f"{character.name} ({element_str})"
        )

    def display_timedelta(self, timedelta: datetime.timedelta, locale: Locale) -> str:
        str_timedelta = str(timedelta)
        return str_timedelta.replace(
            "days", self.translate(LocaleStr(key="days"), locale), 1
        ).replace(", 0:00:00", "")


class AppCommandTranslator(app_commands.Translator):
    async def translate(
        self, string: app_commands.locale_str, locale: Locale, _: TranslationContextTypes
    ) -> str:
        if string.extras.get("key") is None:
            return string.message
        return translator.translate(LocaleStr(**string.extras), locale)


translator = Translator()
