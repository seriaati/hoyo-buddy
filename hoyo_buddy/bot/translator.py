import asyncio
import logging
import os
from typing import Set

from discord import app_commands
from discord.app_commands.translator import TranslationContextTypes, locale_str
from discord.enums import Locale
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractRenderingPolicy

log = logging.getLogger(__name__)


class CustomRenderingPolicy(AbstractRenderingPolicy):
    def get(self, _: str) -> None:
        return None


class Translator:
    def __init__(self, prod: bool) -> None:
        super().__init__()
        self.not_translated: Set[str] = set()
        self.prod = prod

    async def load(self) -> None:
        init(
            token=os.environ["TRANSIFEX_TOKEN"],
            secret=os.environ["TRANSIFEX_SECRET"],
            languages=(
                "en_US",
                "en_GB",
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

        if self.prod:
            log.info("Fetching translations...")
            start = asyncio.get_running_loop().time()
            await asyncio.to_thread(tx.fetch_translations)
            log.info(
                "Fetched translations in %.2f seconds",
                asyncio.get_running_loop().time() - start,
            )

    def translate(
        self,
        string: str,
        locale: Locale,
        **kwargs,
    ) -> str:
        lang = locale.value.replace("-", "_")
        if "<NO_TRANS>" in string or kwargs.get("no_trans", False):
            return string.replace("<NO_TRANS>", "")
        translation = tx.translate(string, lang, params=None if kwargs else kwargs)
        if translation is None:
            self.not_translated.add(string)
            return string
        return translation

    async def unload(self) -> None:
        if self.not_translated and self.prod:
            log.info("Pushing source strings to Transifex...")
            log.info("Strings not translated: %s", self.not_translated)
            await asyncio.to_thread(
                tx.push_source_strings,
                [SourceString(string) for string in self.not_translated],
            )
        log.info("Translator unloaded")


class AppCommandTranslator(app_commands.Translator):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.translator = translator

    async def translate(
        self, string: locale_str, locale: Locale, _: TranslationContextTypes
    ) -> str:
        return self.translator.translate(string.message, locale, **string.extras)
