from __future__ import annotations

from typing import TYPE_CHECKING, Any

import genshin
from discord import ButtonStyle, Locale
from seria.utils import create_bullet_list, shorten

from hoyo_buddy import ui
from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import (
    BELL_OUTLINE,
    INFO,
    MIMO_POINT_EMOJIS,
    PAYMENTS,
    REDEEM_GIFT,
    SHOPPING_CART,
    TASK_LIST,
)
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import MimoUnavailableError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.components import GoBackButton
from hoyo_buddy.utils import convert_code_to_redeem_url, ephemeral, get_mimo_task_str

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Interaction, User


class MimoView(ui.View):
    def __init__(
        self, account: HoyoAccount, *, dark_mode: bool, author: User, locale: Locale
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.client = account.client
        self.client.set_lang(self.locale)

        self.dark_mode = dark_mode
        self.point_emoji = MIMO_POINT_EMOJIS.get(account.game, "")
        self.mimo_game: genshin.models.MimoGame = None  # pyright: ignore[reportAttributeAccessIssue]

    @property
    def game_id(self) -> int:
        return self.mimo_game.id

    @property
    def version_id(self) -> int:
        return self.mimo_game.version_id

    def create_task_bullet_list(self, tasks: Sequence[genshin.models.MimoTask]) -> str:
        return create_bullet_list([get_mimo_task_str(task, self.account.game) for task in tasks])

    def add_task_fields(
        self, embed: DefaultEmbed, tasks: Sequence[genshin.models.MimoTask], name: LocaleStr
    ) -> DefaultEmbed:
        tasks_: list[genshin.models.MimoTask] = []
        bullet_lists: list[str] = []
        for task in tasks:
            if len(self.create_task_bullet_list([*tasks_, task])) <= 1024:
                tasks_.append(task)
            else:
                bullet_lists.append(self.create_task_bullet_list(tasks_))
                tasks_ = [task]

        if tasks_:
            bullet_lists.append(self.create_task_bullet_list(tasks_))

        show_num = len(bullet_lists) > 1
        for i, bullet_list in enumerate(bullet_lists, start=1):
            name_ = LocaleStr(custom_str="{name} ({i})", name=name, i=i) if show_num else name
            embed.add_field(name=name_, value=bullet_list, inline=False)

        return embed

    async def get_tasks_embed(self, *, points: int | None = None) -> DefaultEmbed:
        points = points or await self.client.get_mimo_point_count()
        tasks = await self.client.get_mimo_tasks(game_id=self.game_id, version_id=self.version_id)

        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(
                custom_str="{title} ({start} - {end})",
                title=LocaleStr(key="mimo_tasks_button_label"),
                start=self.mimo_game.start_time.strftime("%m/%d"),
                end=self.mimo_game.end_time.strftime("%m/%d"),
            ),
            description=f"{points} {self.point_emoji}",
        )
        embed = self.add_task_fields(
            embed,
            [task for task in tasks if task.status is genshin.models.MimoTaskStatus.FINISHED],
            LocaleStr(key="mimo_task_status_claimable"),
        )
        embed = self.add_task_fields(
            embed,
            [task for task in tasks if task.status is genshin.models.MimoTaskStatus.ONGOING],
            LocaleStr(key="going", mi18n_game=Game.GENSHIN),
        )
        embed = self.add_task_fields(
            embed,
            [task for task in tasks if task.status is genshin.models.MimoTaskStatus.CLAIMED],
            LocaleStr(key="notes-card.gi.expedition-finished"),
        )
        return embed.add_acc_info(self.account)

    def get_shop_embed(
        self, points: int, shop_items: Sequence[genshin.models.MimoShopItem]
    ) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(
                custom_str="{title} ({start} - {end})",
                title=LocaleStr(key="pc_modal_title_exchange", mi18n_game="mimo"),
                start=self.mimo_game.start_time.strftime("%m/%d"),
                end=self.mimo_game.end_time.strftime("%m/%d"),
            ),
            description=f"{points} {self.point_emoji}",
        )
        stock_str = LocaleStr(key="exchangePrizeLeft", mi18n_game="mimo").translate(self.locale)

        for shop_item in shop_items:
            value = f"{shop_item.cost} {self.point_emoji}\n{stock_str} {shop_item.stock}"

            if shop_item.next_refresh_time.total_seconds() > 0:
                value += f"\n{LocaleStr(key='mimo_item_available_time', time=shop_item.next_refresh_time).translate(self.locale)}"

            if shop_item.status is genshin.models.MimoShopItemStatus.LIMIT_REACHED:
                value += f"\n{LocaleStr(
                    key="mimo_status", status=LocaleStr(key="exchangeLimit", mi18n_game="mimo")
                ).translate(self.locale)}"
            elif shop_item.status is genshin.models.MimoShopItemStatus.SOLD_OUT:
                value += f"\n{LocaleStr(
                    key="mimo_status", status=LocaleStr(key="exchangeSoldOut", mi18n_game="mimo")
                ).translate(self.locale)}"

            embed.add_field(name=shop_item.name, value=value, inline=False)

        return embed.add_acc_info(self.account)

    def get_lottery_info_embed(self, lottery_info: genshin.models.MimoLotteryInfo) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=LocaleStr(key="pc_modal_title_lottery", mi18n_game="mimo"),
            description=f"{lottery_info.current_point} {self.point_emoji}",
        )
        embed.add_description(
            LocaleStr(
                key="lottery_remain",
                mi18n_game="mimo",
                point=lottery_info.cost,
                append=f" {lottery_info.limit_count - lottery_info.current_count}/{lottery_info.limit_count}",
            )
        )
        embed.add_field(
            name=LocaleStr(key="lottery_modal_info_title", mi18n_game="mimo"),
            value=create_bullet_list([r.name for r in lottery_info.rewards]),
        )
        return embed.add_acc_info(self.account)

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        mimo_games = await self.client.get_mimo_games()
        mimo_game = next(
            (game for game in mimo_games if game.game == HB_GAME_TO_GPY_GAME[self.account.game]),
            None,
        )
        if mimo_game is None:
            raise MimoUnavailableError(self.account.game)

        self.mimo_game = mimo_game
        points = self.mimo_game.point

        self.add_item(FinishAndClaimButton())
        self.add_item(NotificationSettings())
        self.add_item(TaskButton())
        self.add_item(ViewShopButton())
        self.add_item(LotteryInfoButton())
        self.add_item(InfoButton())
        self.add_item(AutoFinishAndClaimButton(current_toggle=self.account.mimo_auto_task))
        self.add_item(AutoBuyButton(current_toggle=self.account.mimo_auto_buy))

        embed = await self.get_tasks_embed(points=points)
        await i.followup.send(embed=embed, view=self)
        self.message = await i.original_response()


class TaskButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="mimo_tasks_button_label"), row=1, emoji=TASK_LIST)

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        embed = await self.view.get_tasks_embed()
        await self.unset_loading_state(i, embed=embed)


class FinishAndClaimButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(
            style=ButtonStyle.blurple,
            label=LocaleStr(key="mimo_finish_and_claim_button_label"),
            row=0,
            emoji=REDEEM_GIFT,
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        await self.view.client.finish_and_claim_mimo_tasks(
            game_id=self.view.game_id, version_id=self.view.version_id
        )
        embed = await self.view.get_tasks_embed()
        await self.unset_loading_state(i, embed=embed)


class AutoFinishAndClaimButton(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            toggle_label=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
            row=2,
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.account.mimo_auto_task = self.current_toggle
        await self.view.account.save(update_fields=("mimo_auto_task",))


class AutoBuyButton(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle, toggle_label=LocaleStr(key="mimo_auto_buy_button_label"), row=2
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.account.mimo_auto_buy = self.current_toggle
        await self.view.account.save(update_fields=("mimo_auto_buy",))


class ViewShopButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="mimo_view_shop_button_label"), row=1, emoji=SHOPPING_CART
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()

        shop_items = await self.view.client.get_mimo_shop_items(
            game_id=self.view.mimo_game.id, version_id=self.view.mimo_game.version_id
        )
        points = await self.view.client.get_mimo_point_count()

        go_back_button = GoBackButton(self.view.children)
        self.view.clear_items()
        self.view.add_item(go_back_button)
        self.view.add_item(ShopItemSelector(shop_items, points))

        embed = self.view.get_shop_embed(points, shop_items)
        await i.edit_original_response(embed=embed, view=self.view)


class BuyItemModal(ui.Modal):
    amount = ui.TextInput(
        label=LocaleStr(key="mimo_buy_item_amount_label"), is_digit=True, min_value=1, default="1"
    )

    def __init__(self, item: genshin.models.MimoShopItem) -> None:
        super().__init__(title=shorten(item.name, 45))
        self.amount.max_value = item.user_count


class ShopItemSelector(ui.Select[MimoView]):
    def __init__(self, shop_items: Sequence[genshin.models.MimoShopItem], points: int) -> None:
        super().__init__(
            options=[],
            placeholder=LocaleStr(key="mimo_buy_item_select_placeholder"),
            custom_id="mimo_shop_item_selector",
        )
        self.set_options(shop_items, points)
        self.shop_items = shop_items

    def set_options(self, shop_items: Sequence[genshin.models.MimoShopItem], points: int) -> bool:
        options: list[ui.SelectOption] = []

        for reward in shop_items:
            if (
                reward.status is not genshin.models.MimoShopItemStatus.EXCHANGEABLE
                or reward.cost > points
            ):
                continue

            cost_str = LocaleStr(
                key="yatta_character_skill_energy_need_field_value", energy_need=reward.cost
            )
            stock_str = LocaleStr(
                key="exchangePrizeLeft", mi18n_game="mimo", append=f" {reward.stock}"
            )
            options.append(
                ui.SelectOption(
                    label=reward.name,
                    value=str(reward.id),
                    description=LocaleStr(
                        custom_str="{cost_str}, {stock_str}", cost_str=cost_str, stock_str=stock_str
                    ),
                )
            )

        if not options:
            self.options = [ui.SelectOption(label="placeholder", value="0")]
            self.disabled = True
        else:
            self.options = options
            self.disabled = False

        return self.disabled

    async def callback(self, i: Interaction) -> None:
        item_id = int(self.values[0])
        item = next((reward for reward in self.shop_items if reward.id == item_id), None)
        if item is None:
            msg = f"Shop item with ID {item_id} not found."
            raise ValueError(msg)

        modal = BuyItemModal(item)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        await self.set_loading_state(i)
        code = await self.view.client.buy_mimo_shop_item(
            item_id, game_id=self.view.game_id, version_id=self.view.version_id
        )

        if code:
            success = False
            if self.view.account.can_redeem_code:
                _, success = await self.view.client.redeem_code(code, locale=self.view.locale)
        else:
            success = True

        description = (
            LocaleStr(
                key="exchangeCodeTips",
                mi18n_game="mimo",
                append=f"\n{convert_code_to_redeem_url(code, game=self.view.account.game)}",
            )
            if not success
            else LocaleStr(key="mimo_draw_redeem_success")
        )

        embed = DefaultEmbed(self.view.locale, title=item.name, description=description)
        embed.set_thumbnail(url=item.icon)
        await i.followup.send(embed=embed, ephemeral=True)

        shop_items = await self.view.client.get_mimo_shop_items(
            game_id=self.view.mimo_game.id, version_id=self.view.mimo_game.version_id
        )
        points = await self.view.client.get_mimo_point_count()

        shop_embed = self.view.get_shop_embed(points, shop_items)
        await self.unset_loading_state(i, embed=shop_embed)

        self.set_options(shop_items, points)
        self.translate(self.view.locale)
        await i.edit_original_response(view=self.view)


class InfoButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=0)

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="mimo_info_embed_title"),
            description=LocaleStr(key="mimo_info_embed_desc"),
        )
        embed.add_field(
            name=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
            value=LocaleStr(key="mimo_auto_finish_and_claim_desc"),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr(key="mimo_auto_buy_button_label"),
            value=LocaleStr(key="mimo_auto_buy_desc"),
            inline=False,
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class LotteryDrawButton(ui.Button[MimoView]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="homeLotteryBtnText", mi18n_game="mimo"),
            disabled=disabled,
            style=ButtonStyle.blurple,
            emoji=PAYMENTS,
        )

    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        result = await self.view.client.draw_mimo_lottery(
            game_id=self.view.game_id, version_id=self.view.version_id
        )
        if result.code:
            success = False
            if self.view.account.can_redeem_code:
                _, success = await self.view.client.redeem_code(
                    result.code, locale=self.view.locale
                )
        else:
            success = True

        description = (
            LocaleStr(
                key="exchangeCodeTips",
                mi18n_game="mimo",
                append=f"\n{convert_code_to_redeem_url(result.code, game=self.view.account.game)}",
            )
            if not success
            else LocaleStr(key="mimo_draw_redeem_success")
        )

        result_embed = DefaultEmbed(
            self.view.locale, title=result.reward.name, description=description
        )
        result_embed.set_thumbnail(url=result.reward.icon)
        await i.followup.send(embed=result_embed, ephemeral=True)

        lottery_info = await self.view.client.get_mimo_lottery_info(
            game_id=self.view.game_id, version_id=self.view.version_id
        )
        embed = self.view.get_lottery_info_embed(lottery_info)
        await self.unset_loading_state(i, embed=embed)


class LotteryInfoButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(
            emoji=PAYMENTS, label=LocaleStr(key="pc_modal_title_lottery", mi18n_game="mimo"), row=1
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()
        lottery_info = await self.view.client.get_mimo_lottery_info(
            game_id=self.view.game_id, version_id=self.view.version_id
        )
        embed = self.view.get_lottery_info_embed(lottery_info)
        go_back_button = GoBackButton(self.view.children)
        self.view.clear_items()
        self.view.add_item(go_back_button)
        self.view.add_item(
            LotteryDrawButton(disabled=lottery_info.current_count >= lottery_info.limit_count)
        )
        await i.edit_original_response(embed=embed, view=self.view)


class NotificationSettings(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="notification_settings_button_label"), row=0, emoji=BELL_OUTLINE
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()
        await self.view.account.fetch_related("notif_settings")

        go_back_button = GoBackButton(self.view.children)
        self.view.clear_items()
        self.view.add_item(go_back_button)

        self.view.add_item(
            AutoTaskSuccessNotify(current_toggle=self.view.account.notif_settings.mimo_task_success)
        )
        self.view.add_item(
            AutoTaskFailureNotify(current_toggle=self.view.account.notif_settings.mimo_task_failure)
        )
        self.view.add_item(
            AutoBuySuccessNotify(current_toggle=self.view.account.notif_settings.mimo_buy_success)
        )
        self.view.add_item(
            AutoBuyFailureNotify(current_toggle=self.view.account.notif_settings.mimo_buy_failure)
        )
        await i.edit_original_response(view=self.view)


class AutoTaskSuccessNotify(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            toggle_label=LocaleStr(key="mimo_auto_task_success_notify_toggle_label"),
            row=0,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        await self.view.account.fetch_related("notif_settings")
        self.view.account.notif_settings.mimo_task_success = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("mimo_task_success",))


class AutoTaskFailureNotify(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            toggle_label=LocaleStr(key="mimo_auto_task_failure_notify_toggle_label"),
            row=0,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.notif_settings.mimo_task_failure = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("mimo_task_failure",))


class AutoBuySuccessNotify(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            toggle_label=LocaleStr(key="mimo_auto_buy_success_notify_toggle_label"),
            row=1,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.notif_settings.mimo_buy_success = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("mimo_buy_success",))


class AutoBuyFailureNotify(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            toggle_label=LocaleStr(key="mimo_auto_buy_failure_notify_toggle_label"),
            row=1,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.notif_settings.mimo_buy_failure = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("mimo_buy_failure",))
