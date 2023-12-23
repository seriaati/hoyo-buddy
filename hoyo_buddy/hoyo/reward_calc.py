import calendar
from datetime import timedelta
from typing import TYPE_CHECKING

from genshin.models import ClaimedDailyReward, DailyReward

from ..utils import get_now

if TYPE_CHECKING:
    from collections.abc import Sequence

LAST_REWARD = -2
PREVIOUS_REWARD = -1
TODAY_REWARD = 0
NEXT_REWARD = 1
AFTER_NEXT_REWARD = 2


class RewardCalculator:
    def __init__(
        self,
        claimed_rewards: "Sequence[ClaimedDailyReward]",
        monthly_rewards: "Sequence[DailyReward]",
    ) -> None:
        self._claimed_rewards = claimed_rewards
        self._monthly_rewards = monthly_rewards
        self._today = get_now().date()

    @property
    def _last_month(self) -> int:
        return (self._today - timedelta(days=self._today.day)).month

    @property
    def _last_month_days(self) -> int:
        return calendar.monthrange(self._today.year, self._last_month)[1]

    @property
    def _next_month(self) -> int:
        return self._today.month + 1

    @property
    def _this_month_claimed_rewards(self) -> list[ClaimedDailyReward]:
        return [r for r in self._claimed_rewards if r.time.month == self._today.month]

    @property
    def claimed_amount(self) -> int:
        return min(self._today.day, len(self._this_month_claimed_rewards))

    def _get_claim_status(self, date: tuple[int, int]) -> str:
        return (
            "claimed"
            if any(
                r.time.day >= date[1] and r.time.month == date[0]
                for r in self._this_month_claimed_rewards
            )
            else "unclaimed"
        )

    @staticmethod
    def _change_reward_name(name: str, reward: ClaimedDailyReward | DailyReward) -> DailyReward:
        return DailyReward(name=name, amount=reward.amount, icon=reward.icon)

    def _get_renamed_monthly_rewards(self) -> list[DailyReward]:
        result: list[DailyReward] = []
        for i, r in enumerate(self._monthly_rewards):
            claim_status = self._get_claim_status((self._today.month, i + 1))
            result.append(
                self._change_reward_name(f"{claim_status}_{self._today.month}/{i + 1}", r)
            )
        return result

    def _get_reward_name(self, index: int, reward: DailyReward) -> DailyReward:
        if index in (LAST_REWARD, PREVIOUS_REWARD):
            return self._change_reward_name(f"{self._last_month}/{self._last_month_days}", reward)
        if index == TODAY_REWARD:
            return self._change_reward_name(f"{self._next_month}/1", reward)
        return reward

    def get_rewards(self) -> tuple[DailyReward, ...]:
        renamed_monthly_rewards = self._get_renamed_monthly_rewards()
        if self.claimed_amount == 0:
            return (
                self._change_reward_name(
                    f"{self._last_month}/{self._last_month_days}",
                    renamed_monthly_rewards[-2],
                ),
                self._change_reward_name(
                    f"{self._last_month}/{self._last_month_days}",
                    renamed_monthly_rewards[-1],
                ),
                renamed_monthly_rewards[0],
                renamed_monthly_rewards[1],
            )

        today_claimed = any(r.time.day == self._today.day for r in self._claimed_rewards)
        today_reward_index = self.claimed_amount - int(today_claimed)
        today_reward = renamed_monthly_rewards[today_reward_index]

        rewards = {
            TODAY_REWARD: lambda: (
                self._get_reward_name(LAST_REWARD, renamed_monthly_rewards[LAST_REWARD]),
                self._get_reward_name(PREVIOUS_REWARD, renamed_monthly_rewards[PREVIOUS_REWARD]),
                today_reward,
                renamed_monthly_rewards[AFTER_NEXT_REWARD],
            ),
            NEXT_REWARD: lambda: (
                self._get_reward_name(PREVIOUS_REWARD, renamed_monthly_rewards[PREVIOUS_REWARD]),
                renamed_monthly_rewards[TODAY_REWARD],
                today_reward,
                renamed_monthly_rewards[AFTER_NEXT_REWARD],
            ),
            len(renamed_monthly_rewards) - 1: lambda: (
                renamed_monthly_rewards[today_reward_index + LAST_REWARD],
                renamed_monthly_rewards[today_reward_index + PREVIOUS_REWARD],
                today_reward,
                self._get_reward_name(TODAY_REWARD, renamed_monthly_rewards[TODAY_REWARD]),
            ),
            "default": lambda: (
                renamed_monthly_rewards[today_reward_index + LAST_REWARD],
                renamed_monthly_rewards[today_reward_index + PREVIOUS_REWARD],
                today_reward,
                renamed_monthly_rewards[today_reward_index + NEXT_REWARD],
            ),
        }
        return rewards.get(today_reward_index, rewards["default"])()
