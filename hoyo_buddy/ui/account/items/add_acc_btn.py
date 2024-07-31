from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD, HOYOLAB, MIYOUSHE
from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import EnumStr, LocaleStr

from ...components import Button, GoBackButton
from .with_dev_tools import WithDevTools
from .with_email_pswd import WithEmailPassword
from .with_js import WithJavaScript
from .with_mod_app import WithModApp

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class AddMiyousheAccount(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_miyoushe_account",
            emoji=MIYOUSHE,
            label=EnumStr(Platform.MIYOUSHE),
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="add_hoyolab_acc.embed.title"),
            description=LocaleStr(key="add_miyoushe_acc.embed.description"),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        # self.view.add_item(WithQRCode())
        # self.view.add_item(WithEmailPassword(Platform.MIYOUSHE))
        # self.view.add_item(WithMobileNumber())
        # self.view.add_item(WithDevTools(Platform.MIYOUSHE))
        self.view.add_item(WithModApp())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)


class AddHoyolabAccount(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_hoyolab_account",
            emoji=HOYOLAB,
            label=EnumStr(Platform.HOYOLAB),
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="add_hoyolab_acc.embed.title"),
            description=LocaleStr(key="add_hoyolab_acc.embed.description"),
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
            label=LocaleStr(key="add_account_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="adding_accounts_title"),
            description=LocaleStr(key="adding_accounts_description"),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        self.view.add_item(AddMiyousheAccount())
        self.view.add_item(AddHoyolabAccount())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
