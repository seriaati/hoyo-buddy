from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
from genshin import Game

from ... import emojis
from ...bot.translator import LocaleStr, Translator
from ...db.models import AccountNotifSettings
from ...draw.main_funcs import draw_checkin_card
from ...embeds import DefaultEmbed
from ...models import DrawInput, Reward
from ...utils import get_now
from ..components import Button, GoBackButton, ToggleButton, View

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    import io

    import aiohttp
    from genshin.models import DailyRewardInfo

    from ...db.models import HoyoAccount
    from ...types import Interaction

CHECK_IN_URLS = {
    Game.GENSHIN: "https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id=e202102251931481",
    Game.HONKAI: "https://act.hoyolab.com/bbs/event/signin-bh3/index.html?act_id=e202110291205111",
    Game.STARRAIL: "https://act.hoyolab.com/bbs/event/signin/hkrpg/index.html?act_id=e202303301540311",
    Game.ZZZ: "https://act.hoyolab.com/bbs/event/signin/zzz/e202406031448091.html?act_id=e202406031448091",
}


class CheckInUI(View):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        *,
        author: discord.User | discord.Member,
        locale: discord.Locale,
        translator: Translator,
        timeout: float | None = 180,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator, timeout=timeout)
        self.account = account
        self.client = account.client
        self.client.set_lang(locale)

        self.dark_mode = dark_mode
        self._bytes_obj: io.BytesIO | None = None
        self.add_items()

    def add_items(self) -> None:
        self.add_item(CheckInButton())
        if self.client.game is not None:
            self.add_item(
                Button(
                    url=CHECK_IN_URLS[self.client.game],
                    label=LocaleStr(key="make_up_for_checkin_button_label"),
                )
            )
        self.add_item(AutoCheckInToggle(self.account.daily_checkin))
        self.add_item(NotificationSettingsButton())

    async def _get_rewards(self) -> tuple[list[Reward], DailyRewardInfo]:
        client = self.client

        monthly_rewards = await client.get_monthly_rewards()
        monthly_rewards = [
            Reward(name=r.name, amount=r.amount, index=i, claimed=False, icon=r.icon)
            for i, r in enumerate(monthly_rewards, 1)
        ]

        claimed_rewards = await client.claimed_rewards(limit=get_now().day)
        claimed_rewards = claimed_rewards[::-1]
        claimed_rewards = [r for r in claimed_rewards if r.time.month == get_now().month]

        reward_info = await client.get_reward_info()
        this_month_claim_num = reward_info.claimed_rewards

        for r in monthly_rewards[:this_month_claim_num]:
            r.claimed = True

        rewards_to_return = 3

        if this_month_claim_num < rewards_to_return:
            result = monthly_rewards[:rewards_to_return]
            next_reward = monthly_rewards[rewards_to_return]
        else:
            result = monthly_rewards[
                this_month_claim_num - rewards_to_return : this_month_claim_num
            ]

            try:
                next_reward = monthly_rewards[this_month_claim_num]
            except IndexError:
                next_reward = monthly_rewards[0]

        result.append(next_reward)
        return result, reward_info

    async def get_embed_and_image(
        self,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> tuple[DefaultEmbed, io.BytesIO]:
        rewards, info = await self._get_rewards()

        bytes_obj = await draw_checkin_card(
            DrawInput(
                dark_mode=self.dark_mode,
                locale=self.locale,
                session=session,
                filename="check-in.webp",
                executor=executor,
                loop=loop,
            ),
            rewards,
        )

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="daily_checkin_embed_title"),
            description=LocaleStr(
                key="daily_checkin_embed_description",
                day=info.claimed_rewards,
                missed=info.missed_rewards,
            ),
        )
        embed.set_image(url="attachment://check-in.webp")
        embed.add_acc_info(self.account)
        return embed, bytes_obj

    async def start(self, i: Interaction) -> None:
        await i.response.defer()
        embed, self._bytes_obj = await self.get_embed_and_image(
            i.client.session, i.client.executor, i.client.loop
        )

        self._bytes_obj.seek(0)
        file_ = discord.File(self._bytes_obj, filename="check-in.webp")
        await i.followup.send(embed=embed, file=file_, view=self)
        self.message = await i.original_response()


class CheckInButton(Button[CheckInUI]):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=LocaleStr(key="checkin_button_label"),
            emoji=emojis.FREE_CANCELLATION,
        )

    async def callback(self, i: Interaction) -> Any:
        client = self.view.client
        assert client.game is not None

        await i.response.defer()
        daily_reward = await client.claim_daily_reward()

        embed, self.view._bytes_obj = await self.view.get_embed_and_image(
            i.client.session, i.client.executor, i.client.loop
        )

        self.view._bytes_obj.seek(0)
        file_ = discord.File(self.view._bytes_obj, filename="check-in.webp")

        await i.edit_original_response(embed=embed, attachments=[file_])
        embed = client.get_daily_reward_embed(daily_reward, self.view.locale, self.view.translator, blur=True)
        await i.followup.send(embed=embed)


class AutoCheckInToggle(ToggleButton[CheckInUI]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="auto_checkin_button_label"),
            emoji=emojis.SMART_TOY,
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.account.daily_checkin = self.current_toggle
        await self.view.account.save(update_fields=("daily_checkin",))


class NotificationSettingsButton(Button[CheckInUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="notification_settings_button_label"),
            emoji=emojis.SETTINGS,
            row=1,
        )

    async def callback(self, i: Interaction) -> Any:
        await self.view.account.fetch_related("notif_settings")
        go_back_button = GoBackButton(
            self.view.children,
            self.view.get_embeds(i.message),
            self.view._bytes_obj,
        )
        self.view.clear_items()
        self.view.add_item(go_back_button)
        self.view.add_item(
            NotifyOnFailureToggle(self.view.account.notif_settings.notify_on_checkin_failure)
        )
        self.view.add_item(
            NotifyOnSuccessToggle(self.view.account.notif_settings.notify_on_checkin_success)
        )
        await i.response.edit_message(view=self.view)


class NotifyOnFailureToggle(ToggleButton[CheckInUI]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="notify_on_failure_button_label"),
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        await AccountNotifSettings.filter(account=self.view.account).update(
            notify_on_checkin_failure=self.current_toggle
        )


class NotifyOnSuccessToggle(ToggleButton[CheckInUI]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="notify_on_success_button_label"),
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        await AccountNotifSettings.filter(account=self.view.account).update(
            notify_on_checkin_success=self.current_toggle
        )
