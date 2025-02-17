from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import NotesNotify
from hoyo_buddy.emojis import TRAILBLAZE_POWER
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeOneModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class TBPReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            emoji=TRAILBLAZE_POWER,
            label=LocaleStr(key="hsr_note_stamina", mi18n_game=Game.STARRAIL),
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        notify = await NotesNotify.get_or_none(
            account=self.view.account, type=NotesNotifyType.TB_POWER
        )

        modal = TypeOneModal(
            notify,
            title=LocaleStr(key="reminder_modal.title", notify=self.label),
            threshold_max_value=300,
            min_notify_interval=10,
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        embed = await self.view.process_type_one_modal(
            modal=modal, notify=notify, notify_type=NotesNotifyType.TB_POWER, check_interval=10
        )
        await i.edit_original_response(embed=embed)
