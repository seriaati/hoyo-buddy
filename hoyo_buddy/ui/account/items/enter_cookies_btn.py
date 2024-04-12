from http.cookies import SimpleCookie
from typing import TYPE_CHECKING

from discord import ButtonStyle, TextStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import COOKIE

from ...components import Button, Modal, TextInput

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION

    from ....enums import LoginPlatform


class CookiesModal(Modal):
    cookies = TextInput(
        label="Cookies",
        placeholder=LocaleStr("Paste your cookies here...", key="cookies_modal_placeholder"),
        style=TextStyle.paragraph,
    )


class DevToolCookiesModal(Modal):
    ltuid_v2 = TextInput(label="ltuid_v2", placeholder="1234567")
    ltoken_v2 = TextInput(label="ltoken_v2", placeholder="v2_ABCDe5678...")
    ltmid_v2 = TextInput(label="ltmid_v2", placeholder="1k922_hy")
    account_mid_v2 = TextInput(label="account_mid_v2", placeholder="1k922_hy")
    account_id_v2 = TextInput(label="account_id_v2", placeholder="1234567")


class EnterCookiesButton(Button["AccountManager"]):
    def __init__(self, *, platform: "LoginPlatform", dev_tools: bool = False) -> None:
        super().__init__(
            label=LocaleStr("Enter cookies", key="cookies_button_label"),
            style=ButtonStyle.blurple,
            emoji=COOKIE,
        )
        self._platform = platform
        self._is_dev_tools = dev_tools

    @staticmethod
    def _get_cookies(
        modal: DevToolCookiesModal | CookiesModal,
    ) -> str:
        if isinstance(modal, DevToolCookiesModal):
            cookies = "; ".join(f"{child.label}={child.value.strip()}" for child in modal.children)  # pyright: ignore[reportAttributeAccessIssue]
            return cookies

        return modal.cookies.value.strip()

    def _get_cookies_modal(self) -> DevToolCookiesModal | CookiesModal:
        if self._is_dev_tools:
            return DevToolCookiesModal(title=LocaleStr("Enter Cookies", key="cookies_button_label"))
        return CookiesModal(title=LocaleStr("Enter Cookies", key="cookies_button_label"))

    async def callback(self, i: "INTERACTION") -> None:
        modal = self._get_cookies_modal()
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        cookies = self._get_cookies(modal)
        cookie = SimpleCookie()
        cookie.load(cookies)
        dict_cookies = {key: morsel.value for key, morsel in cookie.items()}

        # Set up variables for the handler
        self.view.interaction = i
        self.view.platform = self._platform

        await self.view.finish_cookie_setup(dict_cookies)
