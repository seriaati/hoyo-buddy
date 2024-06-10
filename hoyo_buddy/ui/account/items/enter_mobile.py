from __future__ import annotations

from typing import TYPE_CHECKING

import genshin
from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import PASSWORD, PHONE
from hoyo_buddy.enums import Platform

from ...components import Button, Modal, TextInput
from ..geetest_handler import GeetestHandler, SendMobileOTPData

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import AccountManager  # noqa: F401


class VerifyCodeInput(Modal):
    code = TextInput(
        label=LocaleStr("Verification code", key="add_miyoushe_acc.verify_code"),
        placeholder="123456",
    )


class PhoneNumberInput(Modal):
    mobile = TextInput(
        label=LocaleStr("Phone number", key="add_miyoushe_acc.mobile_number"),
        placeholder="1234567890",
    )


class EnterVerificationCode(Button["AccountManager"]):
    def __init__(self, mobile: str) -> None:
        super().__init__(
            custom_id="enter_verification_code",
            label=LocaleStr(
                "Enter verification code", key="add_miyoushe_acc.enter_verification_code"
            ),
            emoji=PASSWORD,
            style=ButtonStyle.green,
        )
        self._mobile = mobile

    async def callback(self, i: Interaction) -> None:
        modal = VerifyCodeInput(
            title=LocaleStr(
                "Enter Verification Code", key="add_miyoushe_acc.enter_verification_code"
            )
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        client = genshin.Client(region=genshin.Region.CHINESE)  # OS doesn't have mobile OTP login
        cookies = await client._login_with_mobile_otp(self._mobile, modal.code.value)
        await self.view.finish_cookie_setup(
            cookies.to_dict(), platform=Platform.MIYOUSHE, interaction=i
        )


class EnterPhoneNumber(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="enter_mobile_number",
            label=LocaleStr("Enter phone number", key="add_miyoushe_acc.enter_mobile_number"),
            emoji=PHONE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        modal = PhoneNumberInput(
            title=LocaleStr("Enter Phone Number", key="add_miyoushe_acc.enter_mobile_number")
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        mobile = modal.mobile.value

        client = genshin.Client(region=genshin.Region.CHINESE)  # OS doesn't have mobile OTP login
        result = await client._send_mobile_otp(mobile)

        if isinstance(result, genshin.models.SessionMMT):
            await GeetestHandler.save_user_temp_data(i.user.id, result.dict())
            handler = GeetestHandler(
                view=self.view,
                interaction=i,
                platform=Platform.MIYOUSHE,
                data=SendMobileOTPData(mobile=mobile),
            )
            handler.start_listener()
            await self.view.prompt_user_to_solve_geetest(i, for_code=True, gt_version=4)
        else:
            await self.view.prompt_user_to_enter_mobile_otp(i, mobile)
