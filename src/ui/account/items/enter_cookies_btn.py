from typing import TYPE_CHECKING

import genshin
from discord import ButtonStyle, TextStyle

from src.bot.translator import LocaleStr
from src.embeds import ErrorEmbed
from src.emojis import COOKIE
from src.hoyo.gpy_client import GenshinClient

from ...components import Button, GoBackButton, Modal, TextInput
from .add_acc_select import AddAccountSelect

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from src.bot.bot import INTERACTION


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
    def __init__(self, *, dev_tools: bool = False) -> None:
        super().__init__(
            label=LocaleStr("Enter Cookies", key="cookies_button_label"),
            style=ButtonStyle.blurple,
            emoji=COOKIE,
        )
        self.dev_tools = dev_tools

    async def callback(self, i: "INTERACTION") -> None:
        modal = self.get_cookies_modal()
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        cookies = self._get_cookies(modal)
        if not cookies:
            return

        await self.set_loading_state(i)
        client = GenshinClient(cookies)
        client.set_lang(self.view.locale)

        try:
            game_accounts = await client.get_game_accounts()
        except genshin.InvalidCookies:
            await self.unset_loading_state(i)
            embed = self.get_invalid_cookies_embed(modal)
            await i.edit_original_response(embed=embed)
        else:
            go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
            self.view.clear_items()
            self.view.add_item(
                AddAccountSelect(
                    self.view.locale,
                    self.view.translator,
                    accounts=game_accounts,
                    cookies=cookies,
                )
            )
            self.view.add_item(go_back_button)
            await i.edit_original_response(embed=None, view=self.view)

    def get_cookies_modal(self) -> DevToolCookiesModal | CookiesModal:
        if self.dev_tools:
            return DevToolCookiesModal(title=LocaleStr("Enter Cookies", key="cookies_button_label"))
        return CookiesModal(title=LocaleStr("Enter Cookies", key="cookies_button_label"))

    @staticmethod
    def _get_cookies(
        modal: DevToolCookiesModal | CookiesModal,
    ) -> str | None:
        if isinstance(modal, DevToolCookiesModal):
            cookies = "; ".join(f"{child.label}={child.value.strip()}" for child in modal.children)  # type: ignore
            return cookies

        if modal.cookies.value is None:
            return None
        return modal.cookies.value

    def get_invalid_cookies_embed(self, modal: Modal) -> ErrorEmbed:
        if isinstance(modal, CookiesModal):
            return ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Invalid cookies", key="invalid_cookies_title"),
                description=LocaleStr(
                    (
                        "It is likely that your account has the new security feature enabled.\n"
                        "Part of the cookies is encrypted and cannot be obtained by JavaScript.\n"
                        "Please try the other methods to add your accounts."
                    ),
                    key="invalid_cookies_description",
                ),
            )
        else:
            return ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Invalid cookies", key="invalid_cookies_title"),
                description=LocaleStr(
                    "Please check that you copied the values of the cookies correctly",
                    key="invalid_ltuid_ltoken_description",
                ),
            )
