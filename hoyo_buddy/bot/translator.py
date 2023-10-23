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
    def __init__(self) -> None:
        super().__init__()
        self.not_translated: Set[str] = set()

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
        await asyncio.to_thread(tx.fetch_translations)

    def translate(
        self,
        string: str,
        locale: Locale,
        **kwargs,
    ) -> str:
        lang = locale.value.replace("-", "_")
        if "<NO_TRANSLATE>" in string:
            return string.replace("<NO_TRANSLATE>", "")
        translation = tx.translate(string, lang, params=None if kwargs else kwargs)
        if translation is None:
            self.not_translated.add(string)
            return string
        return translation

    async def unload(self) -> None:
        if self.not_translated:
            log.info("Pushing source strings to Transifex...")
            log.info("Strings not translated: %s", self.not_translated)
            await asyncio.to_thread(
                tx.push_source_strings,
                [SourceString(string) for string in self.not_translated],
            )


class AppCommandTranslator(app_commands.Translator):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.translator = translator

    async def translate(
        self, string: locale_str, locale: Locale, _: TranslationContextTypes
    ) -> str:
        return self.translator.translate(string.message, locale, **string.extras)
