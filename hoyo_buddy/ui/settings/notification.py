from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui
from hoyo_buddy.db.models.notif_settings import AccountNotifSettings
from hoyo_buddy.l10n import LocaleStr

from ._common import AccountToggleButton

if TYPE_CHECKING:
    from hoyo_buddy.db.models.hoyo_account import HoyoAccount
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401


class DisableAllNotificationsButton(ui.Button["SettingsView"]):
    def __init__(self) -> None:
        label = LocaleStr(key="disable_all_button_label")
        super().__init__(style=discord.ButtonStyle.red, label=label)

    async def callback(self, i: Interaction) -> None:
        for field in AccountNotifSettings.ALL_FIELDS:
            setattr(self.view.account.notif_settings, field, False)
        await self.view.account.notif_settings.save()

        await self.view.update(i)


class NotificationSettingsContainer(ui.DefaultContainer["SettingsView"]):
    def __init__(self, *, account: HoyoAccount) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}\n-# {note}",
                    title=LocaleStr(key="notification_settings_button_label"),
                    desc=LocaleStr(key="notification_settings_desc"),
                    note=LocaleStr(key="notification_settings_note"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Auto check-in notifications
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}", title=LocaleStr(key="auto_checkin_button_label")
                )
            ),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_success_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.notify_on_checkin_success",
                    current=account.notif_settings.notify_on_checkin_success,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_failure_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.notify_on_checkin_failure",
                    current=account.notif_settings.notify_on_checkin_failure,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Auto redeem notifications
            ui.TextDisplay(
                LocaleStr(custom_str="### {title}", title=LocaleStr(key="auto_redeem_toggle.label"))
            ),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_success_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.notify_on_checkin_success",
                    current=account.notif_settings.notify_on_checkin_success,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_failure_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.notify_on_checkin_failure",
                    current=account.notif_settings.notify_on_checkin_failure,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.ActionRow(DisableAllNotificationsButton()),
        )


class MimoNotificationSettingsContainer(ui.DefaultContainer["SettingsView"]):
    def __init__(self, *, account: HoyoAccount) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}\n-# {note}",
                    title=LocaleStr(key="mimo_notification_settings"),
                    desc=LocaleStr(key="notification_settings_desc"),
                    note=LocaleStr(key="notification_settings_note"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Auto task notifications
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}",
                    title=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
                )
            ),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_success_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.mimo_task_success",
                    current=account.notif_settings.mimo_task_success,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_failure_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.mimo_task_failure",
                    current=account.notif_settings.mimo_task_failure,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Auto buy notifications
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}", title=LocaleStr(key="mimo_auto_buy_button_label")
                )
            ),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_success_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.mimo_buy_success",
                    current=account.notif_settings.mimo_buy_success,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_failure_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.mimo_buy_failure",
                    current=account.notif_settings.mimo_buy_failure,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Auto draw notifications
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}", title=LocaleStr(key="mimo_auto_draw_button_label")
                )
            ),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_success_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.mimo_draw_success",
                    current=account.notif_settings.mimo_draw_success,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            ui.Section(
                ui.TextDisplay(LocaleStr(key="notify_on_failure_button_label")),
                accessory=AccountToggleButton(
                    attr="notif_settings.mimo_draw_failure",
                    current=account.notif_settings.mimo_draw_failure,
                ),
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.ActionRow(DisableAllNotificationsButton()),
        )
