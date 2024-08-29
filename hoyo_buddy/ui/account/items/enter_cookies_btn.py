from __future__ import annotations

from typing import TYPE_CHECKING

import genshin
from discord import ButtonStyle, TextStyle

from hoyo_buddy.emojis import COOKIE
from hoyo_buddy.l10n import LocaleStr

from ...components import Button, Modal, TextInput

if TYPE_CHECKING:
    from hoyo_buddy.enums import Platform
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager


class CookiesModal(Modal):
    cookies_input = TextInput(
        label="Cookies",
        placeholder=LocaleStr(key="cookies_modal_placeholder"),
        style=TextStyle.paragraph,
    )

    @property
    def cookies(self) -> str:
        return self.cookies_input.value.strip()


class DevToolCookiesModal(Modal):
    ltuid_v2 = TextInput(label="ltuid_v2", placeholder="1234567", is_digit=True)
    ltoken_v2 = TextInput(label="ltoken_v2", placeholder="v2_ABCDe5678...")
    ltmid_v2 = TextInput(label="ltmid_v2", placeholder="1k922_hy")
    account_mid_v2 = TextInput(label="account_mid_v2", placeholder="1k922_hy")
    account_id_v2 = TextInput(label="account_id_v2", placeholder="1234567", is_digit=True)

    @property
    def cookies(self) -> str:
        return "; ".join(f"{child.label}={child.value.strip()}" for child in self.children)  # pyright: ignore[reportAttributeAccessIssue]


class EnterCookiesButton(Button["AccountManager"]):
    def __init__(self, *, platform: Platform, dev_tools: bool = False) -> None:
        super().__init__(
            label=LocaleStr(key="cookies_button_label"),
            style=ButtonStyle.blurple,
            emoji=COOKIE,
        )
        self._platform = platform
        self._is_dev_tools = dev_tools

    def _get_cookies_modal(self) -> DevToolCookiesModal | CookiesModal:
        if self._is_dev_tools:
            return DevToolCookiesModal(title=LocaleStr(key="cookies_button_label"))
        return CookiesModal(title=LocaleStr(key="cookies_button_label"))

    async def callback(self, i: Interaction) -> None:
        modal = self._get_cookies_modal()
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        cookies = genshin.parse_cookie(modal.cookies)
        await self.view.finish_cookie_setup(cookies, platform=self._platform, interaction=i)
