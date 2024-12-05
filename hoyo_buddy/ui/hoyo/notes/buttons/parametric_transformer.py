from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import NotesNotify
from hoyo_buddy.emojis import PT_EMOJI
from hoyo_buddy.enums import NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeTwoModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class PTReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr(key="pt_button.label"), emoji=PT_EMOJI, row=row)

    async def callback(self, i: Interaction) -> None:
        notify = await NotesNotify.get_or_none(account=self.view.account, type=NotesNotifyType.PT)

        modal = TypeTwoModal(notify, title=LocaleStr(key="pt_modal.title"), min_notify_interval=30)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        embed = await self.view.process_type_two_modal(
            modal=modal, notify=notify, notify_type=NotesNotifyType.PT, check_interval=30
        )
        await i.edit_original_response(embed=embed)
