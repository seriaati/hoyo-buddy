from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import emojis, ui
from hoyo_buddy.constants import HOYO_BUDDY_LOCALES
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.db.models.settings import Settings
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401


class DarkThemeToggleButton(ui.EmojiToggleButton["SettingsView"]):
    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.settings.dark_mode = self.current
        await self.view.settings.save(update_fields=("dark_mode",))

        await i.response.edit_message(view=self.view)


class DYKTolggle(ui.EmojiToggleButton["SettingsView"]):
    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.settings.enable_dyk = self.current
        await self.view.settings.save(update_fields=("enable_dyk",))

        await i.response.edit_message(view=self.view)


class LanguageSelect(ui.Select["SettingsView"]):
    def __init__(self, current_locale: Locale | None) -> None:
        super().__init__(
            custom_id="language_select",
            placeholder=LocaleStr(key="language_select_placeholder"),
            options=self._get_options(current_locale),
        )

    @staticmethod
    def _get_options(current_locale: Locale | None) -> list[ui.SelectOption]:
        options: list[ui.SelectOption] = [
            ui.SelectOption(
                label=LocaleStr(key="auto_locale_option_label"),
                value="auto",
                emoji="🏳️",
                default=not current_locale,
            )
        ]
        options.extend(
            [
                ui.SelectOption(
                    label=HOYO_BUDDY_LOCALES[locale]["name"],
                    value=locale.value,
                    emoji=HOYO_BUDDY_LOCALES[locale]["emoji"],
                    default=locale == current_locale,
                )
                for locale in HOYO_BUDDY_LOCALES
            ]
        )
        return options

    async def callback(self, i: Interaction) -> None:
        locale = None if self.values[0] == "auto" else Locale(self.values[0])

        self.view.locale = locale or Locale(str(i.locale))
        self.view.settings.lang = locale.value if locale else None
        await self.view.settings.save(update_fields=("lang",))

        self.update_options_defaults()

        await self.view.update(i)


class UserSettingsContainer(ui.DefaultContainer["SettingsView"]):
    def __init__(self, *, settings: Settings) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="user_settings_title"),
                    desc=LocaleStr(key="user_settings_desc"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {desc}",
                        emoji=emojis.DARK_MODE,
                        desc=LocaleStr(key="dark_theme_desc"),
                    )
                ),
                accessory=DarkThemeToggleButton(current=settings.dark_mode),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {emoji} {desc}",
                        emoji=emojis.LIVE_HELP,
                        desc=LocaleStr(key="settings_dyk_desc"),
                    )
                ),
                accessory=DYKTolggle(current=settings.enable_dyk),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {emoji} {desc}",
                    emoji=emojis.LANGUAGE,
                    desc=LocaleStr(key="language_desc"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.ActionRow(LanguageSelect(settings.locale)),
        )
