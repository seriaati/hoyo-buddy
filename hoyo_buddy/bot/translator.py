import asyncio
import logging
import os
from typing import Dict

from discord import app_commands
from discord.app_commands.translator import TranslationContextTypes, locale_str
from discord.enums import Locale
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractRenderingPolicy

from ..utils import split_list

log = logging.getLogger(__name__)


class CustomRenderingPolicy(AbstractRenderingPolicy):
    @staticmethod
    def get(_: str) -> None:
        return None


class Translator:
    def __init__(self, env: str) -> None:
        super().__init__()
        self.not_translated: Dict[str, str] = {}
        self.env = env

    async def load(self) -> None:
        init(
            token=os.environ["TRANSIFEX_TOKEN"],
            secret=os.environ["TRANSIFEX_SECRET"],
            languages=(
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

    def translate(
        self,
        string: locale_str,
        locale: Locale,
    ) -> str:
        extras = string.extras
        message = string.message

        generated_translation = message.format(**extras)
        if not extras.get("translate", True):
            return generated_translation

        string_key = extras.pop("key", None)
        if string_key is None:
            if extras.get("warn_no_key", True):
                log.warning("Missing key for string %r, using generated key", message)
            string_key = (
                message.replace(" ", "_")
                .replace(",", "")
                .replace(".", "")
                .replace("-", "_")
                .lower()
            )

        lang = locale.value.replace("-", "_")
        translation = tx.translate(
            message,
            lang,
            params=extras,
            _key=string_key,
        )
        if translation is None and string_key is not None:
            existing = self.not_translated.get(string_key)
            if existing is not None and existing != message:
                log.warning(
                    "String %r has different values: %r and %r",
                    string_key,
                    existing,
                    message,
                )

            self.not_translated[string_key] = message
            if self.env == "dev":
                return f"<MT> {generated_translation}"

            return generated_translation
        return translation

    async def fetch_source_strings(self) -> None:
        log.info("Fetching translations...")
        start = asyncio.get_running_loop().time()
        await asyncio.to_thread(tx.fetch_translations)
        log.info(
            "Fetched translations in %.2f seconds",
            asyncio.get_running_loop().time() - start,
        )

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
        self, string: locale_str, locale: Locale, _: TranslationContextTypes
    ) -> str:
        return self.translator.translate(string, locale)
