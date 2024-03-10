from typing import TYPE_CHECKING

from src.bot.translator import LocaleStr
from src.db.models import NotesNotify
from src.emojis import REALM_CURRENCY
from src.enums import NotesNotifyType
from src.ui import Button

from ..modals import TypeOneModal
from ..view import NotesView

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION


class RealmCurrencyReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            emoji=REALM_CURRENCY,
            label=LocaleStr("Realm Currency Reminder", key="realm_curr_button.label"),
            row=row,
        )

    async def callback(self, i: "INTERACTION") -> None:
        notify = await NotesNotify.get_or_none(
            account=self.view._account, type=NotesNotifyType.REALM_CURRENCY
        )

        modal = TypeOneModal(
            notify,
            title=LocaleStr("Realm Currency Reminder Settings", key="realm_curr_modal.title"),
            threshold_max_value=2400,
            min_notify_interval=30,
        )
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.confirm_required_inputs()
        if incomplete:
            return

        embed = await self.view.process_type_one_modal(
            modal=modal,
            notify=notify,
            notify_type=NotesNotifyType.REALM_CURRENCY,
            check_interval=30,
        )
        await i.edit_original_response(embed=embed)
