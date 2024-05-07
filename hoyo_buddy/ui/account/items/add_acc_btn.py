from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD, HOYOLAB, MIYOUSHE

from ....enums import Platform
from ...components import Button, GoBackButton
from .with_dev_tools import WithDevTools
from .with_email_pswd import WithEmailPassword
from .with_js import WithJavaScript
from .with_mobile import WithMobileNumber
from .with_qrcode import WithQRCode

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION


class AddMiyousheAccount(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_miyoushe_account",
            emoji=MIYOUSHE,
            label=LocaleStr(Platform.MIYOUSHE.value, warn_no_key=False),
        )

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(
                "Select a Method to add Your Accounts", key="add_hoyolab_acc.embed.title"
            ),
            description=LocaleStr(
                (
                    "1. With QR code: Recommended for most users if you are logged in on your mobile device\n"
                    "2. With email/username and password\n"
                    "3. With phone number\n"
                    "4. With DevTools: Only work on desktop, a safer option if you have security concerns with the other methods\n"
                ),
                key="add_miyoushe_acc.embed.description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        self.view.add_item(WithQRCode())
        self.view.add_item(WithEmailPassword(Platform.MIYOUSHE))
        self.view.add_item(WithMobileNumber())
        self.view.add_item(WithDevTools(Platform.MIYOUSHE))
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)


class AddHoyolabAccount(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_hoyolab_account",
            emoji=HOYOLAB,
            label=LocaleStr(Platform.HOYOLAB.value, warn_no_key=False),
        )

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(
                "Select a Method to add Your Accounts", key="add_hoyolab_acc.embed.title"
            ),
            description=LocaleStr(
                (
                    "1. With email and password: Most recommended, it's the easiest\n"
                    "2. With DevTools: Only work on desktop, a safer option if you have security concerns with the first one\n"
                    "3. With JavaScript: Outdated method, won't work for most accounts. Works on Google Chrome or Microsoft Edge on both desktop and mobile\n\n"
                ),
                key="add_hoyolab_acc.embed.description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        self.view.add_item(WithEmailPassword(Platform.HOYOLAB))
        self.view.add_item(WithDevTools(Platform.HOYOLAB))
        self.view.add_item(WithJavaScript())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)


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
            title=LocaleStr("Select Your Account's Platform", key="adding_accounts_title"),
            description=LocaleStr(
                (
                    "Welcome to Hoyo Buddy! Enjoy various features by spending less than 1 minute to add your accounts.\n\n"
                    "Regarding account security, please read the [Wiki page](https://github.com/seriaati/hoyo-buddy/wiki/Account-Security), for how we use and collect your data, please read the [Privacy Policy](https://github.com/seriaati/hoyo-buddy/blob/main/PRIVACY.md)"
                ),
                key="adding_accounts_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        self.view.add_item(AddMiyousheAccount())
        self.view.add_item(AddHoyolabAccount())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
