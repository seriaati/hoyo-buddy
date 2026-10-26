from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.db import Settings
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import ToggleButton

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView
else:
    ProfileView = None


class ShowUIDButton(ToggleButton[ProfileView]):
    def __init__(self, current: bool, *, row: int) -> None:
        super().__init__(
            current, LocaleStr(key="show_uid"), disabled=True, custom_id="profile_show_uid", row=row
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=False)

        settings = await Settings.get(user_id=i.user.id)
        settings.show_uid = self.current_toggle
        await settings.save(update_fields=("show_uid",))

        await self.set_loading_state(i)
        await self.view.update(i, self)
