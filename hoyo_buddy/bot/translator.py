from __future__ import annotations

import asyncio
import contextlib
import os
import re
import time
from typing import TYPE_CHECKING, Any

from discord import app_commands
from loguru import logger
from seria.utils import read_json, split_list_to_chunks
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractErrorPolicy, AbstractRenderingPolicy

from ..enums import GenshinElement, HSRElement
from ..utils import capitalize_first_word as capitalize_first_word_
from ..utils import convert_to_title_case

if TYPE_CHECKING:
    from types import TracebackType

    from ambr.models import Character as GenshinCharacter
    from discord.app_commands.translator import TranslationContextTypes
    from discord.enums import Locale
    from hakushin.models.gi import Character as HakushinCharacter
    from yatta.models import Character as HSRCharacter

__all__ = ("AppCommandTranslator", "LocaleStr", "Translator")

COMMAND_REGEX = r"</[^>]+>"


class LocaleStr:
    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        warn_no_key: bool = True,
        translate: bool = True,
        **kwargs: Any,
    ) -> None:
        self.message = message
        self.key = key
        self.warn_no_key = warn_no_key
        self.translate_ = translate
        self.extras: dict[str, Any] = kwargs

    def __repr__(self) -> str:
        return f"locale_str({self.message!r}, key={self.key!r}, extras={self.extras!r})"

    def to_app_command_locale_str(self) -> app_commands.locale_str:
        return app_commands.locale_str(
            self.message,
            key=self.key,
            warn_no_key=self.warn_no_key,
            translate=self.translate_,
            **self.extras,
        )

    def translate(self, translator: Translator, locale: Locale) -> str:
        return translator.translate(self, locale)


class CustomMisisngPolicy(AbstractRenderingPolicy):
    @staticmethod
    def get(_: str) -> None:
        return None


class CustomErrorPolicy(AbstractErrorPolicy):
    @staticmethod
    def get(source_string, translation, language_code, escape, params) -> str:  # noqa: ANN001, ARG004
        return source_string


class Translator:
    def __init__(self, env: str) -> None:
        super().__init__()

        self._env = env
        self._not_translated: dict[str, str] = {}
        self._synced_commands: dict[str, int] = {}

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
        # Commented out languages don't have translations yet
        init(
            token=os.environ["TRANSIFEX_TOKEN"],
            secret=os.environ["TRANSIFEX_SECRET"],
            languages=(
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
            ),
            missing_policy=CustomMisisngPolicy(),
            error_policy=CustomErrorPolicy(),
        )
        await self.load_synced_commands_json()

        if self._env in {"prod", "test"}:
            await self.fetch_source_strings()

        logger.info("Translator loaded")

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
            # it's intentional that we don't apply any modifiers when string is not LocaleStr
            return string

        extras = self._translate_extras(string.extras, locale)
        message = string.message
        message = self._replace_command_with_mentions(message)

        string_key = self._get_string_key(string)

        if string.translate_ and self._env != "dev":
            # Check if the string is missing or has different values
            source_string = tx.translate(
                message, "en_US", _key=string_key, escape=False, params=extras
            )

            if source_string is None and string_key not in self._not_translated:
                self._not_translated[string_key] = message
                logger.info(
                    f"String {string_key!r} is missing on Transifex, added to not_translated"
                )
            elif (
                source_string is not None
                and source_string.lower() != message.format(**extras).lower()
                and string_key not in self._not_translated
            ):
                self._not_translated[string_key] = message
                logger.info(
                    f"String {string_key!r} has different values (CDS vs Local): {source_string!r} and {message.format(**extras)!r}, added to not_translated"
                )

        lang = locale.value.replace("-", "_")

        if (
            "en" in lang
            or not string.translate_
            or self._env == "dev"
            or string_key in self._not_translated
        ):
            translation = message
        else:
            translation = tx.translate(message, lang, _key=string_key, escape=False, params=extras)
            translation = translation or message

        with contextlib.suppress(KeyError):
            translation = translation.format(**extras)

        if title_case:
            translation = convert_to_title_case(translation)
        elif capitalize_first_word:
            translation = capitalize_first_word_(translation)
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
            if string.warn_no_key:
                logger.warning(f"Missing key for string {string.message!r}, using generated key")
            string_key = (
                string.message.replace(" ", "_")
                .replace(",", "")
                .replace(".", "")
                .replace("-", "_")
                .lower()
            )
        else:
            string_key = string.key
        return string_key

    @staticmethod
    async def fetch_source_strings() -> None:
        logger.info("Fetching translations...")
        start = time.time()
        await asyncio.to_thread(tx.fetch_translations)
        logger.info("Fetched translations in %.2f seconds", time.time() - start)

    async def push_source_strings(self) -> None:
        if not self._not_translated:
            return

        logger.info("Pushing %d source strings to Transifex", len(self._not_translated))
        split_source_strings = split_list_to_chunks(
            [SourceString(string, _key=key) for key, string in self._not_translated.items()],
            5,
        )
        for source_strings in split_source_strings:
            await asyncio.to_thread(
                tx.push_source_strings, source_strings, do_not_keep_translations=True
            )

        self._not_translated.clear()

    def get_traveler_name(
        self,
        character: GenshinCharacter | HakushinCharacter,
        locale: Locale,
        *,
        gender_symbol: bool = True,
    ) -> str:
        element_str = self.translate(
            LocaleStr(
                GenshinElement(character.element.name.lower()).value.title(), warn_no_key=False
            ),
            locale,
        )
        gender_str = ("♂" if "5" in character.id else "♀") if gender_symbol else ""
        return (
            f"{character.name} ({element_str}) ({gender_str})"
            if gender_str
            else f"{character.name} ({element_str})"
        )

    def get_trailblazer_name(
        self, character: HSRCharacter, locale: Locale, *, gender_symbol: bool = True
    ) -> str:
        element_str = self.translate(
            LocaleStr(
                HSRElement(character.types.combat_type.lower()).value.title(), warn_no_key=False
            ),
            locale,
        )
        gender_str = ("♂" if character.id % 2 != 0 else "♀") if gender_symbol else ""
        return (
            f"{character.name} ({element_str}) ({gender_str})"
            if gender_str
            else f"{character.name} ({element_str})"
        )

    async def unload(self) -> None:
        if self._not_translated and self._env in {"prod", "test"}:
            await self.push_source_strings()
        logger.info("Translator unloaded")


class AppCommandTranslator(app_commands.Translator):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.translator = translator

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: Locale,
        _: TranslationContextTypes,
    ) -> str:
        locale_str_ = LocaleStr(string.message, **string.extras)
        if not locale_str_.translate_:
            return locale_str_.message
        return self.translator.translate(locale_str_, locale)
