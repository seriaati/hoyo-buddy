from __future__ import annotations

from typing import TYPE_CHECKING

from discord import TextStyle

from hoyo_buddy.emojis import EDIT
from hoyo_buddy.l10n import LocaleStr

from ...components import Button, Modal, TextInput

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager
else:
    AccountManager = None


class NicknameModal(Modal):
    nickname = TextInput(
        label=LocaleStr(key="nickname_modal_label"),
        placeholder=LocaleStr(key="nickname_modal_placeholder"),
        required=False,
        style=TextStyle.short,
        max_length=32,
    )

    def __init__(self, current_nickname: str | None = None) -> None:
        super().__init__(title=LocaleStr(key="edit_nickname_modal_title"))
        self.nickname.default = current_nickname


class EditNicknameButton(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="edit_nickname", emoji=EDIT, label=LocaleStr(key="edit_nickname_modal_title")
        )

    async def callback(self, i: Interaction) -> None:
        account = self.view.selected_account
        if account is None:
            msg = "No account selected"
            raise ValueError(msg)

        modal = NicknameModal(account.nickname)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        account.nickname = modal.nickname.value
        await account.save(update_fields=("nickname",))
        await self.view.refresh(i, soft=True)
