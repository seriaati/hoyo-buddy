from typing import TYPE_CHECKING, Any

from discord import ButtonStyle

from src.bot.translator import LocaleStr
from src.embeds import DefaultEmbed, ErrorEmbed
from src.emojis import FORWARD, INFO, PASSWORD, REFRESH

from ....hoyo.gpy_client import GenshinClient
from ...components import Button, GoBackButton, Modal, TextInput
from .add_acc_select import AddAccountSelect

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from src.bot.bot import INTERACTION

GEETEST_SERVER_URL = {
    "prod": "https://geetest-server.seriaati.xyz",
    "test": "http://geetest-server-test.seriaati.xyz",
    "dev": "http://localhost:5000",
}


class EmailPasswordContinueButton(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="email_password_continue",
            label=LocaleStr("Continue", key="continue_button_label"),
            emoji=FORWARD,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: "INTERACTION") -> None:
        user = self.view.user
        await user.refresh_from_db()
        cookies: dict[str, Any] | None = user.temp_data.get("cookies")
        if cookies is None:
            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Cookies not found", key="cookies_not_found_title"),
                description=LocaleStr(
                    "Please complete the CAPTCHA before continuing.",
                    key="cookies_not_found_description",
                ),
            )
            self.label = self.view.translator.translate(
                LocaleStr("Refresh", key="refresh_button_label"), self.view.locale
            )
            self.emoji = REFRESH
            return await i.response.edit_message(embed=embed, view=self.view)

        if retcode := cookies.get("retcode"):
            if str(retcode) == "-3208":
                embed = ErrorEmbed(
                    self.view.locale,
                    self.view.translator,
                    title=LocaleStr(
                        "Invalid email or password", key="invalid_email_password_title"
                    ),
                    description=LocaleStr(
                        "Either your email or password is incorrect, please try again by pressing the back button.",
                        key="invalid_email_password_description",
                    ),
                )
                self.view.remove_item(self)
                return await i.response.edit_message(embed=embed, view=self.view)

            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Unknown error", key="unknown_error_title"),
                description=LocaleStr(
                    "Error code: {retcode}\nMessage: {msg}",
                    key="unknown_error_description",
                    retcode=retcode,
                    msg=cookies.get("message"),
                ),
            )
            return await i.response.edit_message(embed=embed, view=self.view)

        await self.set_loading_state(i)
        str_cookies = "; ".join(f"{key}={value}" for key, value in cookies.items())
        client = GenshinClient(str_cookies)
        client.set_lang(self.view.locale)
        game_accounts = await client.get_game_accounts()
        await self.unset_loading_state(i)

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(
            AddAccountSelect(
                self.view.locale,
                self.view.translator,
                accounts=game_accounts,
                cookies=str_cookies,
            )
        )
        self.view.add_item(go_back_button)
        await i.edit_original_response(embed=None, view=self.view)


class EmailPasswordModal(Modal):
    email = TextInput(
        label=LocaleStr("email or username", key="email_password_modal_email_input_label"),
        placeholder="a@gmail.com",
    )
    password = TextInput(
        label=LocaleStr("password", key="email_password_modal_password_input_label"),
        placeholder="12345678",
    )


class EnterEmailPassword(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Enter Email and Password", key="enter_email_password_button_label"),
            style=ButtonStyle.blurple,
            emoji=PASSWORD,
        )

    async def callback(self, i: "INTERACTION") -> Any:
        modal = EmailPasswordModal(
            title=LocaleStr("Enter Email and Password", key="enter_email_password_modal_title")
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if modal.email.value is None or modal.password.value is None:
            return
        email = modal.email.value
        password = modal.password.value
        self.view.user.temp_data["email"] = email
        self.view.user.temp_data["password"] = password
        await self.view.user.save()

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        web_server_url = GEETEST_SERVER_URL[i.client.env]
        self.view.add_item(
            Button(
                label=LocaleStr("Complete CAPTCHA", key="complete_captcha_button_label"),
                url=f"{web_server_url}/?user_id={i.user.id}&locale={self.view.locale.value}",
            )
        )
        self.view.add_item(EmailPasswordContinueButton())
        self.view.add_item(go_back_button)
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{INFO} Note: This method **DOESN'T WORK** for Miyoushe users, only HoYoLAB users can use this method.\n\n"
                    "1. Click the `Complete CAPTCHA` button below\n"
                    "2. You will be redirected to a website, click the button and complete the CAPTCHA\n"
                    "3. After completing, click on the `Continue` button below\n"
                ),
                key="email_password_instructions_description",
            ),
        )
        embed.set_image(url="https://i.imgur.com/Q9cR2Sf.gif")
        await i.edit_original_response(embed=embed, view=self.view)


class WithEmailPassword(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("With Email and Password", key="email_password_button_label")
        )

    async def callback(self, i: "INTERACTION") -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{INFO} Note: This method is not recommended as it requires you to enter your private information, it only serves as a last resort when the other 2 methods don't work. Your email and password are not saved permanently in the database, you can refer to the [source code](https://github.com/seriaati/hoyo-buddy/blob/3bbd8a9fb42d2bb8db4426fda7d7d3ba6d86e75c/hoyo_buddy/ui/login/accounts.py#L386) if you feel unsafe.\n\n"
                    "Click the button below to enter your email and password.\n"
                ),
                key="enter_email_password_instructions_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterEmailPassword())
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
