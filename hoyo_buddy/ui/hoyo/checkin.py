import asyncio
from typing import TYPE_CHECKING, Any

import discord
from genshin import Game, GenshinException

from ...bot import INTERACTION, LocaleStr, Translator, emojis
from ...bot.error_handler import get_error_embed
from ...draw import checkin
from ...draw.static import download_and_save_static_images
from ...embeds import DefaultEmbed
from ...hoyo.dataclasses import Reward
from ...utils import get_now
from ..ui import Button, GoBackButton, ToggleButton, View

if TYPE_CHECKING:
    import io

    import aiohttp

    from ...db.models import HoyoAccount

CHECK_IN_URLS = {
    Game.GENSHIN: "https://act.hoyolab.com/ys/event/signin-sea-v3/index.html?act_id=e202102251931481",
    Game.HONKAI: "https://act.hoyolab.com/bbs/event/signin-bh3/index.html?act_id=e202110291205111",
    Game.STARRAIL: "https://act.hoyolab.com/bbs/event/signin/hkrpg/index.html?act_id=e202303301540311",
}


class CheckInUI(View):
    def __init__(
        self,
        account: "HoyoAccount",
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
        self.dark_mode = dark_mode
        self.add_items()

    def add_items(self) -> None:
        if self.client.game is None:
            msg = "Client game is None"
            raise AssertionError(msg)
        self.add_item(CheckInButton())
        self.add_item(
            Button(
                url=CHECK_IN_URLS[self.client.game],
                label=LocaleStr("Make up for check-in", key="make_up_for_checkin_button_label"),
            )
        )
        self.add_item(AutoCheckInToggle(self.account.daily_checkin))
        self.add_item(NotificationSettingsButton())

    @staticmethod
    async def _draw_checkin_image(
        rewards: list[Reward],
        dark_mode: bool,
        session: "aiohttp.ClientSession",
    ) -> "io.BytesIO":
        await download_and_save_static_images([r.icon for r in rewards], "check-in", session)
        return await asyncio.to_thread(checkin.draw_card, rewards, dark_mode)

    async def _get_rewards(self) -> list[Reward]:
        client = self.client

        monthly_rewards = await client.get_monthly_rewards()
        monthly_rewards = [
            Reward(name=r.name, amount=r.amount, index=i, claimed=False, icon=r.icon)
            for i, r in enumerate(monthly_rewards, 1)
        ]

        claimed_rewards = await client.claimed_rewards(limit=31)
        claimed_rewards = claimed_rewards[::-1]
        claimed_rewards = [
            r for r in claimed_rewards if r.time.month == discord.utils.utcnow().month
        ]
        claimed_rewards = [
            Reward(name=r.name, amount=r.amount, index=i, claimed=True, icon=r.icon)
            for i, r in enumerate(claimed_rewards, 1)
        ]

        this_month_claim_num = len(claimed_rewards)
        rewards_to_return = 3

        if this_month_claim_num < rewards_to_return:
            result = monthly_rewards[:rewards_to_return]
            next_reward = monthly_rewards[rewards_to_return]
        else:
            result = claimed_rewards[-rewards_to_return:]

            try:
                next_reward = monthly_rewards[this_month_claim_num]
            except IndexError:
                next_reward = monthly_rewards[0]

        result.append(next_reward)
        return result

    async def get_image_embed_and_file(
        self, session: "aiohttp.ClientSession"
    ) -> tuple[DefaultEmbed, discord.File]:
        rewards = await self._get_rewards()
        checked_in_day_num = rewards[-2].index

        fp = await self._draw_checkin_image(rewards, self.dark_mode, session)
        fp.seek(0)
        file_ = discord.File(fp, filename="check-in.png")

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("Daily Check-in", key="daily_checkin_embed_title"),
            description=LocaleStr(
                "Checked in {day} day(s) this month\n" "Missed check-in for {missed} day(s)\n",
                key="daily_checkin_embed_description",
                day=checked_in_day_num,
                missed=get_now().day - checked_in_day_num,
            ),
        )
        embed.set_image(url="attachment://check-in.png")
        return embed, file_

    async def start(self, i: INTERACTION) -> None:
        await i.response.defer()
        embed, file_ = await self.get_image_embed_and_file(i.client.session)
        await i.followup.send(embed=embed, file=file_, view=self)
        self.message = await i.original_response()


class BackButton(Button):
    def __init__(self) -> None:
        super().__init__(emoji=emojis.BACK, row=4)

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CheckInUI

        await self.set_loading_state(i)
        embed, file_ = await self.view.get_image_embed_and_file(i.client.session)
        self.view.clear_items()
        self.view.add_items()
        await i.edit_original_response(embed=embed, attachments=[file_], view=self.view)


class CheckInButton(Button):
    def __init__(self) -> None:
        super().__init__(
            style=discord.ButtonStyle.primary,
            label=LocaleStr("Check-in", key="checkin_button_label"),
            emoji=emojis.FREE_CANCELLATION,
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CheckInUI

        await self.set_loading_state(i)
        client = self.view.client
        if client.game is None:
            msg = "Client game is None"
            raise AssertionError(msg)

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
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Auto check-in", key="auto_checkin_button_label"),
            emoji=emojis.SMART_TOY,
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CheckInUI
        await super().callback(i)
        self.view.account.daily_checkin = self.current_toggle
        await self.view.account.save()


class NotificationSettingsButton(Button):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Notification settings", key="notification_settings_button_label"),
            emoji=emojis.SETTINGS,
            row=1,
        )

    async def callback(self, i: INTERACTION) -> Any:
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
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Notify on check-in failure", key="notify_on_failure_button_label"),
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CheckInUI
        await super().callback(i)
        self.view.account.notif_settings.notify_on_checkin_failure = self.current_toggle
        await self.view.account.notif_settings.save()


class NotifyOnSuccessToggle(ToggleButton):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Notify on check-in success", key="notify_on_success_button_label"),
        )

    async def callback(self, i: INTERACTION) -> Any:
        self.view: CheckInUI
        await super().callback(i)
        self.view.account.notif_settings.notify_on_checkin_success = self.current_toggle
        await self.view.account.notif_settings.save()
