from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.clients.ambr import ItemCategory
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.db import FarmNotify
    from hoyo_buddy.types import AutocompleteChoices, Interaction

    from .view import RemindersView  # ruff:ignore[unused-import]


def get_farm_item_names(
    item_ids: list[str], *, autofill: AutocompleteChoices, locale: Locale
) -> list[str]:
    names: dict[str, str] = {}
    for category in (ItemCategory.CHARACTERS, ItemCategory.WEAPONS):
        choices = autofill[Game.GENSHIN][category]
        for choice in choices.get(locale) or choices.get(Locale.american_english, []):
            names[choice.value] = choice.name
    return [names.get(item_id, item_id) for item_id in item_ids]


class FarmNotifyToggle(ui.ToggleButton["RemindersView"]):
    def __init__(self, farm_notify: FarmNotify) -> None:
        super().__init__(farm_notify.enabled, LocaleStr(key="reminder_toggle"))
        self.farm_notify = farm_notify

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.farm_notify.enabled = self.current_toggle
        await self.farm_notify.save(update_fields=("enabled",))


class FarmReminderContainer(ui.DefaultContainer["RemindersView"]):
    def __init__(self, *, farm_notify: FarmNotify, item_names: list[str]) -> None:
        # Strings with subcommand mentions can't be nested in another LocaleStr,
        # the outer translation would mangle the already-resolved mention
        if item_names:
            items = (
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="{items}", items="\n".join(f"- {name}" for name in item_names)
                    )
                ),
                ui.TextDisplay(LocaleStr(key="farm_notify.add_item.embed.description")),
                ui.TextDisplay(LocaleStr(key="farm_notify.remove_item.embed.description")),
            )
        else:
            items = (
                ui.TextDisplay(
                    LocaleStr(custom_str="### {title}", title=LocaleStr(key="farm_notify.empty"))
                ),
                ui.TextDisplay(LocaleStr(key="farm_notify.empty_description")),
            )

        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="farm_reminder_title"),
                    desc=LocaleStr(key="farm_notify.description"),
                )
            ),
            ui.ActionRow(FarmNotifyToggle(farm_notify)),
            discord.ui.Separator(visible=True, spacing=discord.SeparatorSpacing.small),
            *items,
        )
