from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import NotesNotify
from hoyo_buddy.emojis import RESIN
from hoyo_buddy.enums import NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeOneModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class ResinReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(emoji=RESIN, label=LocaleStr(key="resin_reminder_button.label"), row=row)

    async def callback(self, i: Interaction) -> None:
        notify = await NotesNotify.get_or_none(
            account=self.view.account, type=NotesNotifyType.RESIN
        )

        modal = TypeOneModal(
            notify,
            title=LocaleStr(key="resin_reminder_modal.title"),
            threshold_max_value=200,
            min_notify_interval=10,
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        embed = await self.view.process_type_one_modal(
            modal=modal, notify=notify, notify_type=NotesNotifyType.RESIN, check_interval=10
        )
        await i.edit_original_response(embed=embed)
