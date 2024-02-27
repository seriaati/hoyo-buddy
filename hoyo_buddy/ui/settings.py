from typing import TYPE_CHECKING, Any

import discord

from ..bot.translator import LocaleStr, Translator
from ..db.models import Settings
from ..embeds import DefaultEmbed
from .components import Select, SelectOption, ToggleButton, View

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION

LOCALES: dict[discord.Locale, dict[str, str]] = {
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
        author: discord.User | discord.Member,
        locale: discord.Locale,
        translator: Translator,
        settings: "Settings",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.settings = settings

        self.add_item(LanguageSelector(self.settings.locale))
        self.add_item(DarkModeToggle(self.settings.dark_mode))

    @staticmethod
    def _get_filename(theme: str, locale: discord.Locale) -> str:
        try:
            return f"hoyo-buddy-assets/assets/brand/{theme}-{locale.value.replace('-', '_')}.png"
        except FileNotFoundError:
            return f"hoyo-buddy-assets/assets/brand/{theme}-en_US.png"

    def get_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator)
        embed.set_image(url="attachment://brand.png")
        return embed

    def get_brand_image_file(self, interaction_locale: discord.Locale) -> discord.File:
        theme = "DARK" if self.settings.dark_mode else "LIGHT"
        locale = self.settings.locale or interaction_locale
        filename = self._get_filename(theme, locale)
        return discord.File(filename, filename="brand.png")

    async def update_ui_and_save_settings(self, i: "INTERACTION") -> None:
        self.translate_items()
        await self.absolute_edit(
            i, embed=self.get_embed(), attachments=[self.get_brand_image_file(i.locale)], view=self
        )

        # NOTE: This is a workaround for a bug in tortoise ORM
        await Settings.filter(user_id=i.user.id).update(
            lang=self.settings.lang, dark_mode=self.settings.dark_mode
        )


class LanguageSelector(Select["SettingsUI"]):
    def __init__(self, current_locale: discord.Locale | None) -> None:
        options = self._get_options(current_locale)
        super().__init__(options=options)

    @staticmethod
    def _get_options(current_locale: discord.Locale | None) -> list[SelectOption]:
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr("Follow client language", key="auto_locale_option_label"),
                value="auto",
                emoji="🏳️",
                default=not current_locale,
            )
        ]
        options.extend(
            [
                SelectOption(
                    label=LOCALES[locale]["name"],
                    value=locale.value,
                    emoji=LOCALES[locale]["emoji"],
                    default=locale == current_locale,
                )
                for locale in LOCALES
            ]
        )
        return options

    async def callback(self, i: "INTERACTION") -> Any:
        selected = self.values[0]
        self.view.locale = discord.Locale(selected) if selected != "auto" else i.locale
        self.view.settings.lang = self.values[0] if selected != "auto" else None
        self.options = self._get_options(self.view.settings.locale)

        await self.view.update_ui_and_save_settings(i)


class DarkModeToggle(ToggleButton["SettingsUI"]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Dark mode", key="dark_mode_button_label"),
        )

    async def callback(self, i: "INTERACTION") -> Any:
        await super().callback(i)
        self.view.settings.dark_mode = self.current_toggle

        await self.view.update_ui_and_save_settings(i)
