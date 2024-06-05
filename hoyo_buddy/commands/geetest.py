from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import asyncpg_listen
import genshin

from ..bot.error_handler import get_error_embed
from ..bot.translator import LocaleStr
from ..constants import GEETEST_SERVERS
from ..db.models import HoyoAccount, User, get_locale
from ..embeds import DefaultEmbed
from ..models import LoginNotifPayload
from ..ui.components import URLButtonView

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy


class GeetestCommand:
    def __init__(self, bot: HoyoBuddy, i: INTERACTION, account: HoyoAccount) -> None:
        self._bot = bot
        self._interaction = i
        self._account = account
        self._locale = i.locale

        self._total_timeout = 0
        self._max_timeout = 300  # 5 minutes

    def start_listener(self) -> None:
        """Start listening for geetest NOTIFY."""
        i = self._interaction

        if i.user.id in self._bot.login_notif_tasks:
            self._bot.login_notif_tasks.pop(i.user.id).cancel()

        listener = asyncpg_listen.NotificationListener(
            asyncpg_listen.connect_func(os.environ["DB_URL"])
        )
        self._bot.login_notif_tasks[i.user.id] = asyncio.create_task(
            listener.run({"geetest": self._handle_notif}, notification_timeout=2),
            name=f"geetest_command_listener{i.user.id}",
        )

    async def _handle_notif(self, notif: asyncpg_listen.NotificationOrTimeout) -> None:
        i = self._interaction

        if isinstance(notif, asyncpg_listen.Timeout):
            self._total_timeout += 2
            if self._total_timeout >= self._max_timeout:
                embed = DefaultEmbed(
                    self._locale,
                    i.client.translator,
                    title=LocaleStr("Verification timeout", key="geeetest_verification_timeout"),
                    description=LocaleStr(
                        "The verification has timed out. Please use the </geetest> comand to try again.",
                        key="geeetest_verification_timeout_description",
                    ),
                )
                await i.edit_original_response(embed=embed, view=None)
                self._bot.login_notif_tasks.pop(i.user.id).cancel()
            return

        try:
            assert notif.payload is not None
            user_id = notif.payload
            if int(user_id) != i.user.id:
                return

            user = await User.get(id=i.user.id)
            result = user.temp_data

            client = self._account.client
            await client.verify_mmt(genshin.models.MMTResult(**result))

            embed = DefaultEmbed(
                self._locale,
                i.client.translator,
                title=LocaleStr("Verification complete", key="geeetest_verification_complete"),
            )
            await i.edit_original_response(embed=embed, view=None)
        except Exception as e:
            embed, recognized = get_error_embed(e, self._locale, self._bot.translator)
            if not recognized:
                self._bot.capture_exception(e)
            await i.edit_original_response(embed=embed, view=None)
        finally:
            self._bot.login_notif_tasks.pop(i.user.id).cancel()

    async def run(self) -> None:
        i = self._interaction
        await i.response.defer()
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
        url = f"{GEETEST_SERVERS[i.client.env]}/captcha?{payload.to_query_string()}"

        view = URLButtonView(
            i.client.translator,
            self._locale,
            url=url,
            label=LocaleStr("Complete geetest", key="complete_geetest_button_label"),
        )

        embed = DefaultEmbed(
            self._locale,
            i.client.translator,
            title=LocaleStr("Complete geetest", key="complete_geetest_button_label"),
            description=LocaleStr(
                "Click the button below to complete the geetest verification",
                key="complete_geetest_button_description",
            ),
        ).add_acc_info(self._account)

        await i.followup.send(embed=embed, view=view, ephemeral=True)
