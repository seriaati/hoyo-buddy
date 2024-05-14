from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import NotesNotify
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.ui import Button

from ..modals import TypeThreeModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION


class DailyReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr("Daily reminder", key="daily_button.label"), row=row)

    async def callback(self, i: INTERACTION) -> None:
        notify_type = (
            NotesNotifyType.GI_DAILY
            if self.view._account.game is Game.GENSHIN
            else NotesNotifyType.HSR_DAILY
        )
        notify = await NotesNotify.get_or_none(account=self.view._account, type=notify_type)

        modal = TypeThreeModal(
            notify,
            title=LocaleStr("Daily Reminder Settings", key="daily_modal.title"),
            min_notify_interval=30,
        )
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.incomplete
        if incomplete:
            return

        embed = await self.view.process_type_three_modal(
            modal=modal,
            notify=notify,
            notify_type=notify_type,
            check_interval=30,
        )
        await i.edit_original_response(embed=embed)
