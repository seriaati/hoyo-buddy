from typing import TYPE_CHECKING, Any

import genshin
from discord import ButtonStyle
from tortoise import Tortoise

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import User
from hoyo_buddy.emojis import PASSWORD
from hoyo_buddy.enums import LoginPlatform

from ...components import Button, Modal, TextInput

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION


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
            label=LocaleStr("Enter verification code", key="email-verification-code.button.label"),
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

        client = genshin.Client(
            region=genshin.Region.OVERSEAS  # CN doesn't have email verification
        )
        await client._verify_email(code, genshin.models.ActionTicket(**user.temp_data))
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
    def __init__(self, platform: LoginPlatform) -> None:
        super().__init__(
            label=LocaleStr(
                "Enter e-mail/username and password", key="enter_email_password_button_label"
            ),
            emoji=PASSWORD,
            style=ButtonStyle.blurple,
        )

        self._platform = platform

    async def callback(self, i: "INTERACTION") -> Any:
        modal = EmailPasswordModal(
            title=LocaleStr(
                "Enter E-Mail/Username and Password", key="enter_email_password_button_label"
            )
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if modal.email.value is None or modal.password.value is None:
            return

        email = modal.email.value
        password = modal.password.value

        client = genshin.Client(
            region=genshin.Region.CHINESE
            if self._platform is LoginPlatform.MIYOUSHE
            else genshin.Region.OVERSEAS
        )
        result = (
            await client._app_login(email, password)
            if self._platform is LoginPlatform.HOYOLAB
            else await client._cn_web_login(email, password)
        )

        if isinstance(result, genshin.models.SessionMMT):
            await self.view.prompt_user_to_solve_geetest(i, for_code=False)
        elif isinstance(result, genshin.models.ActionTicket):
            email_result = await client._send_verification_email(result)
            if isinstance(email_result, genshin.models.SessionMMT):
                return await self.view.prompt_user_to_solve_geetest(i, for_code=True)

            user = await User.get(id=i.user.id)
            user.temp_data = result.model_dump()
            await user.save()
            await self.view.prompt_user_to_verify_email(i)
        else:
            await self.view.finish_cookie_setup(
                result.to_dict(), platform=self._platform, interaction=i
            )
