import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from discord import app_commands
from discord.app_commands.translator import TranslationContextTypes
from discord.enums import Locale
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractRenderingPolicy

from ..utils import split_list

__all__ = ("Translator", "AppCommandTranslator", "locale_str")

log = logging.getLogger(__name__)
COMMAND_REGEX = r"</[a-z]+>"


class locale_str:
    def __init__(
        self,
        message: str,
        *,
        key: Optional[str] = None,
        warn_no_key: bool = True,
        translate: bool = True,
        **kwargs,
    ):
        self.message = message
        self.key = key
        self.warn_no_key = warn_no_key
        self.translate = translate
        self.extras: Dict[str, Any] = kwargs


class CustomRenderingPolicy(AbstractRenderingPolicy):
    @staticmethod
    def get(_: str) -> None:
        return None


class Translator:
    def __init__(self, env: str) -> None:
        super().__init__()
        self.not_translated: Dict[str, str] = {}
        self.env = env
        self.synced_commands: Dict[str, int] = {}
        self.load_synced_commands_json()

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
        log.info("Translator loaded")

        if self.env in ("prod", "test"):
            await self.fetch_source_strings()

    def replace_command_with_mentions(self, message: str) -> str:
        command_occurences: List[str] = re.findall(COMMAND_REGEX, message)
        for command_occurence in command_occurences:
            command_id = self.synced_commands.get(command_occurence[2:-1])
            if command_id is None:
                message = message.replace(command_occurence, f"<{command_occurence}:0>")
            else:
                message = message.replace(
                    command_occurence, f"<{command_occurence}:{command_id}>"
                )
        return message

    def translate(
        self,
        string: locale_str,
        locale: Locale,
    ) -> str:
        extras = string.extras
        message = string.message

        message = self.replace_command_with_mentions(message)
        try:
            generated_translation = message.format(**extras)
        except ValueError:
            generated_translation = message

        if not string.translate:
            return generated_translation

        string_key = string.key
        if string_key is None:
            if string.warn_no_key:
                log.warning("Missing key for string %r, using generated key", message)
            string_key = (
                message.replace(" ", "_")
                .replace(",", "")
                .replace(".", "")
                .replace("-", "_")
                .lower()
            )

        if self.env == "dev":
            return f"<MT> {generated_translation}"

        lang = locale.value.replace("-", "_")
        is_source = "en" in lang
        translation: Optional[str] = tx.translate(
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
            return generated_translation

        if is_source and translation != message and not extras:
            log.info(
                "Local and CDS strings with key %r do not match: %r != %r",
                string_key,
                translation,
                message,
            )
            self.not_translated[string_key] = message
            return message

        return translation

    @staticmethod
    async def fetch_source_strings() -> None:
        log.info("Fetching translations...")
        start = asyncio.get_running_loop().time()
        await asyncio.to_thread(tx.fetch_translations)
        log.info(
            "Fetched translations in %.2f seconds",
            asyncio.get_running_loop().time() - start,
        )

    def load_synced_commands_json(self) -> None:
        try:
            with open("hoyo_buddy/bot/data/synced_commands.json") as f:
                self.synced_commands = json.load(f)
        except FileNotFoundError:
            pass

    async def push_source_strings(self) -> None:
        start = asyncio.get_running_loop().time()
        log.info("Pushing %d source strings to Transifex", len(self.not_translated))
        split_source_strings = split_list(
            [
                SourceString(string, _key=key)
                for key, string in self.not_translated.items()
            ],
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
        if self.not_translated and self.env in ("prod", "test"):
            await self.push_source_strings()
        log.info("Translator unloaded")


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
        locale_str_ = locale_str(string.message, **string.extras)
        return self.translator.translate(locale_str_, locale)
