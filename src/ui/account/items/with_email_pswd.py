import asyncio
import os
from enum import IntEnum
from typing import TYPE_CHECKING, Any

import asyncpg_listen
import genshin
from discord import ButtonStyle

from src.bot.translator import LocaleStr
from src.embeds import DefaultEmbed, ErrorEmbed
from src.emojis import PASSWORD

from ....db.models import User
from ....hoyo.dataclasses import LoginNotifPayload
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


class Condition(IntEnum):
    GEETEST_TRIGGERED = 1
    GEETEST_TRIGGERED_FOR_EMAIL = 2
    NEED_EMAIL_VERIFICATION = 3
    AFTER_GEETEST_TRIGGERED_FOR_EMAIL = 4


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
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                "Click the button below to complete CAPTCHA.\n",
                key="email_password_instructions_description",
            ),
        )
        await i.edit_original_response(embed=embed, view=self.view)

    async def _prompt_user_to_verify_email(self, i: "INTERACTION") -> None:
        assert i.channel is not None and i.message is not None
        payload = LoginNotifPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild else None,
            channel_id=i.channel.id,
            message_id=i.message.id,
            locale=self.view.locale.value,
        )
        url = f"{GEETEST_SERVER_URL[i.client.env]}/verify-email?{payload.to_query_string()}"

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(
            Button(
                label=LocaleStr("Enter Verification Code", key="login.enter_code.button.label"),
                url=url,
            )
        )
        self.view.add_item(go_back_button)

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    "1. Go to the email associated with this account and find the verification code.\n"
                    "2. Click the button below, enter the code in the website's input box.\n"
                ),
                key="login.enter_code.instructions.description",
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
            title=LocaleStr("🎉 Nice! We're almost done", key="select_account.embed.title"),
            description=LocaleStr(
                "Now, select the accounts you want to add to Hoyo Buddy.",
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

    async def _handle_login_notifs(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        if isinstance(notif, asyncpg_listen.Timeout):
            return

        user_id = notif.payload
        if user_id is None or int(user_id) != self.view.author.id:
            return

        user = await User.get(id=int(user_id))
        assert self._interaction is not None

        if self._condition in {Condition.GEETEST_TRIGGERED, Condition.NEED_EMAIL_VERIFICATION}:
            assert self.__email is not None and self.__password is not None

            client = genshin.Client()
            result = await client._app_login(self.__email, self.__password, geetest=user.temp_data)
            await self._finish_cookie_setup(self._interaction, result)

        elif self._condition is Condition.GEETEST_TRIGGERED_FOR_EMAIL:
            await self._prompt_user_to_solve_geetest(self._interaction)
            self._condition = Condition.AFTER_GEETEST_TRIGGERED_FOR_EMAIL

        elif self._condition is Condition.AFTER_GEETEST_TRIGGERED_FOR_EMAIL:
            assert self._ticket is not None
            await self._client._send_verification_email(self._ticket, geetest=user.temp_data)
            await self._prompt_user_to_verify_email(self._interaction)
            self._condition = Condition.NEED_EMAIL_VERIFICATION

        if self._login_listener_task is not None:
            self._login_listener_task.cancel()

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

        client = genshin.Client()
        try:
            result = await client._app_login(email, password)
        except genshin.GenshinException as e:
            if e.retcode == -3208:
                embed = ErrorEmbed(
                    self.view.locale,
                    self.view.translator,
                    title=LocaleStr(
                        "Invalid email or password", key="invalid_email_password_title"
                    ),
                    description=LocaleStr(
                        "Either your email or password is incorrect, please try again.",
                        key="invalid_email_password_description",
                    ),
                )
                return await i.edit_original_response(embed=embed)
            else:
                raise

        # Setup variables for the listener
        self.__email = email
        self.__password = password
        self._interaction = i

        # Star the listener
        login_listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        self._login_listener_task = asyncio.create_task(
            login_listener.run({"login": self._handle_login_notifs}, notification_timeout=3)
        )

        # Determine condition
        if "session_id" in result:
            self._condition = Condition.GEETEST_TRIGGERED
            self.view.user.temp_data = result
            await self.view.user.save()
            await self._prompt_user_to_solve_geetest(i)
        elif "risk_ticket" in result:
            mmt = await client._send_verification_email(result)
            if mmt is not None:
                self._condition = Condition.GEETEST_TRIGGERED_FOR_EMAIL
                self._ticket = result
                self.view.user.temp_data = mmt
                await self.view.user.save()
                await self._prompt_user_to_solve_geetest(i)
            else:
                self._condition = Condition.NEED_EMAIL_VERIFICATION
                await self._client._send_verification_email(result)
                await self._prompt_user_to_verify_email(self._interaction)
        else:
            await self._finish_cookie_setup(i, result)


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
                    "This method requires you to enter your private information.\n"
                    "In exchange, your `cookie_token` can be refreshed automatically, which is used in features like automatic code redemption.\n"
                    "Your email and password are not saved in the database AT ALL, so it is practically impossible for them to be leaked.\n"
                    "Additionally, this bot is open-sourced on [GitHub](https://github.com/seriaati/hoyo-buddy), so you can verify that yourself.\n"
                    "It is ultimately your choice to decide whether to trust this bot or not.\n\n"
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
