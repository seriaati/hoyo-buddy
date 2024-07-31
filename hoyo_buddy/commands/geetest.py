from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import asyncpg_listen
import genshin

from ..bot.error_handler import get_error_embed
from ..constants import GEETEST_SERVERS
from ..db.models import HoyoAccount, User, get_locale
from ..embeds import DefaultEmbed
from ..enums import GeetestNotifyType, GeetestType, Platform
from ..exceptions import FeatureNotImplementedError
from ..l10n import LocaleStr
from ..models import LoginNotifPayload
from ..ui import URLButtonView

if TYPE_CHECKING:
    from discord import Message

    from ..bot import HoyoBuddy
    from ..types import Interaction


class GeetestCommand:
    def __init__(
        self, bot: HoyoBuddy, i: Interaction, account: HoyoAccount, type_: GeetestType
    ) -> None:
        self._bot = bot
        self._interaction = i
        self._user_id = i.user.id
        self._account = account
        self._locale = i.locale
        self._type = type_

        self._total_timeout = 0
        self._max_timeout = 300  # 5 minutes
        self._message: Message | None = None

    def start_listener(self) -> None:
        """Start listening for geetest NOTIFY."""
        i = self._interaction

        if i.user.id in self._bot.login_notif_tasks:
            self._bot.login_notif_tasks.pop(i.user.id).cancel()

        listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        listener_name = f"geetest_{GeetestNotifyType.COMMAND.value}_{self._user_id}"
        self._bot.login_notif_tasks[i.user.id] = asyncio.create_task(
            listener.run(
                {listener_name: self._handle_notif},
                notification_timeout=2,
            ),
            name=listener_name,
        )

    async def _handle_notif(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        assert self._message is not None
        translator = self._bot.translator

        if isinstance(notif, asyncpg_listen.Timeout):
            self._total_timeout += 2
            if self._total_timeout >= self._max_timeout:
                embed = DefaultEmbed(
                    self._locale,
                    translator,
                    title=LocaleStr(key="geeetest_verification_timeout"),
                    description=LocaleStr(key="geeetest_verification_timeout_description"),
                )
                await self._message.edit(embed=embed, view=None)
                self._bot.login_notif_tasks.pop(self._user_id).cancel()
            return

        try:
            user = await User.get(id=self._user_id)
            result = user.temp_data

            client = self._account.client
            if self._type is GeetestType.DAILY_CHECKIN:
                reward = await client.claim_daily_reward(
                    challenge={
                        "challenge": result["geetest_challenge"],
                        "seccode": result["geetest_seccode"],
                        "validate": result["geetest_validate"],
                    }
                )
                embed = client.get_daily_reward_embed(reward, self._locale, translator, blur=True)
            else:
                await client.verify_mmt(genshin.models.MMTResult(**result))
                embed = DefaultEmbed(
                    self._locale,
                    translator,
                    title=LocaleStr(key="geeetest_verification_complete"),
                )

            await self._message.edit(embed=embed, view=None)
        except Exception as e:
            embed, recognized = get_error_embed(e, self._locale, self._bot.translator)
            if not recognized:
                self._bot.capture_exception(e)
            await self._message.edit(embed=embed, view=None)
        finally:
            self._bot.login_notif_tasks.pop(self._user_id).cancel()

    async def run(self) -> None:
        if self._account.platform is not Platform.HOYOLAB:
            raise FeatureNotImplementedError(
                platform=self._account.platform, game=self._account.game
            )

        i = self._interaction
        assert i.channel is not None

        self._locale = await get_locale(i)

        client = self._account.client
        client.set_lang(i.locale)
        mmt = await client.create_mmt()

        # Save mmt to db
        user = await User.get(id=i.user.id)
        user.temp_data = mmt.dict()
        await user.save()

        payload = LoginNotifPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild is not None else None,
            channel_id=i.channel.id,
            message_id=i.message.id if i.message is not None else None,
            gt_version=3,
            api_server="api.geetest.com",
        )
        url = f"{GEETEST_SERVERS[i.client.env]}/captcha?{payload.to_query_string()}&gt_type={GeetestNotifyType.COMMAND.value}"

        view = URLButtonView(
            i.client.translator,
            self._locale,
            url=url,
            label=LocaleStr(key="complete_geetest_button_label"),
        )

        embed = DefaultEmbed(
            self._locale,
            i.client.translator,
            title=LocaleStr(key="complete_geetest_button_label"),
            description=LocaleStr(key="complete_geetest_button_description"),
        ).add_acc_info(self._account)

        await i.followup.send(embed=embed, view=view, ephemeral=True)
        self._message = await i.original_response()
