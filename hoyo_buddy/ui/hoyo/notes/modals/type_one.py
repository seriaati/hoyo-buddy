from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.constants import DB_SMALLINT_MAX
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Label, Modal, TextInput

if TYPE_CHECKING:
    from hoyo_buddy.db import NotesNotify


class TypeOneModal(Modal):
    enabled: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.enabled.label"), component=TextInput(is_bool=True)
    )
    threshold: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.threshold.label"),
        component=TextInput(is_digit=True, min_value=0),
    )
    notify_interval: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.notify_interval.label"),
        component=TextInput(is_digit=True, max_value=DB_SMALLINT_MAX),
    )
    max_notif_count: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.max_notif_count.label"),
        component=TextInput(is_digit=True, min_value=1, max_value=DB_SMALLINT_MAX),
    )

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
