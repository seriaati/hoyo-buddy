import asyncio
import os
from typing import TYPE_CHECKING, Any

import asyncpg_listen
import genshin

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr
from ...db.models import User
from ...embeds import DefaultEmbed
from ...enums import LoginCondition, LoginPlatform, LoginResultType
from ...exceptions import NoGameAccountsError, TryOtherMethodError
from ...hoyo.login_handler import LoginHandler
from ...models import LoginNotifPayload
from .. import View
from ..components import Button, GoBackButton
from .items.add_acc_select import AddAccountSelect
from .items.enter_email_pswd import EnterEmailVerificationCode

if TYPE_CHECKING:
    from ...bot.bot import INTERACTION

GEETEST_SERVERS = {
    "prod": "https://geetest-server.seriaati.xyz",
    "test": "http://geetest-server-test.seriaati.xyz",
    "dev": "http://localhost:5000",
}


class AddAccountHandler(View):
    """Class containing logic of adding game accounts to the user's account."""

    interaction: "INTERACTION"
    condition: LoginCondition
    platform: LoginPlatform
    email: str = ""
    password: str = ""
    mobile: str = ""

    _ticket: dict[str, Any] = {}  # noqa: RUF012
    _task: asyncio.Task | None = None
    _client: genshin.Client | None = None

    @property
    def client(self) -> genshin.Client:
        if self._client is not None:
            return self._client
        self._client = genshin.Client(
            region=genshin.Region.CHINESE
            if self.platform is LoginPlatform.MIYOUSHE
            else genshin.Region.OVERSEAS
        )
        return self._client

    async def on_timeout(self) -> None:
        if self._task is not None:
            self._task.cancel()
        return await super().on_timeout()

    def start_listener(self) -> None:
        login_listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        assert self.author is not None
        self._task = asyncio.create_task(
            login_listener.run({"login": self.handle_login_notifs}, notification_timeout=3),
            name=f"login_listener_{self.author.id}",
        )

    async def handle_login_notifs(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        if isinstance(notif, asyncpg_listen.Timeout):
            return

        assert notif.payload is not None
        user_id = notif.payload
        assert self.author is not None
        if int(user_id) != self.author.id:
            return
        user = await User.get(id=int(user_id))

        try:
            result = await LoginHandler.handle(
                user=user,
                email=self.email,
                password=self.password,
                mobile=self.mobile,
                client=self.client,
                condition=self.condition,
                platform=self.platform,
                ticket=self._ticket,
            )
        except Exception as e:
            embed, recognized = get_error_embed(e, self.locale, self.translator)
            if not recognized:
                self.interaction.client.capture_exception(e)
            await self.interaction.edit_original_response(embed=embed)
            return

        match result.type:
            case LoginResultType.PROCESS_APP_LOGIN_RESULT:
                await self.process_app_login_result(result.data)
            case LoginResultType.PROMPT_USER_TO_VERIFY_EMAIL:
                await self.prompt_user_to_verify_email()
            case LoginResultType.FINISH_COOKIE_SETUP:
                await self.finish_cookie_setup(result.data)

    async def finish_cookie_setup(self, cookies: dict[str, Any]) -> None:
        if self.platform is LoginPlatform.HOYOLAB and "stoken" in cookies:
            # Get ltoken_v2 and cookie_token_v2
            cookie = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
            cookies.update(cookie)

        self.client.set_cookies(cookies)

        # Update the view to let user select the accounts to add
        try:
            accounts = await self.client.get_game_accounts()
        except genshin.errors.InvalidCookies as e:
            raise TryOtherMethodError from e

        if not accounts:
            raise NoGameAccountsError(self.platform)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("🎉 Welcome to Hoyo Buddy!", key="select_account.embed.title"),
            description=LocaleStr(
                "Select the accounts you want to add.",
                key="select_account.embed.description",
            ),
        )

        self.clear_items()
        self.add_item(
            AddAccountSelect(
                self.locale,
                self.translator,
                accounts=accounts,
                cookies="; ".join(f"{k}={v}" for k, v in cookies.items()),
            )
        )

        await self.interaction.edit_original_response(embed=embed, view=self)
        if self._task is not None:
            self._task.cancel()

    async def process_app_login_result(
        self, result: dict[str, Any], *, is_mobile: bool = False
    ) -> None:
        user_id = self.interaction.user.id

        if "session_id" in result:
            self.condition = (
                LoginCondition.GEETEST_TRIGGERED_FOR_OTP
                if is_mobile
                else LoginCondition.GEETEST_TRIGGERED_FOR_LOGIN
            )
            await User.filter(id=user_id).update(temp_data=result)
            return await self.prompt_user_to_solve_geetest()

        if "risk_ticket" in result:
            mmt = await self.client._send_verification_email(result)
            if mmt is not None:
                self.condition = LoginCondition.GEETEST_TRIGGERED_FOR_EMAIL
                self._ticket = result
                await User.filter(id=user_id).update(temp_data=mmt)
                return await self.prompt_user_to_solve_geetest()

            self.condition = LoginCondition.NEED_EMAIL_VERIFICATION
            self._ticket = result
            return await self.prompt_user_to_verify_email()

        await self.finish_cookie_setup(result)

    async def prompt_user_to_solve_geetest(self) -> None:
        i = self.interaction
        assert i.channel is not None and i.message is not None
        payload = LoginNotifPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild else None,
            channel_id=i.channel.id,
            message_id=i.message.id,
            locale=self.locale.value,
        )
        url = f"{GEETEST_SERVERS[i.client.env]}/captcha?{payload.to_query_string()}"

        go_back_button = GoBackButton(self.children, self.get_embeds(i.message))
        self.clear_items()
        self.add_item(
            Button(
                label=LocaleStr("Complete CAPTCHA", key="complete_captcha_button_label"), url=url
            )
        )
        self.add_item(go_back_button)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(
                "😥 Need to solve CAPTCHA before sending the verification code",
                key="email-geetest.embed.title",
            )
            if self.condition
            in {
                LoginCondition.GEETEST_TRIGGERED_FOR_EMAIL,
                LoginCondition.GEETEST_TRIGGERED_FOR_OTP,
            }
            else LocaleStr("😅 Need to solve CAPTCHA before logging in", key="geetest.embed.title"),
            description=LocaleStr(
                "Click on the button below to complete CAPTCHA.\n",
                key="captcha.embed.description",
            ),
        )
        await i.edit_original_response(embed=embed, view=self)

    async def prompt_user_to_verify_email(self) -> None:
        go_back_button = GoBackButton(self.children, self.get_embeds(self.interaction.message))
        self.clear_items()
        self.add_item(EnterEmailVerificationCode())
        self.add_item(go_back_button)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
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

        await self.interaction.edit_original_response(embed=embed, view=self)
