from typing import Any, Dict, List, Optional, Union

import discord
from discord import Interaction

from hoyo_buddy.bot import Translator
from hoyo_buddy.bot import locale_str as _T

from ...bot.bot import HoyoBuddy
from ...db.models import Settings
from ...embeds import DefaultEmbed
from ..ui import Select, SelectOption, ToggleButton, View

LOCALE_NAMES: Dict[discord.Locale, str] = {
    discord.Locale.american_english: "English (US)",
    discord.Locale.chinese: "简体中文",
    discord.Locale.taiwan_chinese: "繁體中文",
    discord.Locale.french: "Français",
    discord.Locale.japanese: "日本語",
    discord.Locale.brazil_portuguese: "Português (BR)",
    discord.Locale.indonesian: "Bahasa Indonesia",
}

LOCALE_FLAG_EMOJIS: Dict[discord.Locale, str] = {
    discord.Locale.american_english: "🇺🇸",
    discord.Locale.chinese: "🇨🇳",
    discord.Locale.taiwan_chinese: "🇹🇼",
    discord.Locale.french: "🇫🇷",
    discord.Locale.japanese: "🇯🇵",
    discord.Locale.brazil_portuguese: "🇧🇷",
    discord.Locale.indonesian: "🇮🇩",
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
        try:
            return discord.File(
                f"hoyo_buddy/draw/static/brand/{theme}-{locale.value.replace('-','_')}.png",
                filename="brand.png",
            )
        except FileNotFoundError:
            return discord.File(
                f"hoyo_buddy/draw/static/brand/{theme}-en_US.png",
                filename="brand.png",
            )


class LanguageSelector(Select):
    def __init__(self, current_locale: Optional[discord.Locale]):
        options = self._get_options(current_locale)
        super().__init__(options=options)

    @staticmethod
    def _get_options(current_locale: Optional[discord.Locale]) -> List[SelectOption]:
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
                    label=_T(LOCALE_NAMES[locale], translate=False),
                    value=locale.value,
                    emoji=LOCALE_FLAG_EMOJIS[locale],
                    default=locale == current_locale,
                )
                for locale in LOCALE_NAMES
            ]
        )
        return options

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: SettingsUI
        selected = self.values[0]
        self.view.settings.lang = None if selected == "auto" else self.values[0]
        self.options = self._get_options(self.view.settings.locale)

        await i.response.edit_message(
            embed=self.view.get_embed(),
            attachments=[self.view.get_brand_image_file(i.locale)],
            view=self.view,
        )
        await self.view.settings.save()


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
        await i.edit_original_response(
            embed=self.view.get_embed(),
            attachments=[self.view.get_brand_image_file(i.locale)],
        )
        await self.view.settings.save()
