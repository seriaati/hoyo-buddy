from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import NotesNotify
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeTwoModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class ExpeditionReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr(key="exped_button.label"), row=row)

    async def callback(self, i: Interaction) -> None:
        notify_type = (
            NotesNotifyType.GI_EXPED
            if self.view._account.game is Game.GENSHIN
            else NotesNotifyType.HSR_EXPED
        )
        notify = await NotesNotify.get_or_none(account=self.view._account, type=notify_type)

        modal = TypeTwoModal(
            notify, title=LocaleStr(key="exped_modal.title"), min_notify_interval=30
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.incomplete
        if incomplete:
            return

        embed = await self.view.process_type_two_modal(
            modal=modal, notify=notify, notify_type=notify_type, check_interval=30
        )
        await i.edit_original_response(embed=embed)
