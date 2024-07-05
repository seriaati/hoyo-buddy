from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

import asyncpg_listen
import genshin
from pydantic import BaseModel

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr
from ...db.models import User
from ...embeds import DefaultEmbed
from ...enums import GeetestNotifyType, Platform

if TYPE_CHECKING:
    from ...types import Interaction
    from .view import AccountManager


class EmailPswdLoginData(BaseModel):
    """Geetest is triggered for email password login."""

    email: str
    password: str


class SendEmailCodeData(BaseModel):
    """Geetest is triggered for sending email verification code."""

    email: str
    password: str
    acition_ticket: genshin.models.ActionTicket


class SendMobileOTPData(BaseModel):
    """Geetest is triggered for sending mobile OTP."""

    mobile: str


class GeetestHandler:
    """Class containing logic of handling account login after geetest is done by the user."""

    def __init__(
        self,
        *,
        view: AccountManager,
        interaction: Interaction,
        platform: Platform,
        data: EmailPswdLoginData | SendMobileOTPData | SendEmailCodeData,
    ) -> None:
        self._view = view
        self._interaction = interaction
        self._bot = interaction.client
        self._user_id = interaction.user.id

        self._platform = platform
        self._data = data

        self._client: genshin.Client | None = None

        self._total_timeout = 0
        self._max_timeout = 300  # 5 minutes

    @property
    def client(self) -> genshin.Client:
        if self._client is not None:
            return self._client
        self._client = genshin.Client(
            region=genshin.Region.CHINESE
            if self._platform is Platform.MIYOUSHE
            else genshin.Region.OVERSEAS
        )
        return self._client

    @staticmethod
    async def save_user_temp_data(user_id: int, data: dict[str, Any]) -> None:
        """Save user's temp_data to the database.

        Args:
            user_id: The user's ID.
            data: The data to save.
        """
        user = await User.get(id=user_id)
        user.temp_data = data
        await user.save()

    def start_listener(self) -> None:
        """Start listening for geetest NOTIFY."""
        if self._user_id in self._bot.login_notif_tasks:
            self._bot.login_notif_tasks.pop(self._user_id).cancel()

        listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        listener_name = f"geetest_{GeetestNotifyType.LOGIN.value}_{self._user_id}"
        self._bot.login_notif_tasks[self._user_id] = asyncio.create_task(
            listener.run(
                {listener_name: self.handle_geetest_notifs},
                notification_timeout=2,
            ),
            name=listener_name,
        )

    async def handle_geetest_notifs(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:  # noqa: PLR0912
        """Notification handler for geetest triggers."""
        if isinstance(notif, asyncpg_listen.Timeout):
            self._total_timeout += 2
            if self._total_timeout >= self._max_timeout:
                embed = DefaultEmbed(
                    self._view.locale,
                    self._view.translator,
                    title=LocaleStr(key="geeetest_verification_timeout"),
                    description=LocaleStr(key="geeetest_verification_timeout_description"),
                )
                await self._interaction.edit_original_response(embed=embed, view=None)
                self._bot.login_notif_tasks.pop(self._user_id).cancel()
            return

        user = await User.get(id=int(self._user_id))

        try:
            if isinstance(self._data, EmailPswdLoginData):
                # geetest was triggered for email password login
                result = await self.client._app_login(
                    self._data.email,
                    self._data.password,
                    mmt_result=genshin.models.SessionMMTResult(**user.temp_data),
                )
                if isinstance(result, genshin.models.ActionTicket):
                    # email verification required
                    email_result = await self.client._send_verification_email(
                        result, mmt_result=genshin.models.SessionMMTResult(**user.temp_data)
                    )
                    if isinstance(email_result, genshin.models.SessionMMT):
                        # geetest triggered for sending email verification code
                        await self.save_user_temp_data(self._user_id, email_result.dict())
                        handler = GeetestHandler(
                            view=self._view,
                            interaction=self._interaction,
                            platform=self._platform,
                            data=SendEmailCodeData(
                                email=self._data.email,
                                password=self._data.password,
                                acition_ticket=result,
                            ),
                        )
                        handler.start_listener()
                        await self._view.prompt_user_to_solve_geetest(
                            self._interaction, for_code=True
                        )
                    else:
                        await self._view.prompt_user_to_enter_email_code(
                            self._interaction,
                            email=self._data.email,
                            password=self._data.password,
                            action_ticket=result,
                        )
                else:
                    # no email verification required
                    await self._view.finish_cookie_setup(
                        result.to_dict(), platform=self._platform, interaction=self._interaction
                    )
            elif isinstance(self._data, SendEmailCodeData):
                # geetest was triggered for sending email verification code
                await self.client._send_verification_email(
                    self._data.acition_ticket,
                    mmt_result=genshin.models.SessionMMTResult(**user.temp_data),
                )
                await self._view.prompt_user_to_enter_email_code(
                    self._interaction,
                    email=self._data.email,
                    password=self._data.password,
                    action_ticket=self._data.acition_ticket,
                )
            else:  # SendMobileOTPData
                # geetest was triggered for sending mobile OTP
                result = await self.client._send_mobile_otp(
                    self._data.mobile,
                    mmt_result=genshin.models.SessionMMTResult(**user.temp_data),
                )
                await self._view.prompt_user_to_enter_mobile_otp(
                    self._interaction, self._data.mobile
                )
        except Exception as e:
            embed, recognized = get_error_embed(e, self._view.locale, self._view.translator)
            if not recognized:
                self._bot.capture_exception(e)
            await self._interaction.edit_original_response(embed=embed, view=None)
        finally:
            self._bot.login_notif_tasks.pop(self._user_id).cancel()
