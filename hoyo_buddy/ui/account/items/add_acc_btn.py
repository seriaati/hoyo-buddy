from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD

from ...components import Button, GoBackButton
from .with_dev_tools import WithDevTools
from .with_email_pswd import WithEmailPassword
from .with_js import WithJavaScript

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION


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
                (
                    "Select one of the methods below to add your accounts to Hoyo Buddy:\n"
                    "1. With Email and Password: Most recommended, it's the easiest\n"
                    "2. With Dev Tools: Only work on desktop, a safer option if you have security concerns with the first one\n"
                    "3. With JavaScript: Outdated method, won't work for most accounts. Works on Google Chrome or Microsoft Edge on both desktop and mobile\n\n"
                    "Regarding account security, read the [Wiki page](https://github.com/seriaati/hoyo-buddy/wiki/Account-Security), for how we use and collect your data, read the [Privacy Policy](https://github.com/seriaati/hoyo-buddy/blob/main/PRIVACY.md)"
                ),
                key="adding_accounts_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        self.view.add_item(WithEmailPassword())
        self.view.add_item(WithDevTools())
        self.view.add_item(WithJavaScript())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
