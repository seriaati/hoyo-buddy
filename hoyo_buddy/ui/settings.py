from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

import discord

from ..bot.translator import LocaleStr, Translator
from ..constants import HOYO_BUDDY_LOCALES
from ..db.models import Settings
from ..embeds import DefaultEmbed
from .components import Select, SelectOption, ToggleButton, View

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION


class SettingsUI(View):
    def __init__(
        self,
        *,
        author: discord.User | discord.Member,
        locale: discord.Locale,
        translator: Translator,
        settings: Settings,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.settings = settings

        self.add_item(LanguageSelector(self.settings.locale))
        self.add_item(DarkModeToggle(self.settings.dark_mode))

    @staticmethod
    def get_brand_img_filename(theme: str, locale: discord.Locale) -> str:
        filename = f"hoyo-buddy-assets/assets/brand/{theme}-{locale.value.replace('-', '_')}.png"
        if not os.path.exists(filename):
            return f"hoyo-buddy-assets/assets/brand/{theme}-en_US.png"
        return filename

    def get_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator)
        embed.set_image(url="attachment://brand.png")
        return embed

    def get_brand_image_file(self, interaction_locale: discord.Locale) -> discord.File:
        theme = "DARK" if self.settings.dark_mode else "LIGHT"
        locale = self.settings.locale or interaction_locale
        filename = self.get_brand_img_filename(theme, locale)
        return discord.File(filename, filename="brand.png")

    async def update_ui_and_save_settings(self, i: INTERACTION) -> None:
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
                    label=HOYO_BUDDY_LOCALES[locale]["name"],
                    value=locale.value,
                    emoji=HOYO_BUDDY_LOCALES[locale]["emoji"],
                    default=locale == current_locale,
                )
                for locale in HOYO_BUDDY_LOCALES
            ]
        )
        return options

    async def callback(self, i: INTERACTION) -> Any:
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

    async def callback(self, i: INTERACTION) -> Any:
        await super().callback(i)
        self.view.settings.dark_mode = self.current_toggle

        await self.view.update_ui_and_save_settings(i)
