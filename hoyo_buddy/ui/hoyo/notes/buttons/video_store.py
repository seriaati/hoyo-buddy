from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import NotesNotify
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeTwoModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class VideoStoreReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr(key="vhs_sale", mi18n_game=Game.ZZZ), row=row)

    async def callback(self, i: Interaction) -> None:
        notify = await NotesNotify.get_or_none(
            account=self.view.account, type=NotesNotifyType.VIDEO_STORE
        )

        modal = TypeTwoModal(
            notify,
            title=LocaleStr(
                key="reminder_modal.title", notify=LocaleStr(key="vhs_sale", mi18n_game=Game.ZZZ)
            ),
            min_notify_interval=30,
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        embed = await self.view.process_type_two_modal(
            modal=modal, notify=notify, notify_type=NotesNotifyType.VIDEO_STORE, check_interval=30
        )
        await i.edit_original_response(embed=embed)
