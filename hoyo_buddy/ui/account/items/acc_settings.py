from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.emojis import GIFT_OUTLINE, PUBLIC, SMART_TOY
from hoyo_buddy.l10n import LocaleStr

from ...components import ToggleButton

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class AutoRedeemToggle(ToggleButton["AccountManager"]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="auto_redeem_toggle.label"),
            row=2,
            emoji=GIFT_OUTLINE,
            custom_id="auto_redeem_toggle",
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        assert self.view.selected_account is not None

        self.view.selected_account.auto_redeem = self.current_toggle
        await self.view.selected_account.save(update_fields=("auto_redeem",))


class AutoCheckinToggle(ToggleButton["AccountManager"]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="auto_checkin_button_label"),
            row=2,
            emoji=SMART_TOY,
            custom_id="auto_checkin_toggle",
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        assert self.view.selected_account is not None

        self.view.selected_account.daily_checkin = self.current_toggle
        await self.view.selected_account.save(update_fields=("daily_checkin",))


class AccountPublicToggle(ToggleButton["AccountManager"]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="public_account_toggle.label"),
            row=2,
            emoji=PUBLIC,
            custom_id="public_account_toggle",
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        assert self.view.selected_account is not None

        self.view.selected_account.public = self.current_toggle
        await self.view.selected_account.save(update_fields=("public",))
