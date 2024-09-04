from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.constants import WEB_APP_URLS
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD, HOYOLAB, MIYOUSHE
from hoyo_buddy.enums import Platform
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.web_app.schema import Params

from ...components import Button, GoBackButton
from .with_dev_tools import WithDevTools
from .with_email_pswd import WithEmailPassword
from .with_js import WithJavaScript
from .with_mobile import WithMobileNumber
from .with_mod_app import WithModApp
from .with_qrcode import WithQRCode

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager
else:
    AccountManager = None


class AddMiyousheAccount(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_miyoushe_account", emoji=MIYOUSHE, label=EnumStr(Platform.MIYOUSHE)
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="add_hoyolab_acc.embed.title"),
            description="1. 通过改装过的米游社应用程序: 只有安卓裝置可使用\n2. 通过扫描二维码\n3. 通过手机号: 只有中国大陆手机号可使用\n4. 通过邮箱密码\n5. 通过开发者工具",
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()

        self.view.add_item(WithModApp())
        self.view.add_item(WithQRCode())
        self.view.add_item(WithMobileNumber())
        self.view.add_item(WithEmailPassword(Platform.MIYOUSHE))
        self.view.add_item(WithDevTools(Platform.MIYOUSHE))
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)


class AddHoyolabAccount(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_hoyolab_account", emoji=HOYOLAB, label=EnumStr(Platform.HOYOLAB)
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


class AddAccountButton(Button[AccountManager]):
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
            title=LocaleStr(key="account_add_start_title"),
            description=LocaleStr(key="account_add_start_message"),
        )
        self.view.clear_items()
        params = Params(
            locale=self.view.locale.value,
            user_id=i.user.id,
            channel_id=i.channel.id if i.channel is not None else 0,
            guild_id=i.guild.id if i.guild is not None else None,
        )
        self.view.add_item(
            Button(
                label=LocaleStr(key="hbls_button_label"),
                url=WEB_APP_URLS[i.client.env] + f"/platforms?{params.to_query_string()}",
            )
        )
        await i.response.edit_message(embed=embed, view=self.view)
