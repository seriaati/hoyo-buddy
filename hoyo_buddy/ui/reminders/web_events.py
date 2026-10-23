from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy import ui
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    from hoyo_buddy.db.models.notif_settings import AccountNotifSettings
    from hoyo_buddy.types import Interaction

    from .view import RemindersView  # ruff:ignore[unused-import]


class WebEventsNotifyToggle(ui.ToggleButton["RemindersView"]):
    def __init__(self, notif_settings: AccountNotifSettings) -> None:
        super().__init__(notif_settings.web_events, LocaleStr(key="web_events_notify_toggle_label"))
        self.notif_settings = notif_settings

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.notif_settings.web_events = self.current_toggle
        await self.notif_settings.save(update_fields=("web_events",))


class WebEventsReminderContainer(ui.DefaultContainer["RemindersView"]):
    def __init__(self, *, notif_settings: AccountNotifSettings) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="web_events_reminder_title"),
                    desc=LocaleStr(key="web_events_reminder_desc"),
                )
            ),
            ui.ActionRow(WebEventsNotifyToggle(notif_settings)),
        )
