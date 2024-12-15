from __future__ import annotations

from typing import TYPE_CHECKING, Any

import genshin
import orjson
from discord import ButtonStyle, Locale
from seria.utils import create_bullet_list, shorten

from hoyo_buddy import ui
from hoyo_buddy.constants import HB_GAME_TO_GPY_GAME
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO, MIMO_POINT_EMOJIS, REDEEM_GIFT, SHOPPING_CART, TASK_LIST
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.utils import ephemeral

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.db.models import HoyoAccount
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
        self.shop_items: Sequence[genshin.models.MimoShopItem] = []

        self.mimo_game: genshin.models.MimoGame = None  # pyright: ignore[reportAttributeAccessIssue]
        self.game_id = self.mimo_game.id
        self.version_id = self.mimo_game.version_id

    @staticmethod
    def get_task_url(task: genshin.models.MimoTask) -> str | None:
        if not task.jump_url:
            return None

        url_data: dict[str, Any] = orjson.loads(task.jump_url)
        host, type_, args = url_data.get("host"), url_data.get("type"), url_data.get("args")
        if host != "hoyolab" or args is None:
            return None

        if type_ == "article":
            post_id = args.get("post_id")
            if post_id is None:
                return None
            return f"https://www.hoyolab.com/article/{post_id}"

        if type_ == "topicDetail":
            topic_id = args.get("topic_id")
            if topic_id is None:
                return None
            return f"https://www.hoyolab.com/topicDetail/{topic_id}"

        if type_ == "circles":
            game_id = args.get("game_id")
            if game_id is None:
                return None
            return f"https://www.hoyolab.com/circles/{game_id}"

        if type_ == "h5":
            url = args.get("url")
            if url is None:
                return None
            return url

        return None

    def create_task_bullet_list(self, tasks: Sequence[genshin.models.MimoTask]) -> str:
        task_strs: list[str] = []
        for task in tasks:
            task_url = self.get_task_url(task)
            if task_url:
                task_strs.append(f"[{task.name}]({task_url}) ({task.point} {self.point_emoji})")
            else:
                task_strs.append(f"{task.name} ({task.point} {self.point_emoji})")
        return create_bullet_list(task_strs)

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

    def get_shop_embed(self, points: int) -> DefaultEmbed:
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
        embed.set_image(url="attachment://mimo_shop_items.png")
        stock_str = LocaleStr(key="exchangePrizeLeft", mi18n_game="mimo").translate(self.locale)

        for shop_item in self.shop_items:
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

        return embed

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        mimo_games = await self.client.get_mimo_games()
        mimo_game = next(
            (game for game in mimo_games if game.game == HB_GAME_TO_GPY_GAME[self.account.game]),
            None,
        )
        if mimo_game is None:
            msg = f"Game {self.account.game} not found in Mimo games."
            raise ValueError(msg)
        self.mimo_game = mimo_game

        self.shop_items = await self.client.get_mimo_shop_items(
            game_id=mimo_game.id, version_id=mimo_game.version_id
        )
        points = await self.client.get_mimo_point_count()

        self.add_item(FinishAndClaimButton())
        self.add_item(TaskButton())
        self.add_item(ViewShopButton())
        self.add_item(InfoButton())
        self.add_item(AutoFinishAndClaimButton(current_toggle=self.account.mimo_auto_task))
        self.add_item(AutoBuyButton(current_toggle=self.account.mimo_auto_buy))
        self.add_item(ShopItemSelector(self.shop_items, points))

        embed = await self.get_tasks_embed(points=points)
        await i.followup.send(embed=embed, view=self)
        self.message = await i.original_response()


class TaskButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="mimo_tasks_button_label"), row=0, emoji=TASK_LIST)

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

        shop_item_select: ShopItemSelector = self.view.get_item("mimo_shop_item_selector")
        points = await self.view.client.get_mimo_point_count()
        disabled = shop_item_select.set_options(self.view.shop_items, points)
        self.view.item_states["mimo_shop_item_selector"] = disabled
        shop_item_select.translate(self.view.locale)

        embed = await self.view.get_tasks_embed(points=points)
        await self.unset_loading_state(i, embed=embed)


class AutoFinishAndClaimButton(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle,
            toggle_label=LocaleStr(key="mimo_auto_finish_and_claim_button_label"),
            row=1,
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.account.mimo_auto_task = self.current_toggle
        await self.view.account.save(update_fields=("mimo_auto_task",))


class AutoBuyButton(ui.ToggleButton[MimoView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle, toggle_label=LocaleStr(key="mimo_auto_buy_button_label"), row=1
        )

    async def callback(self, i: Interaction) -> Any:
        await super().callback(i)
        self.view.account.mimo_auto_buy = self.current_toggle
        await self.view.account.save(update_fields=("mimo_auto_buy",))


class ViewShopButton(ui.Button[MimoView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="mimo_view_shop_button_label"), row=0, emoji=SHOPPING_CART
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()
        embed = self.view.get_shop_embed(points=await self.view.client.get_mimo_point_count())
        await i.edit_original_response(embed=embed)


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

        _, success = await self.view.client.redeem_code(code, locale=self.view.locale)
        message = (
            LocaleStr(key="mimo_redeem_success", name=item.name, points=item.cost)
            if success
            else LocaleStr(key="mimo_redeem_failed", name=item.name, code=code)
        )
        embed = DefaultEmbed(self.view.locale, title=message)
        embed.set_thumbnail(url=item.icon)
        await i.followup.send(embed=embed, ephemeral=True)

        points = await self.view.client.get_mimo_point_count()
        shop_embed = self.view.get_shop_embed(points=points)
        await self.unset_loading_state(i, embed=shop_embed)

        shop_items = await self.view.client.get_mimo_shop_items(
            game_id=self.view.game_id, version_id=self.view.version_id
        )
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
