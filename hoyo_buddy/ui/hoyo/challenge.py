from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Final, TypeAlias

from genshin.models import (
    Character as GICharacter,
)
from genshin.models import (
    SpiralAbyss,
    StarRailChallenge,
    StarRailPureFiction,
)

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.draw.main_funcs import draw_moc_card, draw_pure_fiction_card, draw_spiral_abyss_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.exceptions import NoChallengeDataError
from hoyo_buddy.models import DrawInput

from ...bot.error_handler import get_error_embed
from ...enums import ChallengeType, Game
from ..components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures

    import aiohttp
    from discord import File, Locale, Member, User

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.db.models import HoyoAccount

Challenge: TypeAlias = StarRailChallenge | SpiralAbyss | StarRailPureFiction

GAME_TO_CHALLENGE_TYPES: Final[dict[Game, list[ChallengeType]]] = {
    Game.GENSHIN: [ChallengeType.SPIRAL_ABYSS],
    Game.STARRAIL: [ChallengeType.MOC, ChallengeType.PURE_FICTION],
}


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
        self._challenge_type: ChallengeType | None = None
        self._dark_mode = dark_mode
        self._previous: dict[ChallengeType, bool] = dict.fromkeys(ChallengeType, False)

        self._challenges: defaultdict[ChallengeType, dict[bool, Challenge]] = defaultdict(dict)
        self._characters: list[GICharacter] = []

    async def _fetch_data(self) -> None:
        assert self._challenge_type is not None
        client = self._account.client

        previous = self._previous[self._challenge_type]
        if previous not in self._challenges[self._challenge_type]:
            if self._challenge_type is ChallengeType.SPIRAL_ABYSS:
                challenge = await client.get_genshin_spiral_abyss(
                    self._account.uid, previous=previous
                )
                if not challenge.ranks:
                    await client.get_record_cards()
                    challenge = await client.get_genshin_spiral_abyss(
                        self._account.uid, previous=previous
                    )
                if not self._characters:
                    self._characters = list(await client.get_genshin_characters(self._account.uid))
            elif self._challenge_type is ChallengeType.MOC:
                challenge = await client.get_starrail_challenge(
                    self._account.uid, previous=previous
                )
            elif self._challenge_type is ChallengeType.PURE_FICTION:
                challenge = await client.get_starrail_pure_fiction(
                    self._account.uid, previous=previous
                )
            else:
                msg = f"Invalid challenge type: {self._challenge_type}"
                raise ValueError(msg)

            self._challenges[self._challenge_type] = {previous: challenge}

        challenge = self._challenges[self._challenge_type][previous]
        if isinstance(challenge, SpiralAbyss) and challenge.max_floor == "0-0":
            raise NoChallengeDataError(ChallengeType.SPIRAL_ABYSS)
        elif isinstance(challenge, StarRailChallenge) and not challenge.has_data:
            raise NoChallengeDataError(ChallengeType.MOC)
        elif isinstance(challenge, StarRailPureFiction) and not challenge.has_data:
            raise NoChallengeDataError(ChallengeType.PURE_FICTION)

    async def _draw_card(
        self,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> File:
        assert self._challenge_type is not None

        previous = self._previous[self._challenge_type]
        challenge = self._challenges[self._challenge_type][previous]

        if isinstance(challenge, SpiralAbyss):
            return await draw_spiral_abyss_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                challenge,
                self._characters,
                self.translator,
            )
        elif isinstance(challenge, StarRailChallenge):
            return await draw_moc_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                challenge,
                1 if previous else 0,
                self.translator,
            )
        elif isinstance(challenge, StarRailPureFiction):
            return await draw_pure_fiction_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="challenge.webp",
                    executor=executor,
                    loop=loop,
                ),
                challenge,
                1 if previous else 0,
                self.translator,
            )

        msg = f"Invalid challenge type: {self._challenge_type}"
        raise ValueError(msg)

    def _add_buff_detail(self, embed: DefaultEmbed) -> DefaultEmbed:
        assert self._challenge_type is not None

        previous = self._previous[self._challenge_type]
        challenge = self._challenges[self._challenge_type][previous]

        if not isinstance(challenge, StarRailPureFiction):
            return embed

        season = challenge.seasons[1 if previous else 0]
        buffs: dict[str, str] = {}  # Buff name to description
        buff_usage: defaultdict[str, list[str]] = defaultdict(list)  # Buff name to floor names

        for floor in reversed(challenge.floors):
            n1_buff = floor.node_1.buff
            if n1_buff is not None:
                team_str = LocaleStr(
                    "team {team}",
                    key="challenge_view.team",
                    team=1,
                ).translate(self.translator, self.locale)

                floor_name = floor.name.replace(season.name, "").strip()
                buff_usage[n1_buff.name].append(f"{floor_name} ({team_str})")
                if n1_buff.name not in buffs:
                    buffs[n1_buff.name] = n1_buff.description

            n2_buff = floor.node_2.buff
            if n2_buff is not None:
                team_str = LocaleStr(
                    "team {team}",
                    key="challenge_view.team",
                    team=2,
                ).translate(self.translator, self.locale)

                floor_name = floor.name.replace(season.name, "").strip()
                buff_usage[n2_buff.name].append(f"{floor_name} ({team_str})")
                if n2_buff.name not in buffs:
                    buffs[n2_buff.name] = n2_buff.description

        for buff in buffs:
            used_in = LocaleStr(
                "Used in: {floors}",
                key="challenge_view.buff_used_in",
                floors=", ".join(buff_usage[buff]),
            ).translate(self.translator, self.locale)
            embed.add_field(name=buff, value=f"{used_in}\n{buffs[buff]}", inline=False)

        return embed

    def _add_items(self) -> None:
        self.add_item(ChallengeTypeSelect(GAME_TO_CHALLENGE_TYPES[self._account.game]))
        self.add_item(PhaseSelect(False))

    async def update(
        self,
        item: Select[ChallengeView] | Button[ChallengeView],
        i: INTERACTION,
    ) -> None:
        assert self._challenge_type is not None

        phase_select: PhaseSelect = self.get_item("challenge_view.phase_select")
        phase_select.disabled = self._challenge_type is None
        phase_select.update_options_defaults(
            values=["previous" if self._previous[self._challenge_type] else "current"]
        )

        await item.set_loading_state(i)
        try:
            await self._fetch_data()
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
        embed = self._add_buff_detail(embed)
        embed.set_image(url="attachment://challenge.webp")

        await item.unset_loading_state(i, embed=embed, attachments=[file_])

    async def start(self, i: INTERACTION) -> None:
        self._add_items()
        await i.edit_original_response(view=self)
        self.message = await i.original_response()


class PhaseSelect(Select[ChallengeView]):
    def __init__(self, previous: bool) -> None:
        super().__init__(
            placeholder=LocaleStr("Select a phase", key="abyss.phase_select.placeholder"),
            options=[
                SelectOption(
                    label=LocaleStr("Current phase", key="abyss.current"),
                    value="current",
                    default=not previous,
                ),
                SelectOption(
                    label=LocaleStr("Previous phase", key="abyss.previous"),
                    value="previous",
                    default=previous,
                ),
            ],
            disabled=True,
            custom_id="challenge_view.phase_select",
        )

    async def callback(self, i: INTERACTION) -> None:
        assert self.view._challenge_type is not None

        self.view._previous[self.view._challenge_type] = self.values[0] == "previous"
        await self.view.update(self, i)


class ChallengeTypeSelect(Select[ChallengeView]):
    def __init__(self, types: list[ChallengeType]) -> None:
        super().__init__(
            placeholder=LocaleStr("Select a game mode", key="challenge_type_select.placeholder"),
            options=[
                SelectOption(
                    label=LocaleStr(type_.value, warn_no_key=False),
                    value=type_.value,
                )
                for type_ in types
            ],
        )

    async def callback(self, i: INTERACTION) -> None:
        self.view._challenge_type = ChallengeType(self.values[0])
        await self.view.update(self, i)
