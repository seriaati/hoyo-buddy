from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.ui import Modal

from .components import ENABLED, MAX_NOTIF_COUNT, NOTIFY_INTERVAL, THRESHOLD, TYPE_ONE_TEXT_DISPLAY

if TYPE_CHECKING:
    from hoyo_buddy.db import NotesNotify
    from hoyo_buddy.l10n import LocaleStr


class TypeOneModal(Modal):
    enabled = ENABLED
    threshold = THRESHOLD
    notify_interval = NOTIFY_INTERVAL
    max_notif_count = MAX_NOTIF_COUNT

    def __init__(
        self,
        notes_notify: NotesNotify | None,
        *,
        title: LocaleStr,
        threshold_max_value: int,
        min_notify_interval: int,
    ) -> None:
        self.threshold.max_value = threshold_max_value
        self.notify_interval.min_value = min_notify_interval
        if notes_notify is not None:
            self.enabled.default = str(int(notes_notify.enabled))
            self.threshold.default = (
                str(notes_notify.threshold) if notes_notify.threshold is not None else ""
            )
            self.notify_interval.default = str(notes_notify.notify_interval)
            self.max_notif_count.default = str(notes_notify.max_notif_count)

        super().__init__(title=title, custom_id=f"notes_notify_type_one_{title.key}")
