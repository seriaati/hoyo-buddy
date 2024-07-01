from __future__ import annotations

import contextlib
import pathlib
import re
from typing import TYPE_CHECKING, Any

import ambr
import yatta
from discord import app_commands
from loguru import logger
from seria.utils import read_json, read_yaml

from ..constants import (
    AMBR_ELEMENT_TO_ELEMENT,
    HAKUSHIN_GI_ELEMENT_TO_ELEMENT,
    HAKUSHIN_HSR_ELEMENT_TO_ELEMENT,
    WEEKDAYS,
    YATTA_COMBAT_TYPE_TO_ELEMENT,
)
from ..utils import capitalize_first_word as capitalize_first_word_
from ..utils import convert_to_title_case

if TYPE_CHECKING:
    from enum import StrEnum
    from types import TracebackType

    import hakushin
    from discord.app_commands.translator import TranslationContextTypes
    from discord.enums import Locale


__all__ = ("AppCommandTranslator", "LocaleStr", "Translator")

COMMAND_REGEX = r"</[^>]+>"
SOURCE_LANG = "en_US"
L10N_PATH = pathlib.Path("./l10n")
LANGUAGES = (
    "en_US",
    "zh_CN",
    "zh_TW",
    "ja",
    "fr",
    "pt_BR",
    "id",
    "nl",
    # "de",
    # "ko",
    # "vi",
    # "ru",
    # "th",
    # "es_ES",
    # "hi",
    # "ro",
)


def gen_string_key(string: str) -> str:
    return string.replace(" ", "_").replace(",", "").replace(".", "").replace("-", "_").lower()


class LocaleStr:
    def __init__(
        self,
        *,
        custom_str: str | None = None,
        key: str | None = None,
        translate: bool = True,
        **kwargs: Any,
    ) -> None:
        self.custom_str = custom_str
        self.key = key
        self.translate_ = translate
        self.extras: dict[str, Any] = kwargs

    @property
    def identifier(self) -> str:
        return self.custom_str or self.key or ""

    def translate(self, translator: Translator, locale: Locale) -> str:
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


class Translator:
    def __init__(self) -> None:
        super().__init__()

        self._not_translated: set[str] = set()
        self._synced_commands: dict[str, int] = {}
        self._localizations: dict[str, dict[str, str]] = {}

    async def __aenter__(self) -> Translator:
        await self.load()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.unload()

    async def load(self) -> None:
        await self.load_l10n_files()
        await self.load_synced_commands_json()

        logger.info("Translator loaded")

    async def load_l10n_files(self) -> None:
        for lang in LANGUAGES:
            file_path = L10N_PATH / f"{lang}.yaml"
            if not file_path.exists():
                continue
            self._localizations[lang] = await read_yaml(file_path.as_posix())

    async def unload(self) -> None:
        logger.info("Translator unloaded")

    async def load_synced_commands_json(self) -> None:
        self._synced_commands = await read_json("hoyo_buddy/bot/data/synced_commands.json")

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

        source_string = self._localizations[SOURCE_LANG].get(string_key)
        if string.translate_ and source_string is None and string_key not in self._not_translated:
            self._not_translated.add(string_key)
            logger.error(f"String {string_key!r} is missing in source lang file")

        lang = locale.value.replace("-", "_")
        translation = self._localizations.get(lang, {}).get(string_key)
        translation = translation or source_string or string.custom_str or string_key

        with contextlib.suppress(KeyError):
            translation = translation.format(**extras)

        if title_case:
            translation = convert_to_title_case(translation)
        elif capitalize_first_word:
            translation = capitalize_first_word_(translation)

        translation = self._replace_command_with_mentions(translation)
        return translation

    def _translate_extras(self, extras: dict[str, Any], locale: Locale) -> dict[str, Any]:
        extras_: dict[str, Any] = {}
        for k, v in extras.items():
            if isinstance(v, LocaleStr):
                extras_[k] = self.translate(v, locale)
            elif isinstance(v, list) and isinstance(v[0], LocaleStr):
                extras_[k] = "/".join([self.translate(i, locale) for i in v])
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


class AppCommandTranslator(app_commands.Translator):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.translator = translator

    async def translate(
        self, string: app_commands.locale_str, locale: Locale, _: TranslationContextTypes
    ) -> str:
        if (key := string.extras.get("key")) is None:
            return string.message
        return self.translator.translate(LocaleStr(key=key), locale)
