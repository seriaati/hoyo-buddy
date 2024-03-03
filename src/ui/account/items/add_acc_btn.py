from typing import TYPE_CHECKING

from discord import ButtonStyle

from src.bot.translator import LocaleStr
from src.embeds import DefaultEmbed
from src.emojis import ADD

from ...components import Button, GoBackButton
from .with_dev_tools import WithDevTools
from .with_email_pswd import WithEmailPassword
from .with_js import WithJavaScript

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from src.bot.bot import INTERACTION


class AddAccountButton(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_account",
            emoji=ADD,
            label=LocaleStr("Add accounts", key="add_account_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Adding accounts", key="adding_accounts_title"),
            description=LocaleStr(
                "Below are 3 ways you can add accounts; however, it is recommended to try the first one, then work your way through the others if it doesn't work.",
                key="adding_accounts_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(WithJavaScript())
        self.view.add_item(WithDevTools())
        self.view.add_item(WithEmailPassword())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
