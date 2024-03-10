import asyncio
import os
from enum import IntEnum
from typing import TYPE_CHECKING, Any

import asyncpg_listen
import genshin
from discord import ButtonStyle
from tortoise import Tortoise

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import User
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO, PASSWORD
from hoyo_buddy.exceptions import (
    InvalidCodeError,
    InvalidEmailOrPasswordError,
    VerificationCodeServiceUnavailableError,
)
from hoyo_buddy.models import LoginNotifPayload

from ...components import Button, GoBackButton, Modal, TextInput
from .add_acc_select import AddAccountSelect

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION

GEETEST_SERVER_URL = {
    "prod": "https://geetest-server.seriaati.xyz",
    "test": "http://geetest-server-test.seriaati.xyz",
    "dev": "http://localhost:5000",
}


class Condition(IntEnum):
    GEETEST_TRIGGERED = 1
    GEETEST_TRIGGERED_FOR_EMAIL = 2
    NEED_EMAIL_VERIFICATION = 3


class WithEmailPassword(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("With E-mail and Password", key="email_password_button_label")
        )

    async def callback(self, i: "INTERACTION") -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{INFO} This method requires you to enter your private information.\n\n"
                    "• In exchange, your `cookie_token` can be refreshed automatically, which is used in features related to code redemption.\n"
                    "• Your e-mail and password are **NOT** saved in the database **AT ALL**, so it's practically impossible for them to be leaked.\n"
                    "• Additionally, this bot is open-sourced on [GitHub](https://github.com/seriaati/hoyo-buddy), so you can verify that yourself.\n"
                    "• It is ultimately your choice to decide whether to trust this bot or not.\n\n"
                    "Click on the button below to start.\n"
                ),
                key="enter_email_password_instructions_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterEmailPassword())
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)


class EmailVerificationCodeModal(Modal):
    code = TextInput(
        label=LocaleStr("Verification Code", key="email_verification_code_modal_code_input_label"),
        placeholder="123456",
        min_length=6,
        max_length=6,
    )


class EnterEmailVerificationCode(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Enter Verification Code", key="email-verification-code.button.label"),
            style=ButtonStyle.blurple,
            emoji=PASSWORD,
        )

    async def callback(self, i: "INTERACTION") -> Any:
        modal = EmailVerificationCodeModal(
            title=LocaleStr("Enter Verification Code", key="email-verification-code.button.label")
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if modal.code.value is None:
            return

        user = await User.get(id=i.user.id)
        code = modal.code.value

        client = genshin.Client()
        try:
            await client._verify_email(code, user.temp_data)
        except genshin.GenshinException as e:
            if e.retcode == -3205:
                raise InvalidCodeError from e
            raise

        conn = Tortoise.get_connection("default")
        await conn.execute_query(f"NOTIFY login, '{i.user.id}'")


class EmailPasswordModal(Modal):
    email = TextInput(
        label=LocaleStr("e-mail or username", key="email_password_modal_email_input_label"),
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

        self.__email: str | None = None
        self.__password: str | None = None
        self._condition: Condition | None = None
        self._login_listener_task: asyncio.Task | None = None
        self._client = genshin.Client()
        self._interaction: "INTERACTION | None" = None
        self._ticket: dict[str, Any] | None = None

    async def _prompt_user_to_solve_geetest(self, i: "INTERACTION") -> None:
        assert i.channel is not None and i.message is not None
        payload = LoginNotifPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild else None,
            channel_id=i.channel.id,
            message_id=i.message.id,
            locale=self.view.locale.value,
        )
        url = f"{GEETEST_SERVER_URL[i.client.env]}/captcha?{payload.to_query_string()}"

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(
            Button(
                label=LocaleStr("Complete CAPTCHA", key="complete_captcha_button_label"), url=url
            )
        )
        self.view.add_item(go_back_button)

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(
                "😅 Ugh! Need to solve CAPTCHA before logging in", key="geetest.embed.title"
            )
            if self._condition is Condition.GEETEST_TRIGGERED
            else LocaleStr(
                "😥 Agh! Need to solve CAPTCHA (again!) before sending an e-mail verification",
                key="email-geetest.embed.title",
            ),
            description=LocaleStr(
                "Click on the button below to complete CAPTCHA.\n",
                key="captcha.embed.description",
            ),
        )
        await i.edit_original_response(embed=embed, view=self.view)

    async def _prompt_user_to_verify_email(self, i: "INTERACTION") -> None:
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterEmailVerificationCode())
        self.view.add_item(go_back_button)

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(
                "👍 Almost done! Just need to verify your e-mail",
                key="email-verification.embed.title",
            ),
            description=LocaleStr(
                (
                    "1. Go to the inbox of the e-mail your entered and find the verification code sent from Hoyoverse.\n"
                    "2. Click the button below to enter the code received.\n"
                ),
                key="email-verification.embed.description",
            ),
        )

        await i.edit_original_response(embed=embed, view=self.view)

    async def _finish_cookie_setup(self, i: "INTERACTION", cookies: dict[str, str]) -> None:
        # Get ltoken_v2 and cookie_token_v2
        cookie = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
        cookies.update(cookie)
        self._client.set_cookies(cookies)

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("🎉 Welcome to Hoyo Buddy!", key="select_account.embed.title"),
            description=LocaleStr(
                "Select the accounts you want to add.",
                key="select_account.embed.description",
            ),
        )

        # Update the view to let user select the accounts to add
        accounts = await self._client.get_game_accounts()
        self.view.clear_items()
        self.view.add_item(
            AddAccountSelect(
                self.view.locale,
                self.view.translator,
                accounts=accounts,
                cookies="; ".join(f"{k}={v}" for k, v in cookies.items()),
            )
        )

        await i.edit_original_response(embed=embed, view=self.view)

        if self._login_listener_task is not None:
            self._login_listener_task.cancel()

    def _start_notif_listener(self) -> None:
        login_listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        self._login_listener_task = asyncio.create_task(
            login_listener.run({"login": self._handle_login_notifs}, notification_timeout=3)
        )

    async def _handle_login_notifs(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        if isinstance(notif, asyncpg_listen.Timeout):
            return

        user_id = notif.payload
        assert self.view.author is not None
        if user_id is None or int(user_id) != self.view.author.id:
            return
        user = await User.get(id=int(user_id))

        assert (
            self._interaction is not None
            and self.__email is not None
            and self.__password is not None
            and self._condition is not None
        )

        if self._condition is Condition.GEETEST_TRIGGERED:
            geetest = user.temp_data
            try:
                result = await self._client._app_login(
                    self.__email, self.__password, geetest=geetest
                )
            except genshin.GenshinException as e:
                if e.retcode == -3208:
                    error_embed, _ = get_error_embed(
                        InvalidEmailOrPasswordError(), self.view.locale, self.view.translator
                    )
                    return await self._interaction.followup.send(embed=error_embed, ephemeral=True)
                raise

            await self._process_app_login_result(self._interaction, result)

        elif self._condition is Condition.GEETEST_TRIGGERED_FOR_EMAIL:
            assert self._ticket is not None

            geetest = user.temp_data
            try:
                await self._client._send_verification_email(self._ticket, geetest=geetest)
            except genshin.GenshinException as e:
                if e.retcode == -3206:
                    error_embed, _ = get_error_embed(
                        VerificationCodeServiceUnavailableError(),
                        self.view.locale,
                        self.view.translator,
                    )
                    return await self._interaction.followup.send(embed=error_embed, ephemeral=True)
                raise

            await self._prompt_user_to_verify_email(self._interaction)

        elif self._condition is Condition.NEED_EMAIL_VERIFICATION:
            assert self._ticket is not None
            result = await self._client._app_login(
                self.__email, self.__password, ticket=self._ticket
            )
            await self._finish_cookie_setup(self._interaction, result)

    async def _process_app_login_result(self, i: "INTERACTION", result: dict[str, Any]) -> None:
        if "session_id" in result:
            self._condition = Condition.GEETEST_TRIGGERED
            await User.filter(id=i.user.id).update(temp_data=result)
            return await self._prompt_user_to_solve_geetest(i)

        if "risk_ticket" in result:
            mmt = await self._client._send_verification_email(result)
            if mmt is not None:
                self._condition = Condition.GEETEST_TRIGGERED_FOR_EMAIL
                self._ticket = result
                await User.filter(id=i.user.id).update(temp_data=mmt)
                return await self._prompt_user_to_solve_geetest(i)

            self._condition = Condition.NEED_EMAIL_VERIFICATION
            self._ticket = result
            return await self._prompt_user_to_verify_email(i)

        await self._finish_cookie_setup(i, result)

    async def callback(self, i: "INTERACTION") -> Any:
        modal = EmailPasswordModal(
            title=LocaleStr(
                "Enter e-mail/username and Password", key="enter_email_password_modal_title"
            )
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if modal.email.value is None or modal.password.value is None:
            return

        email = modal.email.value
        password = modal.password.value

        client = genshin.Client()
        try:
            result = await client._app_login(email, password)
        except genshin.GenshinException as e:
            if e.retcode == -3208:
                raise InvalidEmailOrPasswordError from e
            raise

        # Setup variables for the listener
        self.__email = email
        self.__password = password
        self._interaction = i

        self._start_notif_listener()
        await self._process_app_login_result(i, result)
