from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any

import discord
from ambr.utils import remove_html_tags
from genshin.models import (
    ChallengeBuff,
    DeadlyAssault,
    DeadlyAssaultBuff,
    ImgTheaterData,
    ShiyuDefense,
    SpiralAbyss,
    StarRailAPCShadow,
    StarRailChallenge,
    StarRailChallengeSeason,
    StarRailPureFiction,
    TheaterBuff,
)
from genshin.models import Character as GICharacter

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import GAME_CHALLENGE_TYPES, GPY_LANG_TO_LOCALE, TRAVELER_IDS
from hoyo_buddy.db import ChallengeHistory, draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import (
    draw_apc_shadow_card,
    draw_assault_card,
    draw_img_theater_card,
    draw_moc_card,
    draw_pure_fiction_card,
    draw_shiyu_card,
    draw_spiral_abyss_card,
)
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import ChallengeType, Game
from hoyo_buddy.exceptions import NoChallengeDataError
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.types import Buff, Challenge, ChallengeWithBuff
from hoyo_buddy.ui import Button, Select, SelectOption, ToggleButton, View
from hoyo_buddy.utils import get_floor_difficulty

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    from collections.abc import Sequence

    import aiohttp
    from discord import File, Locale, Member, User

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Challenge, ChallengeWithLang, Interaction


class BuffView(View):
    def __init__(
        self,
        challenge: ChallengeWithBuff,
        season: StarRailChallengeSeason | None,
        *,
        author: User | Member,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self._challenge = challenge
        self._season = season
        self.buffs, self._buff_usage = self.calc_buff_usage()
        self.add_item(BuffSelector(list(self.buffs.values())))

    def get_buff_embed(self, buff: Buff, floors: str) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale, title=buff.name, description=remove_html_tags(buff.description)
        )
        embed.add_field(name=LocaleStr(key="challenge_view.buff_used_in"), value=floors)

        if isinstance(buff, ChallengeBuff | TheaterBuff | DeadlyAssaultBuff):
            embed.set_thumbnail(url=buff.icon)

        return embed

    def calc_buff_usage(self) -> tuple[dict[str, Buff], defaultdict[str, list[str]]]:
        buffs: dict[str, Buff] = {}  # Buff name to buff object
        buff_usage: defaultdict[str, list[str]] = defaultdict(list)  # Buff name to floor names

        if isinstance(self._challenge, StarRailPureFiction | StarRailAPCShadow):
            assert self._season is not None

            for floor in reversed(self._challenge.floors):
                n1_buff = floor.node_1.buff
                if n1_buff is not None:
                    team_str = LocaleStr(key="challenge_view.team", team=1).translate(self.locale)

                    floor_name = get_floor_difficulty(floor.name, self._season.name)
                    buff_usage[n1_buff.name].append(f"{floor_name} ({team_str})")
                    if n1_buff.name not in buffs:
                        buffs[n1_buff.name] = n1_buff

                n2_buff = floor.node_2.buff
                if n2_buff is not None:
                    team_str = LocaleStr(key="challenge_view.team", team=2).translate(self.locale)

                    floor_name = get_floor_difficulty(floor.name, self._season.name)
                    buff_usage[n2_buff.name].append(f"{floor_name} ({team_str})")
                    if n2_buff.name not in buffs:
                        buffs[n2_buff.name] = n2_buff
        elif isinstance(self._challenge, ShiyuDefense):
            for floor in reversed(self._challenge.floors):
                for buff in floor.buffs:
                    floor_name = LocaleStr(key=f"shiyu_{floor.index}_frontier").translate(
                        self.locale
                    )
                    buff_usage[buff.name].append(floor_name)
                    if buff.name not in buffs:
                        buffs[buff.name] = buff
        elif isinstance(self._challenge, DeadlyAssault):
            for challenge in self._challenge.challenges:
                for buff in challenge.buffs:
                    buff_usage[buff.name].append(challenge.boss.name)
                    if buff.name not in buffs:
                        buffs[buff.name] = buff
        else:
            for act in reversed(self._challenge.acts):
                act_buffs = list(act.wondroud_booms) + list(act.mystery_caches)
                for buff in act_buffs:
                    act_name = LocaleStr(
                        key="role_combat_round_count", mi18n_game=Game.GENSHIN, n=act.round_id
                    ).translate(self.locale)
                    buff_usage[buff.name].append(act_name)
                    if buff.name not in buffs:
                        buffs[buff.name] = buff

        return buffs, buff_usage


class BuffSelector(Select[BuffView]):
    def __init__(self, buffs: list[Buff]) -> None:
        super().__init__(
            placeholder=LocaleStr(key="challenge_view.buff_select.placeholder"),
            options=[
                SelectOption(
                    label=buff.name,
                    description=remove_html_tags(buff.description)[:100],
                    value=buff.name,
                    default=buff.name == buffs[0].name,
                )
                for buff in buffs
            ],
        )

    async def callback(self, i: Interaction) -> None:
        buff = self.view.buffs[self.values[0]]
        embed = self.view.get_buff_embed(buff, ", ".join(self.view._buff_usage[buff.name]))
        self.update_options_defaults()
        await i.response.edit_message(embed=embed, view=self.view)


class ChallengeView(View):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        challenge_type: ChallengeType,
        *,
        author: User | Member,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        self.challenge_type: ChallengeType = challenge_type
        self.account = account
        self.dark_mode = dark_mode

        self.season_ids: dict[ChallengeType, int] = {}
        """The user's selected season ID for a challange type"""
        self.challenge_cache: defaultdict[ChallengeType, dict[int, ChallengeWithLang]] = (
            defaultdict(dict)
        )
        """Cache of challenges for each season ID and challange type"""

        self.characters: Sequence[GICharacter] = []
        self.agent_ranks: dict[int, int] = {}
        self.uid = account.uid
        self.show_uid = False

    @property
    def challenge(self) -> ChallengeWithLang | None:
        if self.challenge_type not in self.season_ids:
            return None
        return self.challenge_cache[self.challenge_type].get(self.season_id)

    @property
    def season_id(self) -> int:
        return self.season_ids[self.challenge_type]

    @season_id.setter
    def season_id(self, value: int) -> None:
        self.season_ids[self.challenge_type] = value

    @staticmethod
    def _get_season_id(challenge: Challenge, previous: bool) -> int:
        if isinstance(challenge, SpiralAbyss):
            return challenge.season
        if isinstance(challenge, ImgTheaterData):
            return challenge.schedule.id
        if isinstance(challenge, ShiyuDefense):
            return challenge.schedule_id
        if isinstance(challenge, DeadlyAssault):
            return challenge.id

        index = 1 if previous else 0
        return challenge.seasons[index].id

    async def _fetch_data(self) -> None:
        if self.challenge is not None:
            return

        client = self.account.client
        client.set_lang(self.locale)

        if (
            self.challenge_type in {ChallengeType.SPIRAL_ABYSS, ChallengeType.IMG_THEATER}
            and not self.characters
        ):
            self.characters = await client.get_genshin_characters(self.account.uid)

        await client.get_record_cards()

        for previous in (False, True):
            if self.challenge_type is ChallengeType.SPIRAL_ABYSS:
                challenge = await client.get_genshin_spiral_abyss(
                    self.account.uid, previous=previous
                )
            elif self.challenge_type is ChallengeType.MOC:
                challenge = await client.get_starrail_challenge(self.account.uid, previous=previous)
            elif self.challenge_type is ChallengeType.PURE_FICTION:
                challenge = await client.get_starrail_pure_fiction(
                    self.account.uid, previous=previous
                )
            elif self.challenge_type is ChallengeType.APC_SHADOW:
                challenge = await client.get_starrail_apc_shadow(
                    self.account.uid, previous=previous
                )
            elif self.challenge_type is ChallengeType.IMG_THEATER:
                challenges = (
                    await client.get_imaginarium_theater(self.account.uid, previous=previous)
                ).datas
                if not challenges:
                    raise NoChallengeDataError(ChallengeType.IMG_THEATER)

                challenge = max(challenges, key=lambda c: c.stats.difficulty.value)
            elif self.challenge_type is ChallengeType.SHIYU_DEFENSE:
                if not self.agent_ranks:
                    agents = await client.get_zzz_agents(self.account.uid)
                    self.agent_ranks = {agent.id: agent.rank for agent in agents}
                challenge = await client.get_shiyu_defense(self.account.uid, previous=previous)
            elif self.challenge_type is ChallengeType.ASSAULT:
                challenge = await client.get_deadly_assault(self.account.uid, previous=previous)
            else:
                msg = f"Invalid challenge type: {self.challenge_type}"
                raise ValueError(msg)

            try:
                season_id = self._get_season_id(challenge, previous)
            except IndexError:
                # No previous season
                continue

            try:
                self.check_challenge_data(challenge)
            except NoChallengeDataError:
                continue

            # Save data to db
            await ChallengeHistory.add_data(
                uid=self.account.uid,
                challenge_type=self.challenge_type,
                season_id=season_id,
                data=challenge,
                lang=client.lang,
            )

    def check_challenge_data(self, challenge: Challenge | None) -> None:
        if challenge is None:
            raise NoChallengeDataError(self.challenge_type)
        if isinstance(challenge, SpiralAbyss):
            if not challenge.floors:
                raise NoChallengeDataError(ChallengeType.SPIRAL_ABYSS)
        elif not challenge.has_data:
            raise NoChallengeDataError(self.challenge_type)

    def get_season(self, challenge: Challenge) -> StarRailChallengeSeason:
        if isinstance(challenge, SpiralAbyss | ImgTheaterData | ShiyuDefense | DeadlyAssault):
            msg = f"Can't get season for {self.challenge_type}"
            raise TypeError(msg)

        result = next((season for season in challenge.seasons if season.id == self.season_id), None)
        if result is None:
            msg = f"Can't find season with ID {self.season_id}"
            raise ValueError(msg)
        return result

    async def draw_card(
        self,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ThreadPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> File:
        assert self.challenge is not None
        locale = draw_locale(GPY_LANG_TO_LOCALE[self.challenge.lang], self.account)
        draw_input = DrawInput(
            dark_mode=self.dark_mode,
            locale=locale,
            session=session,
            filename="challenge.png",
            executor=executor,
            loop=loop,
        )

        if isinstance(self.challenge, SpiralAbyss):
            return await draw_spiral_abyss_card(draw_input, self.challenge, self.characters)
        if isinstance(self.challenge, StarRailChallenge):
            return await draw_moc_card(draw_input, self.challenge, self.get_season(self.challenge))
        if isinstance(self.challenge, StarRailPureFiction):
            return await draw_pure_fiction_card(
                draw_input, self.challenge, self.get_season(self.challenge)
            )
        if isinstance(self.challenge, StarRailAPCShadow):
            return await draw_apc_shadow_card(
                draw_input, self.challenge, self.get_season(self.challenge)
            )
        if isinstance(self.challenge, ImgTheaterData):
            traveler = next((c for c in self.characters if c.id in TRAVELER_IDS), None)
            return await draw_img_theater_card(
                draw_input,
                self.challenge,
                {chara.id: chara.constellation for chara in self.characters},
                traveler.element if traveler is not None else None,
            )
        if isinstance(self.challenge, DeadlyAssault):
            return await draw_assault_card(
                draw_input, self.challenge, self.uid if self.show_uid else None
            )
        # ShiyuDefense
        return await draw_shiyu_card(
            draw_input, self.challenge, self.agent_ranks, self.uid if self.show_uid else None
        )

    def _add_items(self) -> None:
        self.add_item(
            ChallengeTypeSelect(GAME_CHALLENGE_TYPES[self.account.game], self.challenge_type)
        )
        self.add_item(PhaseSelect())
        self.add_item(ViewBuffs())
        self.add_item(ShowUID(disabled=self.account.game is not Game.ZZZ))

    async def update(
        self, item: Select[ChallengeView] | Button[ChallengeView], i: Interaction
    ) -> None:
        try:
            self.check_challenge_data(self.challenge)
            file_ = await self.draw_card(i.client.session, i.client.executor, i.client.loop)
        except NoChallengeDataError as e:
            embed, _ = get_error_embed(e, self.locale)
            await item.unset_loading_state(i, embed=embed, attachments=[])
            return

        embed = DefaultEmbed(self.locale).add_acc_info(self.account)
        embed.set_image(url="attachment://challenge.png")

        await item.unset_loading_state(i, embed=embed, attachments=[file_])

    async def fetch_data_and_update_ui(self) -> None:
        await self._fetch_data()

        histories = await ChallengeHistory.filter(
            uid=self.account.uid, challenge_type=self.challenge_type
        ).all()
        if not histories:
            raise NoChallengeDataError(self.challenge_type)

        for history in histories:
            self.challenge_cache[self.challenge_type][history.season_id] = history.parsed_data

        if self.challenge_type not in self.season_ids:
            self.season_id = histories[0].season_id

        phase_select: PhaseSelect = self.get_item("challenge_view.phase_select")
        phase_select.set_options(histories)
        phase_select.translate(self.locale)
        phase_select.update_options_defaults(values=[str(self.season_id)])

        buff_button: ViewBuffs = self.get_item("challenge_view.view_buffs")
        self.item_states["challenge_view.view_buffs"] = buff_button.disabled = not isinstance(
            self.challenge, ChallengeWithBuff
        )
        show_uid_button: ShowUID = self.get_item("show_uid")
        self.item_states["show_uid"] = show_uid_button.disabled = not isinstance(
            self.challenge, ShiyuDefense | DeadlyAssault
        )

    async def start(self, i: Interaction) -> None:
        self._add_items()

        await self.fetch_data_and_update_ui()
        self.check_challenge_data(self.challenge)
        file_ = await self.draw_card(i.client.session, i.client.executor, i.client.loop)
        embed = DefaultEmbed(self.locale).add_acc_info(self.account)
        embed.set_image(url="attachment://challenge.png")

        self.message = await i.edit_original_response(
            embed=embed, attachments=[file_], view=self, content=await get_dyk(i)
        )


class PhaseSelect(Select[ChallengeView]):
    def __init__(self) -> None:
        super().__init__(
            placeholder=LocaleStr(key="abyss.phase_select.placeholder"),
            options=[SelectOption(label="initialized", value="0")],
            custom_id="challenge_view.phase_select",
        )

    def set_options(self, histories: Sequence[ChallengeHistory]) -> None:
        options: list[SelectOption] = []
        for history in histories:
            if history.name is not None:
                options.append(
                    SelectOption(
                        label=history.name,
                        description=history.duration_str,
                        value=str(history.season_id),
                    )
                )
            else:
                options.append(
                    SelectOption(label=history.duration_str, value=str(history.season_id))
                )
        self.options = options

    async def callback(self, i: Interaction) -> None:
        self.view.season_id = int(self.values[0])
        await self.set_loading_state(i)
        await self.view.update(self, i)


class ChallengeTypeSelect(Select[ChallengeView]):
    def __init__(self, types: Sequence[ChallengeType], selected: ChallengeType) -> None:
        super().__init__(
            placeholder=LocaleStr(key="challenge_type_select.placeholder"),
            options=[
                SelectOption(label=EnumStr(type_), value=type_.value, default=type_ == selected)
                for type_ in types
            ],
        )

    async def callback(self, i: Interaction) -> None:
        self.view.challenge_type = ChallengeType(self.values[0])
        await self.set_loading_state(i)
        await self.view.fetch_data_and_update_ui()
        await self.view.update(self, i)


class ViewBuffs(Button[ChallengeView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="challenge_view.view_buffs"),
            style=discord.ButtonStyle.blurple,
            disabled=True,
            custom_id="challenge_view.view_buffs",
            row=4,
        )

    async def callback(self, i: Interaction) -> Any:
        assert isinstance(self.view.challenge, ChallengeWithBuff)

        try:
            season = self.view.get_season(self.view.challenge)
        except TypeError:
            season = None

        view = BuffView(self.view.challenge, season, author=i.user, locale=self.view.locale)
        if not view.buffs:
            self.disabled = True
            return await i.response.edit_message(view=self.view)

        first_buff = next(iter(view.buffs.values()), None)
        if first_buff is None:
            self.disabled = True
            return await i.response.edit_message(view=self.view)

        embed = view.get_buff_embed(first_buff, ", ".join(view._buff_usage[first_buff.name]))
        await i.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await i.original_response()
        return None


class ShowUID(ToggleButton[ChallengeView]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            False, LocaleStr(key="show_uid"), row=4, disabled=disabled, custom_id="show_uid"
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=False)
        self.view.show_uid = self.current_toggle
        await self.set_loading_state(i)
        await self.view.update(self, i)
