from __future__ import annotations

import pathlib
from typing import TYPE_CHECKING, Any

import discord

from hoyo_buddy.db import Settings
from hoyo_buddy.enums import Locale

from ..constants import HOYO_BUDDY_LOCALES
from ..embeds import DefaultEmbed
from ..l10n import LocaleStr
from .components import Select, SelectOption, ToggleButton, View

if TYPE_CHECKING:
    from ..types import Interaction


class SettingsUI(View):
    def __init__(
        self, *, author: discord.User | discord.Member, locale: Locale, settings: Settings
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.settings = settings

        self.add_item(LanguageSelector(self.settings.locale))
        self.add_item(DarkModeToggle(current_toggle=self.settings.dark_mode))
        self.add_item(DYKTolggle(current_toggle=self.settings.enable_dyk))

    @staticmethod
    def get_brand_img_filename(theme: str, locale: Locale) -> str:
        filename = f"hoyo-buddy-assets/assets/brand/{theme}-{locale.value.replace('-', '_')}.png"
        if not pathlib.Path(filename).exists():
            return f"hoyo-buddy-assets/assets/brand/{theme}-en_US.png"
        return filename

    def get_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale)
        embed.set_image(url="attachment://brand.webp")
        return embed

    def get_brand_image_file(self, interaction_locale: Locale) -> discord.File:
        theme = "DARK" if self.settings.dark_mode else "LIGHT"
        locale = self.settings.locale or interaction_locale
        filename = self.get_brand_img_filename(theme, locale)
        return discord.File(filename, filename="brand.webp")

    async def update_ui_and_save_settings(self, i: Interaction, *, translate: bool = False) -> None:
        if translate:
            self.translate_items()

        await self.absolute_edit(
            i,
            embed=self.get_embed(),
            attachments=[self.get_brand_image_file(self.locale)],
            view=self,
        )

        # Update cache
        await i.client.cache.set(f"{i.user.id}:lang", self.settings.lang)
        await i.client.cache.set(f"{i.user.id}:dyk", self.settings.enable_dyk)

        # NOTE: This is a workaround for a bug in tortoise ORM
        await Settings.filter(user_id=i.user.id).update(
            lang=self.settings.lang,
            dark_mode=self.settings.dark_mode,
            enable_dyk=self.settings.enable_dyk,
        )


class LanguageSelector(Select["SettingsUI"]):
    def __init__(self, current_locale: Locale | None) -> None:
        options = self._get_options(current_locale)
        super().__init__(options=options)

    @staticmethod
    def _get_options(current_locale: Locale | None) -> list[SelectOption]:
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr(key="auto_locale_option_label"),
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

    async def callback(self, i: Interaction) -> Any:
        selected = self.values[0]
        self.view.locale = Locale(selected) if selected != "auto" else Locale(str(i.locale))
        self.view.settings.lang = self.values[0] if selected != "auto" else None
        self.options = self._get_options(self.view.settings.locale)
        self.update_options_defaults()
        await self.view.update_ui_and_save_settings(i, translate=True)


class DarkModeToggle(ToggleButton["SettingsUI"]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="dark_mode_button_label"))

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.settings.dark_mode = self.current_toggle
        await self.view.update_ui_and_save_settings(i)


class DYKTolggle(ToggleButton[SettingsUI]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="button_label_dyk"))

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.settings.enable_dyk = self.current_toggle
        await self.view.update_ui_and_save_settings(i)
