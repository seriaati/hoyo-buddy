from typing import TYPE_CHECKING

from src.bot.translator import LocaleStr
from src.db.models import NotesNotify
from src.enums import Game, NotesNotifyType
from src.ui import Button

from ..modals import TypeTwoModal
from ..view import NotesView

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION


class ExpeditionReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr("Expedition Reminder", key="exped_button.label"), row=row)

    async def callback(self, i: "INTERACTION") -> None:
        notify_type = (
            NotesNotifyType.GI_EXPED
            if self.view._account.game is Game.GENSHIN
            else NotesNotifyType.HSR_EXPED
        )
        notify = await NotesNotify.get_or_none(account=self.view._account, type=notify_type)

        modal = TypeTwoModal(
            notify,
            title=LocaleStr("Expedition Reminder Settings", key="exped_modal.title"),
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
            notify_type=notify_type,
            check_interval=30,
        )
        await i.edit_original_response(embed=embed)
