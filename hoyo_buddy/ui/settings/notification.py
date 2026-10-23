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

    from .view import SettingsView  # ruff:ignore[unused-import]


class DisableAllNotificationsButton(ui.Button["SettingsView"]):
    def __init__(self) -> None:
        label = LocaleStr(key="disable_all_button_label")
        super().__init__(style=discord.ButtonStyle.red, label=label)

    async def callback(self, i: Interaction) -> None:
        for field in AccountNotifSettings.ALL_FIELDS:
            setattr(self.view.account.notif_settings, field, False)
        await self.view.account.notif_settings.save()

        await self.view.update(i)


def _notif_toggles(
    title: LocaleStr, account: HoyoAccount, *, success: str, failure: str
) -> tuple[ui.TextDisplay, ui.ActionRow]:
    return (
        ui.TextDisplay(LocaleStr(custom_str="### {title}", title=title)),
        ui.ActionRow(
            AccountToggleButton(
                attr=f"notif_settings.{success}",
                current=getattr(account.notif_settings, success),
                label=LocaleStr(key="notify_on_success_button_label"),
            ),
            AccountToggleButton(
                attr=f"notif_settings.{failure}",
                current=getattr(account.notif_settings, failure),
                label=LocaleStr(key="notify_on_failure_button_label"),
            ),
        ),
    )


def _gap() -> tuple[discord.ui.Separator, discord.ui.Separator]:
    return (
        discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
        discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
    )


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
            *_notif_toggles(
                LocaleStr(key="auto_checkin_button_label"),
                account,
                success="notify_on_checkin_success",
                failure="notify_on_checkin_failure",
            ),
            *_gap(),
            *_notif_toggles(
                LocaleStr(key="auto_redeem_toggle.label"),
                account,
                success="redeem_success",
                failure="redeem_failure",
            ),
            *_gap(),
            *_notif_toggles(
                LocaleStr(key="accompany_button_label"),
                account,
                success="notify_on_accompany_success",
                failure="notify_on_accompany_failure",
            ),
            *_gap(),
            *_notif_toggles(
                LocaleStr(key="auto_gacha_import_label"),
                account,
                success="gacha_import_success",
                failure="gacha_import_failure",
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
            *_notif_toggles(
                LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
                account,
                success="mimo_task_success",
                failure="mimo_task_failure",
            ),
            *_gap(),
            *_notif_toggles(
                LocaleStr(key="mimo_auto_buy_button_label"),
                account,
                success="mimo_buy_success",
                failure="mimo_buy_failure",
            ),
            *_gap(),
            *_notif_toggles(
                LocaleStr(key="mimo_auto_draw_button_label"),
                account,
                success="mimo_draw_success",
                failure="mimo_draw_failure",
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
            ui.ActionRow(DisableAllNotificationsButton()),
        )
