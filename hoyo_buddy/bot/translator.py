import asyncio
import os
from typing import Optional, Set

from discord import app_commands
from discord.app_commands.translator import TranslationContextTypes, locale_str
from discord.enums import Locale
from transifex.native import init, tx
from transifex.native.parsing import SourceString
from transifex.native.rendering import AbstractRenderingPolicy


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
            languages=["en", "zh_CN", "zh_TW", "ja"],
            missing_policy=CustomRenderingPolicy(),
        )
        await asyncio.to_thread(tx.fetch_translations)

    async def translate(
        self,
        string: locale_str,
        locale: Locale,
        _: Optional[TranslationContextTypes] = None,
    ) -> Optional[str]:
        lang = locale.value.replace("-", "_")
        message = string.message
        translation = tx.translate(message, lang, params=string.extras)
        if translation is None:
            self.not_translated.add(message)
        return translation

    async def unload(self) -> None:
        await asyncio.to_thread(
            tx.push_source_strings,
            [SourceString(string) for string in self.not_translated],
        )


class AppCommandTranslator(app_commands.Translator):
    def __init__(self, translator: Translator) -> None:
        super().__init__()
        self.translator = translator

    async def translate(
        self, string: locale_str, locale: Locale, context: TranslationContextTypes
    ) -> Optional[str]:
        return await self.translator.translate(string, locale, context)
