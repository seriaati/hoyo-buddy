from typing import TYPE_CHECKING

from src.bot.translator import LocaleStr
from src.constants import DB_INTEGER_MAX
from src.ui import Modal, TextInput

if TYPE_CHECKING:
    from src.db.models import NotesNotify


class TypeTwoModal(Modal):
    enabled = TextInput(
        label=LocaleStr("Enabled (0 or 1)", key="notif_modal.enabled.label"),
        is_bool=True,
    )
    notify_interval = TextInput(
        label=LocaleStr("Notify Interval (in minutes)", key="notif_modal.notify_interval.label"),
        is_digit=True,
        min_value=10,
        max_value=DB_INTEGER_MAX,
    )
    max_notif_count = TextInput(
        label=LocaleStr("Max Notify Count", key="notif_modal.max_notif_count.label"),
        is_digit=True,
        min_value=1,
        max_value=DB_INTEGER_MAX,
    )

    def __init__(
        self, notes_notify: "NotesNotify | None", *, title: LocaleStr, min_notify_interval: int
    ) -> None:
        self.notify_interval.min_value = min_notify_interval
        if notes_notify is not None:
            self.enabled.default = str(int(notes_notify.enabled))
            self.notify_interval.default = str(notes_notify.notify_interval)
            self.max_notif_count.default = str(notes_notify.max_notif_count)

        super().__init__(title=title, custom_id=f"notes_notify_type_two_{title.key}")
