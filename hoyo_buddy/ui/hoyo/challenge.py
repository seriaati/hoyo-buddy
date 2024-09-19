from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import discord
from ambr.utils import remove_html_tags
from genshin.models import (
    ChallengeBuff,
    ImgTheaterData,
    SpiralAbyss,
    StarRailAPCShadow,
    StarRailChallenge,
    StarRailChallengeSeason,
    StarRailPureFiction,
    TheaterBuff,
)
from genshin.models import Character as GICharacter

from hoyo_buddy.constants import GAME_CHALLENGE_TYPES, GPY_LANG_TO_LOCALE
from hoyo_buddy.draw.main_funcs import (
    draw_apc_shadow_card,
    draw_img_theater_card,
    draw_moc_card,
    draw_pure_fiction_card,
    draw_spiral_abyss_card,
)
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.exceptions import NoChallengeDataError
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.types import ChallengeWithBuff, ChallengeWithLang

from ...bot.error_handler import get_error_embed
from ...db.models import ChallengeHistory, get_dyk
from ...enums import ChallengeType
from ...utils import get_floor_difficulty
from ..components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    from collections.abc import Sequence

    import aiohttp
    from discord import File, Locale, Member, User

    from hoyo_buddy.db.models import HoyoAccount
    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Challenge, Interaction


class BuffView(View):
    def __init__(
        self,
        challenge: ChallengeWithBuff,
        season: StarRailChallengeSeason | None,
        *,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self._challenge = challenge
        self._season = season
        self.buffs, self._buff_usage = self.calc_buff_usage()
        self.add_item(BuffSelector(list(self.buffs.values())))

    def get_buff_embed(self, buff: ChallengeBuff | TheaterBuff, floors: str) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=buff.name,
            description=remove_html_tags(buff.description),
        )
        embed.add_field(name=LocaleStr(key="challenge_view.buff_used_in"), value=floors)
        embed.set_thumbnail(url=buff.icon)
        return embed

    def calc_buff_usage(
        self,
    ) -> tuple[dict[str, ChallengeBuff | TheaterBuff], defaultdict[str, list[str]]]:
        buffs: dict[str, ChallengeBuff | TheaterBuff] = {}  # Buff name to buff object
        buff_usage: defaultdict[str, list[str]] = defaultdict(list)  # Buff name to floor names

        if isinstance(self._challenge, StarRailPureFiction | StarRailAPCShadow):
            assert self._season is not None

            for floor in reversed(self._challenge.floors):
                n1_buff = floor.node_1.buff
                if n1_buff is not None:
                    team_str = LocaleStr(key="challenge_view.team", team=1).translate(
                        self.translator, self.locale
                    )

                    floor_name = get_floor_difficulty(floor.name, self._season.name)
                    buff_usage[n1_buff.name].append(f"{floor_name} ({team_str})")
                    if n1_buff.name not in buffs:
                        buffs[n1_buff.name] = n1_buff

                n2_buff = floor.node_2.buff
                if n2_buff is not None:
                    team_str = LocaleStr(key="challenge_view.team", team=2).translate(
                        self.translator, self.locale
                    )

                    floor_name = get_floor_difficulty(floor.name, self._season.name)
                    buff_usage[n2_buff.name].append(f"{floor_name} ({team_str})")
                    if n2_buff.name not in buffs:
                        buffs[n2_buff.name] = n2_buff
        else:
            for act in reversed(self._challenge.acts):
                act_buffs = list(act.wondroud_booms) + list(act.mystery_caches)
                for buff in act_buffs:
                    act_name = LocaleStr(
                        key="img_theater_act_block_title", act=act.round_id
                    ).translate(self.translator, self.locale)
                    buff_usage[buff.name].append(act_name)
                    if buff.name not in buffs:
                        buffs[buff.name] = buff

        return buffs, buff_usage


class BuffSelector(Select[BuffView]):
    def __init__(self, buffs: list[ChallengeBuff | TheaterBuff]) -> None:
        super().__init__(
            placeholder=LocaleStr(key="challenge_view.buff_select.placeholder"),
            options=[
                SelectOption(
                    label=buff.name,
                    description=remove_html_tags(buff.description[:100]),
                    value=buff.name,
                    default=buff.name == buffs[0].name,
                )
                for buff in buffs
            ],
        )

    async def callback(self, i: Interaction) -> None:
        buff = self.view.buffs[self.values[0]]
        embed = self.view.get_buff_embed(buff, ", ".join(self.view._buff_usage[buff.name]))
        await i.response.edit_message(embed=embed)


class ChallengeView(View):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        *,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._account = account
        self._dark_mode = dark_mode

        self._challenge_type: ChallengeType | None = None
        self._season_ids: dict[ChallengeType, int] = {}
        """The user's selected season ID for a challange type"""
        self._challenge_cache: defaultdict[ChallengeType, dict[int, ChallengeWithLang]] = (
            defaultdict(dict)
        )
        """Cache of challenges for each season ID and challange type"""
        self._characters: list[GICharacter] = []

    @property
    def challenge_type(self) -> ChallengeType:
        if self._challenge_type is None:
            msg = "Challenge type is not set"
            raise ValueError(msg)
        return self._challenge_type

    @property
    def challenge(self) -> ChallengeWithLang | None:
        if self.challenge_type not in self._season_ids:
            return None
        return self._challenge_cache[self.challenge_type].get(self.season_id)

    @property
    def season_id(self) -> int:
        return self._season_ids[self.challenge_type]

    @season_id.setter
    def season_id(self, value: int) -> None:
        self._season_ids[self.challenge_type] = value

    def _get_season_id(self, challenge: Challenge, previous: bool) -> int:
        if isinstance(challenge, SpiralAbyss):
            return challenge.season
        if isinstance(challenge, ImgTheaterData):
            return challenge.schedule.id
        index = 1 if previous else 0
        return challenge.seasons[index].id

    async def _fetch_data(self) -> None:
        if self.challenge is not None:
            return

        client = self._account.client
        client.set_lang(self.locale)

        if (
            self.challenge_type in {ChallengeType.SPIRAL_ABYSS, ChallengeType.IMG_THEATER}
            and not self._characters
        ):
            self._characters = list(await client.get_genshin_characters(self._account.uid))

        for previous in (False, True):
            if self.challenge_type is ChallengeType.SPIRAL_ABYSS:
                challenge = await client.get_genshin_spiral_abyss(
                    self._account.uid, previous=previous
                )
                if not challenge.ranks:
                    await client.get_record_cards()
                    challenge = await client.get_genshin_spiral_abyss(
                        self._account.uid, previous=previous
                    )
            elif self.challenge_type is ChallengeType.MOC:
                challenge = await client.get_starrail_challenge(
                    self._account.uid, previous=previous
                )
            elif self.challenge_type is ChallengeType.PURE_FICTION:
                challenge = await client.get_starrail_pure_fiction(
                    self._account.uid, previous=previous
                )
            elif self.challenge_type is ChallengeType.APC_SHADOW:
                challenge = await client.get_starrail_apc_shadow(
                    self._account.uid, previous=previous
                )
            elif self.challenge_type is ChallengeType.IMG_THEATER:
                challenges = (
                    await client.get_imaginarium_theater(self._account.uid, previous=previous)
                ).datas
                challenge = max(challenges, key=lambda c: c.stats.difficulty.value)
            else:
                msg = f"Invalid challenge type: {self._challenge_type}"
                raise ValueError(msg)

            try:
                season_id = self._get_season_id(challenge, previous)
            except IndexError:
                # No previous season
                continue

            # Save data to db
            await ChallengeHistory.add_data(
                uid=self._account.uid,
                challenge_type=self.challenge_type,
                season_id=season_id,
                data=challenge,
                lang=client.lang,
            )

    def _check_challlenge_data(self, challenge: Challenge | None) -> None:
        if challenge is None:
            raise NoChallengeDataError(self.challenge_type)
        if isinstance(challenge, SpiralAbyss):
            if challenge.max_floor == "0-0":
                raise NoChallengeDataError(ChallengeType.SPIRAL_ABYSS)
        elif not challenge.has_data:
            raise NoChallengeDataError(self.challenge_type)

    def _get_season(self, challenge: Challenge) -> StarRailChallengeSeason:
        if isinstance(challenge, SpiralAbyss | ImgTheaterData):
            msg = f"Can't get season for {self.challenge_type}"
            raise TypeError(msg)

        result = next((season for season in challenge.seasons if season.id == self.season_id), None)
        if result is None:
            msg = f"Can't find season with ID {self.season_id}"
            raise ValueError(msg)
        return result

    async def _draw_card(
        self,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ThreadPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> File:
        if isinstance(self.challenge, SpiralAbyss):
            return await draw_spiral_abyss_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=GPY_LANG_TO_LOCALE[self.challenge.lang],
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                self.challenge,
                self._characters,
                self.translator,
            )
        if isinstance(self.challenge, StarRailChallenge):
            return await draw_moc_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=GPY_LANG_TO_LOCALE[self.challenge.lang],
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                self.challenge,
                self._get_season(self.challenge),
                self.translator,
            )
        if isinstance(self.challenge, StarRailPureFiction):
            return await draw_pure_fiction_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=GPY_LANG_TO_LOCALE[self.challenge.lang],
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                self.challenge,
                self._get_season(self.challenge),
                self.translator,
            )
        if isinstance(self.challenge, StarRailAPCShadow):
            return await draw_apc_shadow_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=GPY_LANG_TO_LOCALE[self.challenge.lang],
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                self.challenge,
                self._get_season(self.challenge),
                self.translator,
            )
        if isinstance(self.challenge, ImgTheaterData):
            return await draw_img_theater_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=GPY_LANG_TO_LOCALE[self.challenge.lang],
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                self.challenge,
                {chara.id: chara.constellation for chara in self._characters},
                self.translator,
            )

        msg = f"Invalid challenge type: {self._challenge_type}"
        raise ValueError(msg)

    def _add_items(self) -> None:
        self.add_item(ChallengeTypeSelect(GAME_CHALLENGE_TYPES[self._account.game]))
        self.add_item(PhaseSelect())
        self.add_item(ViewBuffs())

    async def update(
        self, item: Select[ChallengeView] | Button[ChallengeView], i: Interaction
    ) -> None:
        try:
            self._check_challlenge_data(self.challenge)
            file_ = await self._draw_card(i.client.session, i.client.executor, i.client.loop)
        except NoChallengeDataError as e:
            await item.unset_loading_state(i)
            embed, _ = get_error_embed(e, self.locale, self.translator)
            await i.edit_original_response(embed=embed, view=self, attachments=[])
            return
        except Exception:
            await item.unset_loading_state(i)
            raise

        embed = DefaultEmbed(self.locale, self.translator).add_acc_info(self._account)
        embed.set_image(url="attachment://challenge.webp")

        await item.unset_loading_state(i, embed=embed, attachments=[file_])

    async def start(self, i: Interaction) -> None:
        self._add_items()
        self.message = await i.edit_original_response(view=self, content=await get_dyk(i))


class PhaseSelect(Select[ChallengeView]):
    def __init__(self) -> None:
        super().__init__(
            placeholder=LocaleStr(key="abyss.phase_select.placeholder"),
            options=[SelectOption(label="initialized", value="0")],
            disabled=True,
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
    def __init__(self, types: Sequence[ChallengeType]) -> None:
        super().__init__(
            placeholder=LocaleStr(key="challenge_type_select.placeholder"),
            options=[SelectOption(label=EnumStr(type_), value=type_.value) for type_ in types],
        )

    async def callback(self, i: Interaction) -> None:
        self.view._challenge_type = ChallengeType(self.values[0])

        phase_select: PhaseSelect = self.view.get_item("challenge_view.phase_select")
        phase_select.disabled = False

        await self.set_loading_state(i)
        try:
            await self.view._fetch_data()
        except Exception:
            await self.unset_loading_state(i)
            raise

        histories = await ChallengeHistory.filter(
            uid=self.view._account.uid, challenge_type=self.view.challenge_type
        )
        for history in histories:
            self.view._challenge_cache[self.view.challenge_type][history.season_id] = (
                history.parsed_data
            )

        if self.view.challenge_type not in self.view._season_ids:
            self.view.season_id = histories[0].season_id

        phase_select.set_options(histories)
        phase_select.translate(self.view.locale, self.view.translator)
        phase_select.update_options_defaults(values=[str(self.view.season_id)])

        self.view._item_states["challenge_view.view_buffs"] = not isinstance(
            self.view.challenge, ChallengeWithBuff
        )

        await self.view.update(self, i)


class ViewBuffs(Button[ChallengeView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="challenge_view.view_buffs"),
            style=discord.ButtonStyle.blurple,
            disabled=True,
            custom_id="challenge_view.view_buffs",
        )

    async def callback(self, i: Interaction) -> None:
        assert isinstance(self.view.challenge, ChallengeWithBuff)

        season = (
            None
            if self.view.challenge_type is ChallengeType.IMG_THEATER
            else self.view._get_season(self.view.challenge)
        )
        view = BuffView(
            self.view.challenge,
            season,
            author=i.user,
            locale=self.view.locale,
            translator=self.view.translator,
        )
        if not view.buffs:
            self.disabled = True
            return await i.response.edit_message(view=self.view)

        first_buff = next(iter(view.buffs.values()))
        embed = view.get_buff_embed(first_buff, ", ".join(view._buff_usage[first_buff.name]))
        await i.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await i.original_response()
        return None
