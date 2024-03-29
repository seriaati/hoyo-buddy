from typing import TYPE_CHECKING, Any

from ..enums import LoginCondition, LoginPlatform, LoginResultType

if TYPE_CHECKING:
    import genshin

    from ..db.models import User


class LoginHandlerResult:
    def __init__(self, result_type: LoginResultType, data: dict[str, Any] | None = None) -> None:
        self.type = result_type
        self.data: dict[str, Any] = data or {}


class LoginHandler:
    _client: "genshin.Client"

    @classmethod
    async def _handle_geetest_triggered_for_login(
        cls, email: str, password: str, *, geetest: dict[str, Any], platform: LoginPlatform
    ) -> LoginHandlerResult:
        if platform is LoginPlatform.MIYOUSHE:
            result = await cls._client._cn_login_by_password(email, password, geetest=geetest)
        else:
            result = await cls._client._app_login(email, password, geetest=geetest)
        return LoginHandlerResult(LoginResultType.PROCESS_APP_LOGIN_RESULT, result)

    @classmethod
    async def _handle_geetest_triggered_for_email(
        cls, *, geetest: dict[str, Any], ticket: dict[str, Any]
    ) -> LoginHandlerResult:
        await cls._client._send_verification_email(ticket, geetest=geetest)
        return LoginHandlerResult(LoginResultType.PROMPT_USER_TO_VERIFY_EMAIL)

    @classmethod
    async def _handle_geetest_triggered_for_otp(
        cls, mobile: str, *, geetest: dict[str, Any]
    ) -> LoginHandlerResult:
        await cls._client._send_mobile_otp(mobile, geetest=geetest)
        return LoginHandlerResult(LoginResultType.PROMPT_USER_TO_VERIFY_EMAIL)

    @classmethod
    async def _handle_need_email_verification(
        cls, email: str, password: str, *, ticket: dict[str, Any]
    ) -> LoginHandlerResult:
        # Miyoushe doesn't have email verification
        result = await cls._client._app_login(email, password, ticket=ticket)
        return LoginHandlerResult(LoginResultType.FINISH_COOKIE_SETUP, result)

    @classmethod
    async def handle(
        cls,
        *,
        user: "User",
        email: str,
        password: str,
        mobile: str,
        ticket: dict[str, Any],
        client: "genshin.Client",
        condition: LoginCondition,
        platform: LoginPlatform,
    ) -> LoginHandlerResult:
        cls._client = client
        geetest = user.temp_data

        match condition:
            case LoginCondition.GEETEST_TRIGGERED_FOR_LOGIN:
                return await cls._handle_geetest_triggered_for_login(
                    email, password, geetest=geetest, platform=platform
                )
            case LoginCondition.GEETEST_TRIGGERED_FOR_EMAIL:
                return await cls._handle_geetest_triggered_for_email(geetest=geetest, ticket=ticket)
            case LoginCondition.GEETEST_TRIGGERED_FOR_OTP:
                return await cls._handle_geetest_triggered_for_otp(mobile, geetest=geetest)
            case LoginCondition.NEED_EMAIL_VERIFICATION:
                return await cls._handle_need_email_verification(email, password, ticket=ticket)
