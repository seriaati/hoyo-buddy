from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import NotesNotify
from hoyo_buddy.emojis import SCRATCH_CARD_EMOJI
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeThreeModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class ScratchCardReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            emoji=SCRATCH_CARD_EMOJI, label=LocaleStr(key="card", mi18n_game=Game.ZZZ), row=row
        )

    async def callback(self, i: Interaction) -> None:
        notify = await NotesNotify.get_or_none(
            account=self.view.account, type=NotesNotifyType.SCRATCH_CARD
        )

        modal = TypeThreeModal(
            notify,
            title=LocaleStr(
                key="reminder_modal.title", notify=LocaleStr(key="card", mi18n_game=Game.ZZZ)
            ),
            min_notify_interval=30,
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        embed = await self.view.process_type_three_modal(
            modal=modal, notify=notify, notify_type=NotesNotifyType.SCRATCH_CARD, check_interval=30
        )
        await i.edit_original_response(embed=embed)
