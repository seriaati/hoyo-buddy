from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, TypeAlias

import genshin
from seria.utils import create_bullet_list

from hoyo_buddy import ui
from hoyo_buddy.constants import BLOCK_COLORS
from hoyo_buddy.db import HoyoAccount, draw_locale
from hoyo_buddy.draw.main_funcs import draw_block_list_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game
from hoyo_buddy.l10n import LocaleStr, TimeRemainingStr, UnlocksInStr
from hoyo_buddy.models import DrawInput, SingleBlock

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord
    from discord import Locale

    from hoyo_buddy.bot import HoyoBuddy
    from hoyo_buddy.types import Interaction, User

CalendarItem: TypeAlias = (
    genshin.models.Banner
    | genshin.models.EventWarp
    | genshin.models.Event
    | genshin.models.HSREvent
    | genshin.models.HSRChallenge
)
EventItem: TypeAlias = genshin.models.Event | genshin.models.HSREvent
ChallengeItem: TypeAlias = genshin.models.Event | genshin.models.HSRChallenge
GICalendarItem: TypeAlias = genshin.models.Banner | genshin.models.Event
HSRCalendarItem: TypeAlias = (
    genshin.models.EventWarp | genshin.models.HSREvent | genshin.models.HSRChallenge
)


def event_not_started(item: CalendarItem) -> bool:
    if isinstance(item, HSRCalendarItem):
        return item.time_info is not None and item.time_info.now < item.time_info.start
    if isinstance(item, genshin.models.Banner):
        return False
    return item.status == 1


def event_is_finished(item: EventItem | ChallengeItem) -> bool:
    if isinstance(item, genshin.models.HSREvent):
        return item.all_finished or (
            item.type is genshin.models.HSREventType.DOUBLE_REWARDS and item.current_progress == 0
        )
    if isinstance(item, genshin.models.HSRChallenge):
        return item.current_progress == item.total_progress
    if item.abyss_detail is not None:
        return item.abyss_detail.total_star == item.abyss_detail.max_star
    if item.theater_detail is not None:
        return item.theater_detail.max_round == 10
    return item.is_finished


def get_option_desc(item: CalendarItem, cur_game_version: str | None = None) -> LocaleStr:
    if event_not_started(item):
        return LocaleStr(key="unopened", mi18n_game=Game.GENSHIN)

    finished = False
    if isinstance(item, EventItem | ChallengeItem) and event_is_finished(item):
        finished = True

    if isinstance(item, GICalendarItem):
        seconds = item.countdown_seconds
    elif item.time_info is None:
        return LocaleStr(key="going", mi18n_game=Game.GENSHIN)
    elif (
        isinstance(item, genshin.models.EventWarp)
        and cur_game_version is not None
        and item.version != cur_game_version
    ):
        return UnlocksInStr(item.time_info.start - item.time_info.now)
    else:
        seconds = item.time_info.end - item.time_info.now

    if finished:
        return LocaleStr(
            custom_str="{fin} | {time}",
            fin=LocaleStr(key="notes-card.gi.expedition-finished"),
            time=TimeRemainingStr(seconds),
        )
    return TimeRemainingStr(seconds)


def get_duration_str(banner_or_event: CalendarItem) -> str:
    if isinstance(banner_or_event, GICalendarItem):
        if banner_or_event.start_time is None or banner_or_event.end_time is None:
            return ""
        return f"{banner_or_event.start_time.strftime('%Y-%m-%d')} ~ {banner_or_event.end_time.strftime('%Y-%m-%d')}"

    if banner_or_event.time_info is None:
        return ""

    start = banner_or_event.time_info.start
    end = banner_or_event.time_info.end
    return f"{start.strftime('%Y-%m-%d')} ~ {end.strftime('%Y-%m-%d')}"


class EventCalendarView(ui.View):
    def __init__(
        self,
        calendar: genshin.models.GenshinEventCalendar | genshin.models.HSREventCalendar,
        account: HoyoAccount,
        dark_mode: bool,
        *,
        author: User,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.calendar = calendar
        self.account = account
        self.dark_mode = dark_mode

        if isinstance(calendar, genshin.models.GenshinEventCalendar):
            banners: list[genshin.models.Banner] = []
            banners.extend(calendar.character_banners)
            banners.extend(calendar.weapon_banners)
            self.add_item(BannerSelector(banners))
        else:
            warps: list[genshin.models.EventWarp] = []
            warps.extend(calendar.character_warps)
            warps.extend(calendar.light_cone_warps)
            self.add_item(BannerSelector(warps, cur_game_version=calendar.cur_game_version))

        if calendar.events:
            self.add_item(EventSelector(calendar.events))
        if calendar.challenges:
            self.add_item(ChallengeSelector(calendar.challenges))

    @property
    def embed(self) -> DefaultEmbed:
        in_progress: list[EventItem | ChallengeItem] = [
            event
            for event in list(self.calendar.events) + list(self.calendar.challenges)
            if not event_is_finished(event) and not event_not_started(event)
        ]
        names: list[str] = []
        for event in in_progress:
            if isinstance(event, ChallengeItem):
                name = ChallengeSelector.get_option_name(event)
                if isinstance(name, LocaleStr):
                    name = name.translate(self.locale)
                names.append(name)
            else:
                names.append(event.name)

        return DefaultEmbed(
            self.locale,
            title=LocaleStr(key="going", mi18n_game=Game.GENSHIN),
            description=create_bullet_list(names),
        )

    async def draw_rewards_card(
        self, bot: HoyoBuddy, event: EventItem | genshin.models.HSRChallenge
    ) -> discord.File:
        blocks = [
            SingleBlock(
                icon=i.icon,
                bottom_text=str(i.num) if i.num > 0 else "-",
                bg_color=BLOCK_COLORS[self.dark_mode][i.rarity],
            )
            for i in event.rewards
        ]
        return await draw_block_list_card(
            DrawInput(
                dark_mode=self.dark_mode,
                locale=draw_locale(self.locale, self.account),
                session=bot.session,
                executor=bot.executor,
                loop=bot.loop,
                filename="rewards.png",
            ),
            list(itertools.batched(blocks, 4)),
        )

    async def start(self, i: Interaction) -> None:
        await i.followup.send(embed=self.embed, view=self)
        self.message = await i.original_response()


class ItemSelector(ui.Select[EventCalendarView]):
    async def callback(self, _: Interaction) -> None:
        for item in self.view.children:
            if isinstance(item, ui.Select):
                item.reset_options_defaults()
        self.update_options_defaults()


class BannerSelector(ItemSelector):
    def __init__(
        self,
        banners: Sequence[genshin.models.Banner] | Sequence[genshin.models.EventWarp],
        *,
        cur_game_version: str | None = None,
    ) -> None:
        super().__init__(
            placeholder=LocaleStr(key="banner_selector_placeholder"),
            options=[
                ui.SelectOption(
                    label=self.get_option_name(b),
                    description=get_option_desc(b, cur_game_version=cur_game_version),
                    value=str(b.id),
                )
                for b in banners
            ],
        )
        self.banners = banners

    @staticmethod
    def get_option_name(banner: genshin.models.Banner | genshin.models.EventWarp) -> str:
        if isinstance(banner, genshin.models.Banner):
            return banner.name
        items = list(banner.characters) + list(banner.light_cones)
        return " / ".join(i.name for i in items if i.rarity == 5)

    def get_embed(self, banner: genshin.models.Banner | genshin.models.EventWarp) -> DefaultEmbed:
        return DefaultEmbed(
            self.view.locale,
            title=self.get_option_name(banner),
            description=get_duration_str(banner),
        ).set_image(url="attachment://banner_items.png")

    async def draw_banner_items(
        self, bot: HoyoBuddy, banner: genshin.models.Banner | genshin.models.EventWarp
    ) -> discord.File:
        if isinstance(banner, genshin.models.Banner):
            banner_items = list(banner.characters) + list(banner.weapons)
        else:
            banner_items = list(banner.characters) + list(banner.light_cones)

        blocks = [
            SingleBlock(icon=i.icon, bg_color=BLOCK_COLORS[self.view.dark_mode][i.rarity])
            for i in banner_items
        ]
        return await draw_block_list_card(
            DrawInput(
                dark_mode=self.view.dark_mode,
                locale=draw_locale(self.view.locale, self.view.account),
                session=bot.session,
                executor=bot.executor,
                loop=bot.loop,
                filename="banner_items.png",
            ),
            list(itertools.batched(blocks, 4)),
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        await self.set_loading_state(i)

        banner_id = int(self.values[0])
        banner = next((b for b in self.banners if b.id == banner_id), None)
        if banner is None:
            msg = f"Banner with ID {banner_id} not found."
            raise ValueError(msg)

        embed = self.get_embed(banner)
        file_ = await self.draw_banner_items(i.client, banner)
        await self.unset_loading_state(i, embed=embed, attachments=[file_])


class EventSelector(ItemSelector):
    def __init__(
        self, events: Sequence[genshin.models.Event] | Sequence[genshin.models.HSREvent]
    ) -> None:
        super().__init__(
            placeholder=LocaleStr(key="events_view_ann_select_placeholder"),
            options=[
                ui.SelectOption(label=e.name, description=get_option_desc(e), value=str(e.id))
                for e in events
            ],
        )
        self.events = events

    def get_embed(self, event: EventItem) -> DefaultEmbed:
        if event_is_finished(event):
            status_str = LocaleStr(key="notes-card.gi.expedition-finished")
        elif event_not_started(event):
            status_str = LocaleStr(key="unopened", mi18n_game=Game.GENSHIN)
        else:
            status_str = LocaleStr(key="going", mi18n_game=Game.GENSHIN)

        embed = (
            DefaultEmbed(
                self.view.locale,
                title=event.name,
                description=f"{get_duration_str(event)}\n\n{event.description}",
            )
            .set_image(url="attachment://rewards.png")
            .add_field(
                name=LocaleStr(key="finished_status_field_name"), value=status_str, inline=False
            )
        )

        if (
            isinstance(event, genshin.models.Event)
            and (exp_detail := event.exploration_detail) is not None
        ):
            embed.add_field(
                name=LocaleStr(key="exploration_progress", mi18n_game=Game.GENSHIN),
                value=f"{exp_detail.explored_percentage}%",
                inline=False,
            )

        remaining = None
        total = None

        if (
            isinstance(event, genshin.models.HSREvent)
            and event.type == genshin.models.HSREventType.DOUBLE_REWARDS
        ):
            remaining = event.current_progress
            total = event.total_progress

        if (
            isinstance(event, genshin.models.Event)
            and (double_detail := event.double_reward_detail) is not None
        ):
            remaining = double_detail.remaining
            total = double_detail.total

        if remaining is not None and total is not None:
            embed.add_field(
                name=LocaleStr(key="double_act_text", mi18n_game=Game.STARRAIL),
                value=f"{remaining}/{total}",
                inline=False,
            )

        if event.rewards:
            embed.add_field(
                name=LocaleStr(key="reward_overview", mi18n_game=Game.GENSHIN),
                value="",
                inline=False,
            )
        return embed

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        await self.set_loading_state(i)

        event_id = int(self.values[0])
        event = next((e for e in self.events if e.id == event_id), None)
        if event is None:
            msg = f"Event with ID {event_id} not found."
            raise ValueError(msg)

        embed = self.get_embed(event)
        if event.rewards:
            file_ = await self.view.draw_rewards_card(i.client, event)
            await self.unset_loading_state(i, embed=embed, attachments=[file_])
        else:
            await self.unset_loading_state(i, embed=embed, attachments=[])


class ChallengeSelector(ItemSelector):
    def __init__(
        self, challenges: Sequence[genshin.models.HSRChallenge] | Sequence[genshin.models.Event]
    ) -> None:
        super().__init__(
            placeholder=LocaleStr(key="challenge_selector_placeholder"),
            options=[
                ui.SelectOption(
                    label=self.get_option_name(c),
                    description=get_option_desc(c),
                    value=self.get_option_value(c),
                )
                for c in challenges
            ],
        )
        self.challenges = challenges

    @staticmethod
    def get_option_name(challenge: ChallengeItem) -> LocaleStr | str:
        if isinstance(challenge, genshin.models.Event):
            name = challenge.name
            if challenge.abyss_detail is not None:
                name = f"{name} ({challenge.abyss_detail.total_star}/{challenge.abyss_detail.max_star})"
            if challenge.theater_detail is not None:
                name = f"{name} ({challenge.theater_detail.max_round or "-"}/10)"
            return name

        if challenge.type is genshin.models.ChallengeType.MOC:
            key = "memory_of_chaos"
        elif challenge.type is genshin.models.ChallengeType.PURE_FICTION:
            key = "pure_fiction"
        else:
            key = "apocalyptic_shadow"

        name = LocaleStr(key=key, append=f": {challenge.name}")
        return LocaleStr(
            custom_str="{name} ({star}/{max_star})",
            name=name,
            star=challenge.current_progress,
            max_star=challenge.total_progress,
        )

    @staticmethod
    def get_option_value(challenge: ChallengeItem) -> str:
        if isinstance(challenge, genshin.models.Event):
            return str(challenge.type)
        return str(challenge.id)

    def get_embed(self, challenge: ChallengeItem) -> DefaultEmbed:
        star = None
        max_star = None
        act = None

        if isinstance(challenge, genshin.models.HSRChallenge):
            star = challenge.current_progress
            max_star = challenge.total_progress
        elif challenge.type == "ActTypeTower":
            if challenge.abyss_detail is None:
                msg = "Abyss detail not found."
                raise ValueError(msg)
            star = challenge.abyss_detail.total_star
            max_star = challenge.abyss_detail.max_star
        elif challenge.type == "ActTypeRoleCombat":
            if challenge.theater_detail is None:
                msg = "Theater detail not found."
                raise ValueError(msg)
            act = challenge.theater_detail.max_round

        embed = DefaultEmbed(
            self.view.locale,
            title=self.get_option_name(challenge),
            description=get_duration_str(challenge),
        ).set_image(url="attachment://rewards.png")
        if star is not None and max_star is not None:
            embed.add_field(
                name=LocaleStr(key="music_grade", mi18n_game=Game.GENSHIN),
                value=f"{star}/{max_star}",
                inline=False,
            )
        if act is not None:
            embed.add_field(
                name=LocaleStr(key="deepest_arrive", mi18n_game=Game.GENSHIN),
                value=LocaleStr(
                    key="role_combat_round_count", mi18n_game=Game.GENSHIN, n=act or "-"
                ),
                inline=False,
            )
        if challenge.rewards:
            embed.add_field(
                name=LocaleStr(key="reward_overview", mi18n_game=Game.GENSHIN),
                value="",
                inline=False,
            )
        return embed

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        await self.set_loading_state(i)

        id_ = self.values[0]
        challenge = next((c for c in self.challenges if self.get_option_value(c) == id_), None)
        if challenge is None:
            msg = f"Challenge with id {id_} not found."
            raise ValueError(msg)

        embed = self.get_embed(challenge)
        if challenge.rewards:
            file_ = await self.view.draw_rewards_card(i.client, challenge)
            await self.unset_loading_state(i, embed=embed, attachments=[file_])
        else:
            await self.unset_loading_state(i, embed=embed, attachments=[])
