from __future__ import annotations

from http.cookies import SimpleCookie
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle, TextStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Platform

from ...components import Button, GoBackButton, Modal, TextInput

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import AccountManager  # noqa: F401


class WithModApp(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr("With modded app", key="modded_app_button_label"))

    @property
    def _instructions_embed(self) -> list[DefaultEmbed]:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                "1. If you have Miyoushe installed on your device, uninstall it.\n"
                "2. Download the modded apk by clicking the button below.\n"
                "3. Install the modded app and open it.\n"
                "4. Ignore any update prompts and log in with your account.\n"
                "5. Click 'my account' and click on the key icon.\n"
                "6. Click 'copy login details'.\n"
                "7. Click the '{label}' button below and paste the copied details.",
                key="modded_app_login_instructions.desc",
                label=LocaleStr("Enter login details", key="enter_login_details_button_label"),
            ),
            url="https://github.com/seriaati/hoyo-buddy",
        )
        embed.set_image(
            url="https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/MiyousheCopyLoginTutorial1.jpg"
        )
        embed2 = embed.copy()
        embed2.set_image(
            url="https://raw.githubusercontent.com/seriaati/hoyo-buddy/assets/MiyousheCopyLoginTutorial2.jpg"
        )
        return [embed, embed2]

    async def callback(self, i: Interaction) -> Any:
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(go_back_button)
        self.view.add_item(
            Button(
                label=LocaleStr("Download app", key="download_app_button_label"),
                url="https://github.com/PaiGramTeam/GetToken/releases/latest/download/miyoushe-361-lspatched.apk",
            )
        )
        self.view.add_item(EnterLoginDetails())
        await i.response.edit_message(embeds=self._instructions_embed, view=self.view)


class LoginDetailModal(Modal):
    login_detail = TextInput(
        label=LocaleStr("Login details", key="login_detail_modal.input_label"), style=TextStyle.long
    )


class EnterLoginDetails(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Enter login details", key="enter_login_details_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: Interaction) -> Any:
        self.view.clear_items()
        self.view.add_item(GoBackButton(self.view.children, self.view.get_embeds(i.message)))

        modal = LoginDetailModal(
            title=LocaleStr("Enter login details", key="enter_login_details_button_label")
        )
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        cookie = SimpleCookie()
        cookie.load(modal.login_detail.value)
        dict_cookies = {key: morsel.value for key, morsel in cookie.items()}
        await self.view.finish_cookie_setup(dict_cookies, platform=Platform.MIYOUSHE, interaction=i)
