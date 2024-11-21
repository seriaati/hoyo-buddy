from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import NotesNotify
from hoyo_buddy.enums import NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeOneModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class StaminaReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr(key="notes.stamina_label"), row=row)

    async def callback(self, i: Interaction) -> None:
        notify = await NotesNotify.get_or_none(account=self.view._account, type=NotesNotifyType.STAMINA)

        modal = TypeOneModal(
            notify,
            title=LocaleStr(key="reminder_modal.title", notify=LocaleStr(key="notes.stamina_label")),
            threshold_max_value=240,
            min_notify_interval=10,
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.incomplete
        if incomplete:
            return

        embed = await self.view.process_type_one_modal(
            modal=modal, notify=notify, notify_type=NotesNotifyType.STAMINA, check_interval=10
        )
        await i.edit_original_response(embed=embed)
