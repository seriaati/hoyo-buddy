import asyncio
import contextlib
import logging
import os
import re
from typing import TYPE_CHECKING, Any

import aiofiles
import orjson
from discord import app_commands
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractRenderingPolicy

from ..utils import split_list

if TYPE_CHECKING:
    from types import TracebackType

    from discord.app_commands.translator import TranslationContextTypes
    from discord.enums import Locale

__all__ = ("Translator", "AppCommandTranslator", "LocaleStr")

log = logging.getLogger(__name__)
COMMAND_REGEX = r"</[a-z]+>"


class LocaleStr:
    def __init__(
        self,
        message: str,
        *,
        key: str | None = None,
        warn_no_key: bool = True,
        translate: bool = True,
        replace_command_mentions: bool = True,
        **kwargs,
    ) -> None:
        self.message = message
        self.key = key
        self.warn_no_key = warn_no_key
        self.translate = translate
        self.replace_command_mentions = replace_command_mentions
        self.extras: dict[str, Any] = kwargs

    def __repr__(self) -> str:
        return f"locale_str({self.message!r}, key={self.key!r}, extras={self.extras!r})"


class CustomRenderingPolicy(AbstractRenderingPolicy):
    @staticmethod
    def get(_: str) -> None:
        return None


class Translator:
    def __init__(self, env: str) -> None:
        super().__init__()
        self.not_translated: dict[str, str] = {}
        self.env = env
        self.synced_commands: dict[str, int] = {}

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
        init(
            token=os.environ["TRANSIFEX_TOKEN"],
            secret=os.environ["TRANSIFEX_SECRET"],
            languages=(
                "en_US",
                "zh_CN",
                "zh_TW",
                "ja",
                "ko",
                "fr",
                "de",
                "pt_BR",
                "vi",
                "ru",
                "th",
                "id",
                "es_ES",
            ),
            missing_policy=CustomRenderingPolicy(),
        )
        await self.load_synced_commands_json()
        log.info("Translator loaded")

        if self.env in {"prod", "test"}:
            await self.fetch_source_strings()

    def replace_command_with_mentions(self, message: str) -> str:
        command_occurences: list[str] = re.findall(COMMAND_REGEX, message)
        for command_occurence in command_occurences:
            command_name = command_occurence[2:-1]
            command_id = self.synced_commands.get(command_name)
            if command_id is None:
                message = message.replace(command_occurence, f"</{command_name}:0>")
            else:
                message = message.replace(command_occurence, f"</{command_name}:{command_id}>")
        return message

    def translate(self, string: LocaleStr | str, locale: "Locale") -> str:
        if isinstance(string, str):
            return string

        log.debug("Translating %r to %s", string, locale.value)

        extras = self._translate_extras(string.extras, locale)
        message = string.message

        if string.replace_command_mentions:
            message = self.replace_command_with_mentions(message)

        generated_translation = self._generate_translation(message, extras)

        if not string.translate:
            return generated_translation

        string_key = self._get_string_key(string)
        lang = locale.value.replace("-", "_")
        is_source = "en" in lang
        translation = None
        with contextlib.suppress(KeyError):
            translation = self._get_translation(message, lang, extras, string_key, is_source)

        if translation is None:
            self._handle_missing_translation(string_key, message)
            return generated_translation

        if is_source and translation != message and not extras:
            self._handle_mismatched_strings(string_key, translation, message)
            return message

        return translation

    def _translate_extras(self, extras: dict, locale: "Locale") -> dict:
        translated_extras = {}
        for k, v in extras.items():
            if isinstance(v, LocaleStr):
                translated_extras[k] = self.translate(v, locale)
            else:
                translated_extras[k] = v
        return translated_extras

    @staticmethod
    def _generate_translation(message: str, extras: dict) -> str:
        try:
            generated_translation = message.format(**extras)
        except ValueError:
            generated_translation = message
        return generated_translation

    @staticmethod
    def _get_string_key(string: LocaleStr) -> str:
        if string.key is None:
            if string.warn_no_key:
                log.warning("Missing key for string %r, using generated key", string.message)
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

    def _get_translation(
        self, message: str, lang: str, extras: dict, string_key: str, is_source: bool
    ) -> str | None:
        translation = tx.translate(
            message,
            lang,
            params=extras,
            _key=string_key,
            escape=False,
            is_source=is_source,
        )
        if translation is None:
            existing = self.not_translated.get(string_key)
            if existing is not None and existing != message:
                log.warning(
                    "String %r has different values: %r and %r",
                    string_key,
                    existing,
                    message,
                )
            self.not_translated[string_key] = message
        return translation

    def _handle_missing_translation(self, string_key: str, message: str) -> None:
        self.not_translated[string_key] = message

    def _handle_mismatched_strings(self, string_key: str, translation: str, message: str) -> None:
        log.info(
            "Local and CDS strings with key %r do not match: %r != %r",
            string_key,
            translation,
            message,
        )
        self.not_translated[string_key] = message

    @staticmethod
    async def fetch_source_strings() -> None:
        log.info("Fetching translations...")
        start = asyncio.get_running_loop().time()
        await asyncio.to_thread(tx.fetch_translations)
        log.info(
            "Fetched translations in %.2f seconds",
            asyncio.get_running_loop().time() - start,
        )

    async def load_synced_commands_json(self) -> None:
        try:
            async with aiofiles.open(
                "hoyo_buddy/bot/data/synced_commands.json", encoding="utf-8"
            ) as f:
                self.synced_commands = orjson.loads(await f.read())
        except FileNotFoundError:
            pass

    async def push_source_strings(self) -> None:
        start = asyncio.get_running_loop().time()
        log.info("Pushing %d source strings to Transifex", len(self.not_translated))
        split_source_strings = split_list(
            [SourceString(string, _key=key) for key, string in self.not_translated.items()],
            5,
        )
        for source_strings in split_source_strings:
            await asyncio.to_thread(
                tx.push_source_strings, source_strings, do_not_keep_translations=True
            )

        self.not_translated.clear()
        log.info(
            "Pushed source strings in %.2f seconds",
            asyncio.get_running_loop().time() - start,
        )

    async def unload(self) -> None:
        if self.not_translated and self.env in {"prod", "test"}:
            await self.push_source_strings()
        log.info("Translator unloaded")


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
