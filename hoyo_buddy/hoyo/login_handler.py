from enum import IntEnum
from typing import TYPE_CHECKING, Any

import genshin

from ..exceptions import InvalidEmailOrPasswordError, VerCodeServiceDownError

if TYPE_CHECKING:
    from ..db.models import User


class LoginResultType(IntEnum):
    PROCESS_APP_LOGIN_RESULT = 0
    PROMPT_USER_TO_VERIFY_EMAIL = 1
    FINISH_COOKIE_SETUP = 2


class LoginCondition(IntEnum):
    GEETEST_TRIGGERED = 1
    GEETEST_TRIGGERED_FOR_EMAIL = 2
    NEED_EMAIL_VERIFICATION = 3


class LoginHandlerResult:
    def __init__(self, result_type: LoginResultType, data: dict[str, Any] | None = None) -> None:
        self.type = result_type
        self.data: dict[str, Any] = data or {}


class LoginHandler:
    _client: genshin.Client

    @classmethod
    async def _handle_geetest_triggered(
        cls, geetest: dict[str, Any], email: str, password: str
    ) -> LoginHandlerResult:
        result = await cls._client._app_login(email, password, geetest=geetest)
        return LoginHandlerResult(LoginResultType.PROCESS_APP_LOGIN_RESULT, result)

    @classmethod
    async def _handle_geetest_triggered_for_email(
        cls, geetest: dict[str, Any], ticket: dict[str, Any]
    ) -> LoginHandlerResult:
        await cls._client._send_verification_email(ticket, geetest=geetest)
        return LoginHandlerResult(LoginResultType.PROMPT_USER_TO_VERIFY_EMAIL)

    @classmethod
    async def _handle_need_email_verification(
        cls, ticket: dict[str, Any], email: str, password: str
    ) -> LoginHandlerResult:
        result = await cls._client._app_login(email, password, ticket=ticket)
        return LoginHandlerResult(LoginResultType.FINISH_COOKIE_SETUP, result)

    @classmethod
    async def handle(
        cls,
        user: "User",
        email: str,
        password: str,
        client: genshin.Client,
        condition: LoginCondition,
    ) -> LoginHandlerResult:
        cls._client = client

        try:
            match condition:
                case LoginCondition.GEETEST_TRIGGERED:
                    return await cls._handle_geetest_triggered(user.temp_data, email, password)
                case LoginCondition.GEETEST_TRIGGERED_FOR_EMAIL:
                    return await cls._handle_geetest_triggered_for_email(
                        user.temp_data, user.temp_data
                    )
                case LoginCondition.NEED_EMAIL_VERIFICATION:
                    return await cls._handle_need_email_verification(
                        user.temp_data, email, password
                    )
        except genshin.GenshinException as e:
            if e.retcode in {-3208, -3203}:
                raise InvalidEmailOrPasswordError from e
            elif e.retcode == -3206:
                raise VerCodeServiceDownError from e
            else:
                raise
        except Exception:
            raise
        finally:
            user.temp_data.clear()
            await user.save()
