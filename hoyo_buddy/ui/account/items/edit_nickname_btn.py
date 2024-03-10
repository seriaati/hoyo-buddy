from typing import TYPE_CHECKING

from discord import TextStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import EDIT

from ...components import Button, Modal, TextInput

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION


class NicknameModal(Modal):
    nickname = TextInput(
        label=LocaleStr("Nickname", key="nickname_modal_label"),
        placeholder=LocaleStr("Main account, Asia account...", key="nickname_modal_placeholder"),
        required=False,
        style=TextStyle.short,
        max_length=32,
    )

    def __init__(self, current_nickname: str | None = None) -> None:
        super().__init__(title=LocaleStr("Edit nickname", key="edit_nickname_modal_title"))
        self.nickname.default = current_nickname


class EditNicknameButton(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="edit_nickname",
            emoji=EDIT,
            label=LocaleStr("Edit nickname", key="edit_nickname_button_label"),
        )

    async def callback(self, i: "INTERACTION") -> None:
        account = self.view.selected_account
        if account is None:
            msg = "No account selected"
            raise ValueError(msg)

        modal = NicknameModal(account.nickname)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        account.nickname = modal.nickname.value
        await account.save()
        await self.view.refresh(i, soft=True)
