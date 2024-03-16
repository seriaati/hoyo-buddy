import asyncio
import contextlib
import logging
import os
import re
import time
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

from discord import app_commands
from seria.utils import read_json, split_list_to_chunks
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractRenderingPolicy

from ..enums import GenshinElement, HSRElement

if TYPE_CHECKING:
    from types import TracebackType

    from ambr.models import Character as GenshinCharacter
    from discord.app_commands.translator import TranslationContextTypes
    from discord.enums import Locale
    from yatta.models import Character as HSRCharacter

__all__ = ("Translator", "AppCommandTranslator", "LocaleStr")

LOGGER_ = logging.getLogger(__name__)
COMMAND_REGEX = r"</[^>]+>"


class LocaleStr:
    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        warn_no_key: bool = True,
        translate: bool = True,
        replace_command_mentions: bool = True,
        **kwargs: Any,
    ) -> None:
        self.message = message
        self.key = key
        self.warn_no_key = warn_no_key
        self.translate_ = translate
        self.replace_command_mentions = replace_command_mentions
        self.extras: dict[str, Any] = kwargs

    def __repr__(self) -> str:
        return f"locale_str({self.message!r}, key={self.key!r}, extras={self.extras!r})"

    def to_app_command_locale_str(self) -> app_commands.locale_str:
        return app_commands.locale_str(
            self.message,
            key=self.key,
            warn_no_key=self.warn_no_key,
            translate=self.translate_,
            replace_command_mentions=self.replace_command_mentions,
            **self.extras,
        )

    def translate(self, translator: "Translator", locale: "Locale") -> str:
        return translator.translate(self, locale)


class CustomRenderingPolicy(AbstractRenderingPolicy):
    @staticmethod
    def get(_: str) -> None:
        return None


class Translator:
    def __init__(self, env: str) -> None:
        super().__init__()

        self._env = env
        self._not_translated: dict[str, str] = {}
        self._synced_commands: dict[str, int] = {}

    async def __aenter__(self) -> "Translator":
        await self.load()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: "TracebackType | None",
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
                # "ko",
                "fr",
                # "de",
                "pt_BR",
                # "vi",
                # "ru",
                # "th",
                "id",
                # "es_ES",
            ),
            missing_policy=CustomRenderingPolicy(),
        )
        await self.load_synced_commands_json()

        if self._env in {"prod", "test"}:
            await self.fetch_source_strings()

        LOGGER_.info("Translator loaded")

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
            if command_id is None:
                message = message.replace(command_occurence, f"</{command_name}:0>")
            else:
                message = message.replace(command_occurence, f"</{command_name}:{command_id}>")
        return message

    def translate(self, string: LocaleStr | str, locale: "Locale") -> str:
        if isinstance(string, str):
            return string

        extras = self._translate_extras(string.extras, locale)
        message = string.message

        if string.replace_command_mentions:
            message = self._replace_command_with_mentions(message)

        string_key = self._get_string_key(string)

        source_string = tx.translate(message, "en_US", _key=string_key, escape=False, params=extras)
        if source_string is None and self._env != "dev":
            self._not_translated[string_key] = message
            LOGGER_.warning(
                "String %r is missing on Transifex, added to not_translated", string_key
            )
        elif source_string != message.format(**extras) and self._env != "dev":
            self._not_translated[string_key] = message
            LOGGER_.warning(
                "String %r has different values (CDS vs Local): %r and %r",
                string_key,
                source_string,
                message,
            )

        lang = locale.value.replace("-", "_")

        if "en" in lang or not string.translate_:
            translation = message
        else:
            translation = tx.translate(message, lang, _key=string_key, escape=False, params=extras)
            translation = translation or message

        with contextlib.suppress(KeyError):
            translation = translation.format(**extras)

        return translation

    def _translate_extras(self, extras: dict[str, Any], locale: "Locale") -> dict[str, Any]:
        extras_: dict[str, Any] = {}
        for k, v in extras.items():
            if isinstance(v, LocaleStr):
                extras_[k] = self.translate(v, locale)
            elif isinstance(v, Sequence) and isinstance(v[0], LocaleStr):
                extras_[k] = "/".join([self.translate(i, locale) for i in v])
            else:
                extras_[k] = v
        return extras_

    @staticmethod
    def _get_string_key(string: LocaleStr) -> str:
        if string.key is None:
            if string.warn_no_key:
                LOGGER_.warning("Missing key for string %r, using generated key", string.message)
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
        LOGGER_.info("Fetching translations...")
        start = time.time()
        await asyncio.to_thread(tx.fetch_translations)
        LOGGER_.info("Fetched translations in %.2f seconds", time.time() - start)

    async def push_source_strings(self) -> None:
        if not self._not_translated:
            return

        LOGGER_.info("Pushing %d source strings to Transifex", len(self._not_translated))
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
        self, character: "GenshinCharacter", locale: "Locale", *, gender_symbol: bool = True
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
        self, character: "HSRCharacter", locale: "Locale", *, gender_symbol: bool = True
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
        LOGGER_.info("Translator unloaded")


class AppCommandTranslator(app_commands.Translator):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.translator = translator

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: "Locale",
        _: "TranslationContextTypes",
    ) -> str:
        locale_str_ = LocaleStr(string.message, **string.extras)
        return self.translator.translate(locale_str_, locale)
