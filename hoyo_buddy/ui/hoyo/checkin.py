import asyncio
import io
from typing import Any, Optional, Sequence, Tuple, Union

import aiohttp
import discord
from discord.interactions import Interaction
from genshin import Game, GenshinException
from genshin.models import ClaimedDailyReward, DailyReward

from ...bot import HoyoBuddy, Translator, emojis
from ...bot import locale_str as _T
from ...bot.error_handler import get_error_embed
from ...db.models import HoyoAccount
from ...draw import checkin
from ...draw.static import download_and_save_static_images
from ...embeds import DefaultEmbed
from ...hoyo.reward_calc import RewardCalculator
from ...utils import get_now
from ..ui import Button, GoBackButton, ToggleButton, View

CHECK_IN_URLS = {
    Game.GENSHIN: "https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id=e202102251931481",
    Game.HONKAI: "https://act.hoyolab.com/bbs/event/signin-bh3/index.html?act_id=e202110291205111",
    Game.STARRAIL: "https://act.hoyolab.com/bbs/event/signin/hkrpg/index.html?act_id=e202303301540311",
}


class CheckInUI(View):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        *,
        author: Union[discord.User, discord.Member],
        locale: discord.Locale,
        translator: Translator,
        timeout: Optional[float] = 180,
    ):
        super().__init__(author=author, locale=locale, translator=translator, timeout=timeout)
        self.account = account
        self.client = account.client
        self.dark_mode = dark_mode
        self.add_items()

    def add_items(self) -> None:
        if self.client.game is None:
            raise AssertionError("Client game is None")
        self.add_item(CheckInButton())
        self.add_item(
            Button(
                url=CHECK_IN_URLS[self.client.game],
                label=_T("Make up for check-in", key="make_up_for_checkin_button_label"),
            )
        )
        self.add_item(AutoCheckInToggle(self.account.daily_checkin))
        self.add_item(NotificationSettingsButton())

    @staticmethod
    async def _draw_checkin_image(
        rewards: Tuple[DailyReward, ...],
        dark_mode: bool,
        session: aiohttp.ClientSession,
    ) -> io.BytesIO:
        await download_and_save_static_images([r.icon for r in rewards], "check-in", session)
        return await asyncio.to_thread(checkin.draw_card, rewards, dark_mode)

    @staticmethod
    def _calc_valuable_amount(claimed_rewards: Sequence[ClaimedDailyReward]) -> int:
        return sum(
            r.amount for r in claimed_rewards if r.name in ("Primogem", "Crystal", "Stellar Jade")
        )

    @staticmethod
    def _calc_missed_days(claimed_rewards: Sequence[ClaimedDailyReward]) -> int:
        now = get_now()
        missed = now.day - len(claimed_rewards)
        return missed

    async def get_image_embed_and_file(
        self, session: aiohttp.ClientSession
    ) -> Tuple[DefaultEmbed, discord.File]:
        monthly_rewards = await self.client.get_monthly_rewards()
        claimed_rewards = await self.client.claimed_rewards()
        reward_calculator = RewardCalculator(claimed_rewards, monthly_rewards)
        rewards = reward_calculator.get_rewards()

        fp = await self._draw_checkin_image(rewards, self.dark_mode, session)
        fp.seek(0)
        file_ = discord.File(fp, filename="check-in.png")

        if self.client.game == Game.GENSHIN:
            valuable_name = _T("primogems", warn_no_key=False)
        elif self.client.game == Game.HONKAI:
            valuable_name = _T("crystals", warn_no_key=False)
        else:  # Game.STARRAIL
            valuable_name = _T("stellar jades", warn_no_key=False)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=_T("Daily Check-in", key="daily_checkin_embed_title"),
            description=_T(
                (
                    "Claimed {amount} {valuable_name} so far\n"
                    "Checked in {day} day(s) this month\n"
                    "Missed check-in for {missed} day(s)\n"
                ),
                key="daily_checkin_embed_description",
                amount=self._calc_valuable_amount(claimed_rewards),
                valuable_name=valuable_name,
                day=reward_calculator.claimed_amount,
                missed=get_now().day - reward_calculator.claimed_amount,
            ),
        )
        embed.set_image(url="attachment://check-in.png")
        return embed, file_

    async def start(self, i: discord.Interaction[HoyoBuddy]):
        await i.response.defer()
        embed, file_ = await self.get_image_embed_and_file(i.client.session)
        await i.followup.send(embed=embed, file=file_, view=self)
        self.message = await i.original_response()


class BackButton(Button):
    def __init__(self):
        super().__init__(emoji=emojis.BACK, row=4)

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI

        await self.set_loading_state(i)
        embed, file_ = await self.view.get_image_embed_and_file(i.client.session)
        self.view.clear_items()
        self.view.add_items()
        await i.edit_original_response(embed=embed, attachments=[file_], view=self.view)


class CheckInButton(Button):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=_T("Check-in", key="checkin_button_label"),
            emoji=emojis.FREE_CANCELLATION,
        )

    async def callback(self, i: discord.Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI

        await self.set_loading_state(i)
        client = self.view.client
        if client.game is None:
            raise AssertionError("Client game is None")

        self.view.clear_items()
        self.view.add_item(BackButton())

        try:
            daily_reward = await client.claim_daily_reward()
        except GenshinException as e:
            embed, _ = get_error_embed(e, self.view.locale, self.view.translator)
            return await i.edit_original_response(embed=embed, attachments=[], view=self.view)

        embed = client.get_daily_reward_embed(
            daily_reward, client.game, self.view.locale, self.view.translator
        )
        await i.edit_original_response(embed=embed, attachments=[], view=self.view)


class AutoCheckInToggle(ToggleButton):
    def __init__(self, current_toggle: bool):
        super().__init__(
            current_toggle,
            _T("Auto check-in", key="auto_checkin_button_label"),
            emoji=emojis.SMART_TOY,
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI
        await super().callback(i)
        self.view.account.daily_checkin = self.current_toggle
        await self.view.account.save()


class NotificationSettingsButton(Button):
    def __init__(self):
        super().__init__(
            label=_T("Notification settings", key="notification_settings_button_label"),
            emoji=emojis.SETTINGS,
            row=1,
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI
        await self.view.account.fetch_related("notif_settings")
        go_back_button = GoBackButton(
            self.view.children,
            self.view.get_embeds(i.message),
            self.view.get_attachments(i.message),
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


class NotifyOnFailureToggle(ToggleButton):
    def __init__(self, current_toggle: bool):
        super().__init__(
            current_toggle,
            _T("Notify on check-in failure", key="notify_on_failure_button_label"),
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI
        await super().callback(i)
        self.view.account.notif_settings.notify_on_checkin_failure = self.current_toggle
        await self.view.account.notif_settings.save()


class NotifyOnSuccessToggle(ToggleButton):
    def __init__(self, current_toggle: bool):
        super().__init__(
            current_toggle,
            _T("Notify on check-in success", key="notify_on_success_button_label"),
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI
        await super().callback(i)
        self.view.account.notif_settings.notify_on_checkin_success = self.current_toggle
        await self.view.account.notif_settings.save()
