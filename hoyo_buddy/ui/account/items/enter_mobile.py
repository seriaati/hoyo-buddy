from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import PASSWORD, PHONE

from ....embeds import DefaultEmbed
from ....enums import LoginPlatform
from ...components import Button, Modal, TextInput

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from ....bot.bot import INTERACTION


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
    def __init__(self) -> None:
        super().__init__(
            custom_id="enter_verification_code",
            label=LocaleStr(
                "Enter verification code", key="add_miyoushe_acc.enter_verification_code"
            ),
            emoji=PASSWORD,
            style=ButtonStyle.green,
        )

    async def callback(self, i: "INTERACTION") -> None:
        modal = VerifyCodeInput(
            title=LocaleStr(
                "Enter verification code", key="add_miyoushe_acc.enter_verification_code"
            )
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        cookies = await self.view.client._login_with_mobile_otp(self.view.mobile, modal.code.value)
        await self.view.finish_cookie_setup(cookies)


class EnterPhoneNumber(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="enter_mobile_number",
            label=LocaleStr("Enter phone number", key="add_miyoushe_acc.enter_mobile_number"),
            emoji=PHONE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: "INTERACTION") -> None:
        modal = PhoneNumberInput(
            title=LocaleStr("Enter phone number", key="add_miyoushe_acc.enter_mobile_number")
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        # Set up variables for the handler
        self.view.interaction = i
        self.view.platform = LoginPlatform.MIYOUSHE
        self.view.mobile = modal.mobile.value

        result = await self.view.client._send_mobile_otp(modal.mobile.value)

        if result is None:
            embed = DefaultEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr(
                    "Verification code sent",
                    key="add_miyoushe_acc.verification_code_sent",
                ),
                description=LocaleStr(
                    "Please check your phone for the verification code and click the button below to enter it.",
                    key="add_miyoushe_acc.verification_code_sent_description",
                ),
            )
            self.view.clear_items()
            self.view.add_item(EnterVerificationCode())
            await i.edit_original_response(embed=embed, view=self.view)
        else:
            self.view.start_listener()
            await self.view.process_app_login_result(result, is_mobile=True)
