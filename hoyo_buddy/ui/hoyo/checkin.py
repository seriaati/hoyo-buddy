import asyncio
import calendar
import io
from datetime import datetime, timedelta
from typing import Any, ClassVar, List, Optional, Sequence, Tuple, Union

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
from ...utils import get_now
from ..ui import Button, GoBackButton, View

CHECK_IN_URLS = {
    Game.GENSHIN: "https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id=e202102251931481",
    Game.HONKAI: "https://act.hoyolab.com/bbs/event/signin-bh3/index.html?act_id=e202110291205111",
    Game.STARRAIL: "https://act.hoyolab.com/bbs/event/signin/hkrpg/index.html?act_id=e202303301540311",
}


class RewardCalculator:
    _now: ClassVar[datetime]
    _claimed_rewards: ClassVar[Sequence[ClaimedDailyReward]]
    _mora: ClassVar[DailyReward]
    _last_month: ClassVar[int]

    @classmethod
    def _change_reward_name(
        cls, name: str, reward: Union[ClaimedDailyReward, DailyReward]
    ) -> DailyReward:
        return DailyReward(name=name, amount=reward.amount, icon=reward.icon)

    @classmethod
    def _get_claim_status(
        cls,
        day: int,
        rewards: Sequence[ClaimedDailyReward],
    ) -> str:
        return "claimed" if any((r.time.day == day for r in rewards)) else "unclaimed"

    @classmethod
    def _get_last_month_data(cls) -> Tuple[int, int]:
        last_month = cls._now - timedelta(days=cls._now.day)
        return (
            last_month.month,
            calendar.monthrange(last_month.year, last_month.month)[1],
        )

    @classmethod
    def _get_mora_with_claim_status(
        cls,
        day: int,
    ) -> DailyReward:
        return cls._change_reward_name(
            f"{cls._get_claim_status(day, cls._claimed_rewards)}_{cls._last_month}/{day}",
            cls._mora,
        )

    @classmethod
    def exec(
        cls,
        monthly_rewards: Sequence[DailyReward],
        claimed_rewards: Sequence[ClaimedDailyReward],
    ) -> Tuple[DailyReward, ...]:
        # initialization
        cls._now = get_now()
        cls._claimed_rewards = claimed_rewards
        cls._mora = monthly_rewards[2]
        now_month = cls._now.month
        last_month, last_month_days = cls._get_last_month_data()
        cls._last_month = last_month
        this_month_claimed_rewards = [
            r for r in claimed_rewards if r.time.month == cls._now.month
        ][::-1]

        if not this_month_claimed_rewards:
            return (
                cls._get_mora_with_claim_status(last_month_days - 1),
                cls._get_mora_with_claim_status(last_month_days),
                cls._change_reward_name(f"{now_month}/1", monthly_rewards[0]),
                cls._change_reward_name(f"{now_month}/2", monthly_rewards[1]),
            )

        last_claimed = this_month_claimed_rewards[-1]
        claim_index = last_claimed.time.day - 1
        last_claimed_daily_reward = cls._change_reward_name(
            f"{cls._get_claim_status(cls._now.day, this_month_claimed_rewards)}_{last_claimed.time.month}/{last_claimed.time.day}",
            last_claimed,
        )

        if claim_index < 2:
            if claim_index == 0:  # claimed reward on first day of month
                return (
                    cls._get_mora_with_claim_status(last_month_days - 1),
                    cls._get_mora_with_claim_status(last_month_days),
                    last_claimed_daily_reward,
                    cls._change_reward_name("2", monthly_rewards[1]),
                )
            # claimed reward on second day of month
            return (
                cls._get_mora_with_claim_status(last_month_days),
                cls._change_reward_name(f"claimed_{now_month}/1", monthly_rewards[0]),
                last_claimed_daily_reward,
                cls._change_reward_name(f"{now_month}/3", monthly_rewards[2]),
            )

        if (
            claim_index == len(monthly_rewards) - 1
        ):  # claimed reward on last day of month
            return (
                cls._change_reward_name(
                    f"{now_month}/{claim_index - 1}", monthly_rewards[claim_index - 2]
                ),
                cls._change_reward_name(
                    f"{now_month}/{claim_index}", monthly_rewards[claim_index - 1]
                ),
                last_claimed_daily_reward,
                cls._change_reward_name(f"{now_month+1}/1", monthly_rewards[0]),
            )
        return (
            cls._change_reward_name(
                f"{now_month}/{claim_index - 1}", monthly_rewards[claim_index - 2]
            ),
            cls._change_reward_name(
                f"{now_month}/{claim_index}", monthly_rewards[claim_index - 1]
            ),
            last_claimed_daily_reward,
            cls._change_reward_name(
                f"{now_month}/{claim_index + 2}", monthly_rewards[claim_index + 1]
            ),
        )


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
        super().__init__(
            author=author, locale=locale, translator=translator, timeout=timeout
        )
        self.account = account
        self.client = account.client
        self.dark_mode = dark_mode
        self._add_items()

    def _add_items(self) -> None:
        if self.client.game is None:
            raise AssertionError("Client game is None")
        self.add_item(CheckInButton())
        self.add_item(
            Button(
                url=CHECK_IN_URLS[self.client.game],
                label=_T(
                    "Make up for check-in", key="make_up_for_checkin_button_label"
                ),
            )
        )
        self.add_item(AutoCheckInToggle(self.account.daily_checkin))
        self.add_item(NotificationSettingsButton())

    async def _draw_checkin_image(
        self,
        rewards: Tuple[DailyReward, ...],
        dark_mode: bool,
        session: aiohttp.ClientSession,
    ) -> io.BytesIO:
        await download_and_save_static_images(
            [r.icon for r in rewards], "check-in", session
        )
        return await asyncio.to_thread(checkin.draw, rewards, dark_mode)

    def _calc_valuable_amount(
        self, claimed_rewards: Sequence[ClaimedDailyReward]
    ) -> int:
        return sum(
            (
                r.amount
                for r in claimed_rewards
                if r.name in ("Primogem", "Crystal", "Stellar Jade")
            )
        )

    def _calc_missed_days(self, claimed_rewards: Sequence[ClaimedDailyReward]) -> int:
        now = get_now()
        missed = now.day - len(claimed_rewards)
        return missed

    async def _get_image_embed_and_file(
        self, session: aiohttp.ClientSession
    ) -> Tuple[DefaultEmbed, discord.File]:
        monthly_rewards = await self.client.get_monthly_rewards()
        claimed_rewards = await self.client.claimed_rewards()
        rewards = RewardCalculator.exec(monthly_rewards, claimed_rewards)
        now = get_now()
        claimed_rewards = [c for c in claimed_rewards if c.time.month == now.month]

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
                day=len(claimed_rewards),
                missed=self._calc_missed_days(claimed_rewards),
            ),
        )
        embed.set_image(url="attachment://check-in.png")
        return embed, file_

    async def start(self, i: discord.Interaction[HoyoBuddy]):
        await i.response.defer()
        embed, file_ = await self._get_image_embed_and_file(i.client.session)
        await i.followup.send(embed=embed, file=file_, view=self)
        self.message = await i.original_response()


class BackButton(Button):
    def __init__(self):
        super().__init__(emoji=emojis.BACK, row=4)

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI

        await self.set_loading_state(i)
        embed, file_ = await self.view._get_image_embed_and_file(i.client.session)
        self.view.clear_items()
        self.view._add_items()
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
            embed = get_error_embed(e, self.view.locale, self.view.translator)
            return await i.edit_original_response(
                embed=embed, attachments=[], view=self.view
            )

        embed = client.get_daily_reward_embed(
            daily_reward, client.game, self.view.locale, self.view.translator
        )
        await i.edit_original_response(embed=embed, attachments=[], view=self.view)


class ToggleButton(Button):
    def __init__(self, current_toggle: bool, toggle_label: _T, **kwargs):
        self.current_toggle = current_toggle
        self.toggle_label = toggle_label
        super().__init__(
            style=self._get_style(), label=self._get_label(), row=1, **kwargs
        )

    def _get_style(self) -> discord.ButtonStyle:
        return (
            discord.ButtonStyle.success
            if self.current_toggle
            else discord.ButtonStyle.secondary
        )

    def _get_label(self) -> _T:
        return _T(
            "{toggle_label}: {toggle}",
            key="auto_checkin_button_label",
            toggle_label=self.toggle_label,
            toggle=(
                _T("On", key="toggle_on_text")
                if self.current_toggle
                else _T("Off", key="toggle_off_text")
            ),
            translate=False,
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
        self.view: CheckInUI
        self.current_toggle = not self.current_toggle
        self.style = self._get_style()
        self.label = self.view.translator.translate(self._get_label(), self.view.locale)
        await i.response.edit_message(view=self.view)


class AutoCheckInToggle(ToggleButton):
    def __init__(self, current_toggle: bool):
        super().__init__(
            current_toggle,
            _T("Auto check-in", key="auto_checkin_button_label"),
            emoji=emojis.SMART_TOY,
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
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
            NotifyOnFailureToggle(
                self.view.account.notif_settings.notify_on_checkin_failure
            )
        )
        self.view.add_item(
            NotifyOnSuccessToggle(
                self.view.account.notif_settings.notify_on_checkin_success
            )
        )
        await i.response.edit_message(view=self.view)


class NotifyOnFailureToggle(ToggleButton):
    def __init__(self, current_toggle: bool):
        super().__init__(
            current_toggle,
            _T("Notify on check-in failure", key="notify_on_failure_button_label"),
        )

    async def callback(self, i: Interaction[HoyoBuddy]) -> Any:
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
        await super().callback(i)
        self.view.account.notif_settings.notify_on_checkin_success = self.current_toggle
        await self.view.account.notif_settings.save()
