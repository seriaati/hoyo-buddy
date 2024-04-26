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


class AddAccountHandler:
    """Class containing logic of adding game accounts to the user's account."""

    def __init__(
        self,
        user_id: int,
        email: str | None = None,
        password: str | None = None,
        mobile: str | None = None,
    ) -> None:
        self._user_id = user_id

        self._email = email
        self._password = password
        self._mobile = mobile

        self._ticket: dict[str, Any] = {}
        self._task: asyncio.Task | None = None
        self._client: genshin.Client | None = None

    interaction: "INTERACTION"
    condition: LoginCondition
    platform: LoginPlatform

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

    def start_listener(self) -> None:
        login_listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        self._task = asyncio.create_task(
            login_listener.run({"login": self.handle_login_notifs}, notification_timeout=3),
            name=f"login_listener_{self._user_id}",
        )

    async def handle_login_notifs(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        if isinstance(notif, asyncpg_listen.Timeout):
            return

        assert notif.payload is not None
        user_id = notif.payload
        if int(user_id) != self._user_id:
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
