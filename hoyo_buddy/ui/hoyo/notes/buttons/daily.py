from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db.models import NotesNotify
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button

from ..modals import TypeThreeModal
from ..view import NotesView

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction


class DailyReminder(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(label=LocaleStr(key="daily_button.label"), row=row)

    async def callback(self, i: Interaction) -> None:
        notify_types = {
            Game.GENSHIN: NotesNotifyType.GI_DAILY,
            Game.STARRAIL: NotesNotifyType.HSR_DAILY,
            Game.ZZZ: NotesNotifyType.ZZZ_DAILY,
        }
        notify_type = notify_types.get(self.view._account.game)
        if notify_type is None:
            msg = f"Daily reminder not supported for game: {self.view._account.game}"
            raise ValueError(msg)

        notify = await NotesNotify.get_or_none(account=self.view._account, type=notify_type)

        modal = TypeThreeModal(notify, title=LocaleStr(key="daily_modal.title"), min_notify_interval=30)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.incomplete
        if incomplete:
            return

        embed = await self.view.process_type_three_modal(
            modal=modal, notify=notify, notify_type=notify_type, check_interval=30
        )
        await i.edit_original_response(embed=embed)
