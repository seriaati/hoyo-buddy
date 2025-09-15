from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.constants import DB_SMALLINT_MAX
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Label, Modal, TextInput
from hoyo_buddy.ui.discord.select import BooleanSelect

if TYPE_CHECKING:
    from hoyo_buddy.db import NotesNotify


class TypeFourModal(Modal):
    enabled: Label[BooleanSelect] = Label(
        text=LocaleStr(key="notif_modal.enabled.label"), component=BooleanSelect()
    )
    notify_interval: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.notify_interval.label"),
        component=TextInput(is_digit=True, min_value=10, max_value=DB_SMALLINT_MAX),
    )
    max_notif_count: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.max_notif_count.label"),
        component=TextInput(is_digit=True, min_value=1, max_value=DB_SMALLINT_MAX),
    )
    notify_time: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.notify_time.label"),
        component=TextInput(is_digit=True, min_value=1, max_value=24),
    )
    notify_weekday: Label[TextInput] = Label(
        text=LocaleStr(key="notif_modal.notify_weekday.label"),
        component=TextInput(is_digit=True, min_value=1, max_value=7),
    )

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
