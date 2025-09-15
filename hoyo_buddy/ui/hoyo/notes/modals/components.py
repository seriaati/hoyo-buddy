from __future__ import annotations

from hoyo_buddy.constants import DB_SMALLINT_MAX
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import BooleanSelect, Label, TextDisplay, TextInput, WeekdaySelect

# Text displays
TYPE_ONE_TEXT_DISPLAY = TextDisplay(content=LocaleStr(key="notif_modal.type_one.description"))

# Labels
ENABLED: Label[BooleanSelect] = Label(
    text=LocaleStr(key="notif_modal.enabled.label"), component=BooleanSelect()
)
NOTIFY_INTERVAL: Label[TextInput] = Label(
    text=LocaleStr(key="notif_modal.notify_interval.label"),
    component=TextInput(is_digit=True, min_value=10, max_value=DB_SMALLINT_MAX),
    description=LocaleStr(key="notif_modal.notify_interval.description"),
)
MAX_NOTIF_COUNT: Label[TextInput] = Label(
    text=LocaleStr(key="notif_modal.max_notif_count.label"),
    component=TextInput(is_digit=True, min_value=1, max_value=DB_SMALLINT_MAX),
    description=LocaleStr(key="notif_modal.max_notif_count.description"),
)
NOTIFY_TIME: Label[TextInput] = Label(
    text=LocaleStr(key="notif_modal.notify_time.label"),
    component=TextInput(is_digit=True, min_value=1, max_value=24),
    description=LocaleStr(key="notif_modal.notify_time.description"),
)
NOTIFY_WEEKDAY: Label[TextInput] = Label(
    text=LocaleStr(key="notif_modal.notify_weekday.label"), component=WeekdaySelect()
)
HOURS_BEFORE: Label[TextInput] = Label(
    text=LocaleStr(key="notif_modal.notify_time.label"),
    component=TextInput(is_digit=True, min_value=1, max_value=DB_SMALLINT_MAX),
    description=LocaleStr(key="notif_modal.hours_before.label"),
)
THRESHOLD: Label[TextInput] = Label(
    text=LocaleStr(key="notif_modal.threshold.label"),
    component=TextInput(is_digit=True, min_value=0),
    description=LocaleStr(key="notif_modal.threshold.description"),
)
