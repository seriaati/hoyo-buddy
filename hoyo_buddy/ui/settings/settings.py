from typing import Any, Dict, List, Optional, Union

import discord
from discord import Interaction

from hoyo_buddy.bot import Translator
from hoyo_buddy.bot import locale_str as _T

from ...bot.bot import HoyoBuddy
from ...db.models import Settings
from ...embeds import DefaultEmbed
from ..ui import Select, SelectOption, ToggleButton, View

LOCALES: Dict[discord.Locale, Dict[str, str]] = {
    discord.Locale.american_english: {"name": "English (US)", "emoji": "🇺🇸"},
    discord.Locale.chinese: {"name": "简体中文", "emoji": "🇨🇳"},
    discord.Locale.taiwan_chinese: {"name": "繁體中文", "emoji": "🇹🇼"},
    discord.Locale.french: {"name": "Français", "emoji": "🇫🇷"},
    discord.Locale.japanese: {"name": "日本語", "emoji": "🇯🇵"},
    discord.Locale.brazil_portuguese: {"name": "Português (BR)", "emoji": "🇧🇷"},
    discord.Locale.indonesian: {"name": "Bahasa Indonesia", "emoji": "🇮🇩"},
}


class SettingsUI(View):
    def __init__(
        self,
        *,
        author: Union[discord.User, discord.Member],
        locale: discord.Locale,
        translator: Translator,
        settings: Settings,
    ):
        super().__init__(author=author, locale=locale, translator=translator)
        self.settings = settings

        self.add_item(LanguageSelector(self.settings.locale))
        self.add_item(DarkModeToggle(self.settings.dark_mode))

    def get_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator)
        embed.set_image(url="attachment://brand.png")
        return embed

    def get_brand_image_file(self, interaction_locale: discord.Locale) -> discord.File:
        theme = "DARK" if self.settings.dark_mode else "LIGHT"
        locale = self.settings.locale or interaction_locale
        filename = self._get_filename(theme, locale)
        return discord.File(filename, filename="brand.png")

    def _get_filename(self, theme: str, locale: discord.Locale) -> str:
        try:
            return f"hoyo_buddy/draw/static/brand/{theme}-{locale.value.replace('-','_')}.png"
        except FileNotFoundError:
            return f"hoyo_buddy/draw/static/brand/{theme}-en_US.png"

    async def _update_and_save(self, i: Interaction[HoyoBuddy]):
        await i.edit_original_response(
            embed=self.get_embed(),
            attachments=[self.get_brand_image_file(i.locale)],
        )
        await self.settings.save()


class LanguageSelector(Select):
    def __init__(self, current_locale: Optional[discord.Locale]):
        options = self._get_options(current_locale)
        super().__init__(options=options)

    def _get_options(
        self, current_locale: Optional[discord.Locale]
    ) -> List[SelectOption]:
        options: List[SelectOption] = [
            SelectOption(
                label=_T("Follow client language", key="auto_locale_option_label"),
                value="auto",
                emoji="🏳️",
                default=not current_locale,
            )
        ]
        options.extend(
            [
                SelectOption(
                    label=_T(LOCALES[locale]["name"], translate=False),
                    value=locale.value,
                    emoji=LOCALES[locale]["emoji"],
                    default=locale == current_locale,
                )
                for locale in LOCALES
            ]
        )
        return options

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: SettingsUI
        selected = self.values[0]
        self.view.settings.lang = None if selected == "auto" else self.values[0]
        self.options = self._get_options(self.view.settings.locale)

        await self.view._update_and_save(i)


class DarkModeToggle(ToggleButton):
    def __init__(self, current_toggle: bool):
        super().__init__(
            current_toggle,
            _T("Dark mode", key="dark_mode_button_label"),
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: SettingsUI
        await super().callback(i)
        self.view.settings.dark_mode = self.current_toggle

        await self.view._update_and_save(i)
