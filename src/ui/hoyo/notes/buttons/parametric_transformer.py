from typing import TYPE_CHECKING

from src.bot.translator import LocaleStr
from src.db.models import NotesNotify
from src.emojis import PT_EMOJI
from src.enums import NotesNotifyType
from src.ui import Button

from ..modals import TypeTwoModal
from ..view import NotesView

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION


class PTReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            label=LocaleStr("Parametric Transformer Reminder", key="pt_button.label"),
            emoji=PT_EMOJI,
            row=row,
        )

    async def callback(self, i: "INTERACTION") -> None:
        notify = await NotesNotify.get_or_none(account=self.view._account, type=NotesNotifyType.PT)

        modal = TypeTwoModal(
            notify,
            title=LocaleStr("Parametric Transformer Reminder Settings", key="pt_modal.title"),
            min_notify_interval=30,
        )
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.confirm_required_inputs()
        if incomplete:
            return

        embed = await self.view.process_type_two_modal(
            modal=modal,
            notify=notify,
            notify_type=NotesNotifyType.PT,
            check_interval=30,
        )
        await i.edit_original_response(embed=embed)
