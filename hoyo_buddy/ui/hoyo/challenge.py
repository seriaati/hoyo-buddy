from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Any, TypeAlias, cast

import discord
from ambr.utils import remove_html_tags
from genshin.models import (
    ChallengeBuff,
    DeadlyAssault,
    DeadlyAssaultBuff,
    HardChallenge,
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
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.constants import GAME_CHALLENGE_TYPES, GPY_LANG_TO_LOCALE, TRAVELER_IDS
from hoyo_buddy.db import ChallengeHistory, draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import (
    draw_apc_shadow_card,
    draw_assault_card,
    draw_hard_challenge,
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
from hoyo_buddy.utils import blur_uid, get_floor_difficulty

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    from collections.abc import Mapping, Sequence

    import aiohttp
    import genshin
    from discord import File, Member, User

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Challenge, ChallengeWithLang, Interaction

ShowUIDChallenge: TypeAlias = ShiyuDefense | DeadlyAssault | HardChallenge


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
    def _get_season_id(challenge: Challenge, *, previous: bool) -> int:
        if isinstance(challenge, SpiralAbyss):
            return challenge.season
        if isinstance(challenge, ImgTheaterData):
            return challenge.schedule.id
        if isinstance(challenge, ShiyuDefense):
            return challenge.schedule_id
        if isinstance(challenge, DeadlyAssault):
            return challenge.id
        if isinstance(challenge, HardChallenge):
            return challenge.season.id

        index = 1 if previous else 0
        return challenge.seasons[index].id

    async def _fetch_img_theater_raw_data(self, client: genshin.Client) -> None:
        raw_ = await client.get_imaginarium_theater(self.account.uid, raw=True)
        datas: list[dict[str, Any]] = raw_.get("data", [])
        if not datas:
            raise NoChallengeDataError(ChallengeType.IMG_THEATER)

            # Organize data by start time
        data_by_date: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
        for data in datas:
            start: int = data["schedule"]["start_time"]
            data_by_date[start].append(data)

        for datas in data_by_date.values():
            most_difficult = max(datas, key=lambda d: d["stat"]["difficulty_id"])
            await self._validate_and_save_challenge_data(
                most_difficult, previous=False, lang=client.lang
            )

    async def _fetch_hard_challenge_raw_data(self, client: genshin.Client) -> None:
        datas = await client.get_stygian_onslaught(self.account.uid, raw=True)
        for data in datas:
            if data["schedule"]["schedule_id"] == "0":
                continue
            await self._validate_and_save_challenge_data(data, previous=False, lang=client.lang)

    async def _fetch_data(self) -> None:
        if self.challenge is not None:
            return

        client = self.account.client
        client.set_lang(self.locale)

        await client.get_record_cards()

        # Special handling for game modes that don't have previous parameters

        if self.challenge_type is ChallengeType.IMG_THEATER:
            await self._fetch_img_theater_raw_data(client)
            return

        if self.challenge_type is ChallengeType.HARD_CHALLENGE:
            await self._fetch_hard_challenge_raw_data(client)
            return

        for previous in (False, True):
            raw = await self._fetch_challenge_raw_data(client, previous=previous)
            await self._validate_and_save_challenge_data(raw, previous=previous, lang=client.lang)

    async def _validate_and_save_challenge_data(
        self, raw: Mapping[str, Any], *, previous: bool, lang: str
    ) -> None:
        try:
            challenge = ChallengeHistory.load_data(raw, challenge_type=self.challenge_type)
        except Exception as e:
            logger.warning(f"Failed to load challenge data for {self.challenge_type!r}: {e}")
            return

        if (
            self.challenge_type in {ChallengeType.SPIRAL_ABYSS, ChallengeType.IMG_THEATER}
            and not self.characters
        ):
            # Only fetch characters when challenge has data
            try:
                self.check_challenge_data(challenge)
            except NoChallengeDataError:
                pass
            else:
                client = self.account.client
                self.characters = await client.get_genshin_characters(self.account.uid)

        try:
            season_id = self._get_season_id(challenge, previous=previous)
        except IndexError:
            # No previous season
            return

        try:
            self.check_challenge_data(challenge)
        except NoChallengeDataError:
            return

        # Save data to db
        await ChallengeHistory.add_data(
            uid=self.account.uid,
            challenge_type=self.challenge_type,
            season_id=season_id,
            raw=raw,
            lang=lang,
        )

    async def _fetch_challenge_raw_data(
        self, client: genshin.Client, *, previous: bool
    ) -> Mapping[str, Any]:
        if self.challenge_type is ChallengeType.SPIRAL_ABYSS:
            return await client.get_genshin_spiral_abyss(
                self.account.uid, previous=previous, raw=True
            )

        if self.challenge_type is ChallengeType.MOC:
            return await client.get_starrail_challenge(
                self.account.uid, previous=previous, raw=True
            )

        if self.challenge_type is ChallengeType.PURE_FICTION:
            return await client.get_starrail_pure_fiction(
                self.account.uid, previous=previous, raw=True
            )

        if self.challenge_type is ChallengeType.APC_SHADOW:
            return await client.get_starrail_apc_shadow(
                self.account.uid, previous=previous, raw=True
            )

        if self.challenge_type is ChallengeType.SHIYU_DEFENSE:
            raw = await client.get_shiyu_defense(self.account.uid, previous=previous, raw=True)
            challenge = ChallengeHistory.load_data(raw, challenge_type=self.challenge_type)
            challenge = cast("ShiyuDefense", challenge)

            # Backward compatibility, ShiyuDefenseCharacter.mindscape is added in
            # https://github.com/thesadru/genshin.py/commit/4e17d37f84048d2b0a478b45e374f980a7bbe3a3
            is_new_ver = (
                challenge.floors
                and challenge.floors[0].node_1.characters
                and hasattr(challenge.floors[0].node_1.characters[0], "mindscape")
            )

            # No need to fetch agent ranks if the data is using new version
            if challenge.has_data and not self.agent_ranks and not is_new_ver:
                agents = await client.get_zzz_agents(self.account.uid)
                self.agent_ranks = {agent.id: agent.rank for agent in agents}

            return raw

        if self.challenge_type is ChallengeType.ASSAULT:
            return await client.get_deadly_assault(self.account.uid, previous=previous, raw=True)

        msg = f"Data fetching for {self.challenge_type!r} is not implemented"
        raise NotImplementedError(msg)

    def check_challenge_data(self, challenge: Challenge | None) -> None:
        """Check if the challenge has data and raise an error if it doesn't"""
        exc = NoChallengeDataError(self.challenge_type)
        if challenge is None:
            raise exc
        if isinstance(challenge, SpiralAbyss):
            if not challenge.floors:
                raise exc
        elif isinstance(challenge, HardChallenge):
            if not challenge.single_player.has_data:
                raise exc
        elif not challenge.has_data:
            raise exc

    def get_season(self, challenge: Challenge) -> StarRailChallengeSeason:
        if isinstance(
            challenge, SpiralAbyss | ImgTheaterData | ShiyuDefense | DeadlyAssault | HardChallenge
        ):
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
        executor: concurrent.futures.Executor,
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
        if isinstance(self.challenge, HardChallenge):
            return await draw_hard_challenge(
                draw_input, self.challenge, str(self.uid) if self.show_uid else blur_uid(self.uid)
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
        self.add_item(ShowUID())

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

        try:
            show_uid_button: ShowUID = self.get_item("show_uid")
        except ValueError:
            pass
        else:
            self.item_states["show_uid"] = show_uid_button.disabled = not isinstance(
                self.challenge, ShowUIDChallenge
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
    def __init__(self) -> None:
        super().__init__(False, LocaleStr(key="show_uid"), row=4, custom_id="show_uid")

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=False)
        self.view.show_uid = self.current_toggle
        await self.set_loading_state(i)
        await self.view.update(self, i)
