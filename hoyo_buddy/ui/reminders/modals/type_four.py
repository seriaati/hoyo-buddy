from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.ui import Modal

from .components import ENABLED, MAX_NOTIF_COUNT, NOTIFY_INTERVAL, NOTIFY_TIME, NOTIFY_WEEKDAY

if TYPE_CHECKING:
    from hoyo_buddy.db import NotesNotify
    from hoyo_buddy.l10n import LocaleStr


class TypeFourModal(Modal):
    enabled = ENABLED
    notify_interval = NOTIFY_INTERVAL
    max_notif_count = MAX_NOTIF_COUNT
    notify_time = NOTIFY_TIME
    notify_weekday = NOTIFY_WEEKDAY

    def __init__(
        self, notes_notify: NotesNotify | None, *, title: LocaleStr, min_notify_interval: int
    ) -> None:
        self.notify_interval.min_value = min_notify_interval
        if notes_notify is not None:
            self.enabled.default = str(int(notes_notify.enabled))
            self.notify_interval.default = str(notes_notify.notify_interval)
            self.max_notif_count.default = str(notes_notify.max_notif_count)
            self.notify_time.default = str(notes_notify.notify_time)
            self.notify_weekday.default = str(notes_notify.notify_weekday)

        super().__init__(title=title, custom_id=f"notes_notify_type_one_{title.key}")
