from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Final, TypeAlias

from discord import ButtonStyle, Locale
from genshin.models import Character as GICharacter
from genshin.models import FullBattlesuit as HonkaiCharacter
from genshin.models import StarRailDetailCharacter as HSRCharacter
from genshin.models import ZZZFullAgent as ZZZCharacter
from genshin.models import ZZZSpecialty

from hoyo_buddy.draw.main_funcs import (
    draw_gi_characters_card,
    draw_honkai_suits_card,
    draw_hsr_characters_card,
    draw_zzz_characters_card,
)
from hoyo_buddy.enums import Game, GenshinElement, HSRElement, HSRPath, Platform, ZZZElement
from hoyo_buddy.l10n import EnumStr, LocaleStr

from ...constants import (
    TRAILBLAZER_IDS,
    TRAVELER_IDS,
    UTC_8,
    YATTA_PATH_TO_GPY_PATH,
    contains_traveler_id,
)
from ...db.models import JSONFile
from ...embeds import DefaultEmbed
from ...emojis import (
    ZZZ_SPECIALTY_EMOJIS,
    get_gi_element_emoji,
    get_hsr_element_emoji,
    get_hsr_path_emoji,
    get_zzz_element_emoji,
)
from ...exceptions import ActionInCooldownError, FeatureNotImplementedError, NoCharsFoundError
from ...hoyo.clients.ambr import AmbrAPIClient
from ...hoyo.clients.yatta import YattaAPIClient
from ...icons import LOADING_ICON
from ...models import DrawInput, UnownedCharacter
from ...utils import get_now
from ..components import Button, Select, SelectOption, ToggleButton, View

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    from collections.abc import Iterable, Sequence

    import aiohttp
    from discord import File, Member, User

    from hoyo_buddy.db.models import HoyoAccount
    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction

GAME_FOOTERS: Final[dict[Game, tuple[str, ...]]] = {
    Game.GENSHIN: (
        "hsr.normal_attack",
        "gi.skill",
        "gi.burst",
    ),
    Game.STARRAIL: (
        "hsr.normal_attack",
        "hsr.skill",
        "hsr.ultimate",
        "hsr.talent",
    ),
    Game.ZZZ: (
        "zzz.basic",
        "zzz.dodge",
        "zzz.assist",
        "zzz.special",
        "zzz.chain",
        "zzz.core",
    ),
}


class GIFilter(StrEnum):
    NONE = "none"
    MAX_FRIENDSHIP = "max_friendship"
    NOT_MAX_FRIENDSHIP = "not_max_friendship"


class GISorter(StrEnum):
    ELEMENT = "element"
    LEVEL = "level"
    RARITY = "rarity"
    FRIENDSHIP = "friendship"
    CONSTELLATION = "constellation"


class HSRSorter(StrEnum):
    ELEMENT = "element"
    PATH = "path"
    RARITY = "rarity"
    LEVEL = "level"
    EIDOLON = "eidolon"


class ZZZSorter(StrEnum):
    ELEMENT = "element"
    SPECIALTY = "speciality"
    FACTION = "faction"
    RARITY = "rarity"
    LEVEL = "level"
    MINDSCAPE_CINEMA = "mindscape_cinema"


class HonkaiSorter(StrEnum):
    LEVEL = "level"
    RARITY = "rarity"


Character: TypeAlias = (
    GICharacter | HSRCharacter | UnownedCharacter | ZZZCharacter | HonkaiCharacter
)
Sorter: TypeAlias = GISorter | HSRSorter | ZZZSorter | HonkaiSorter


class CharactersView(View):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        element_char_counts: dict[str, int],
        path_char_counts: dict[str, int],
        faction_char_counts: dict[str, int],
        *,
        author: User | Member | None,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._account = account
        self._game = account.game
        self._dark_mode = dark_mode
        self._element_char_counts = element_char_counts
        self._path_char_counts = path_char_counts
        self._faction_char_counts = faction_char_counts

        self._gi_characters: list[GICharacter | UnownedCharacter] = []
        self._hsr_characters: list[HSRCharacter | UnownedCharacter] = []
        self._zzz_characters: list[ZZZCharacter] = []
        self._honkai_characters: list[HonkaiCharacter] = []

        self._filter: GIFilter = GIFilter.NONE
        self._element_filters: list[GenshinElement | HSRElement | ZZZElement] = []
        self._path_filters: list[HSRPath] = []

        self._speciality_filters: list[ZZZSpecialty] = []
        self._faction_filters: list[str] = []
        self._faction_l10n: dict[str, str] = {}

        self._sorter: Sorter
        if self._game is Game.GENSHIN:
            self._sorter = GISorter.ELEMENT
        elif self._game is Game.STARRAIL:
            self._sorter = HSRSorter.ELEMENT
        elif self._game is Game.ZZZ:
            self._sorter = ZZZSorter.ELEMENT
        elif self._game is Game.HONKAI:
            self._sorter = HonkaiSorter.LEVEL

    async def _get_gi_pc_icons(self) -> dict[str, str]:
        if self._account.platform is Platform.HOYOLAB:
            await self._account.client.update_pc_icons()

        pc_icons = await JSONFile.read("pc_icons.json")

        is_missing = any(str(c.id) not in pc_icons for c in self._gi_characters)
        if is_missing:
            async with AmbrAPIClient(translator=self.translator) as client:
                ambr_charas = await client.fetch_characters()
                for chara in self._gi_characters:
                    if str(chara.id) in pc_icons:
                        continue
                    ambr_chara = next((c for c in ambr_charas if c.id == chara.id), None)
                    if ambr_chara is None:
                        continue
                    pc_icons[str(chara.id)] = ambr_chara.icon
                await JSONFile.write("pc_icons.json", pc_icons)

            pc_icons = await JSONFile.read("pc_icons.json")

        return pc_icons

    def _apply_gi_filter(
        self, characters: Sequence[GICharacter | UnownedCharacter]
    ) -> Sequence[GICharacter | UnownedCharacter]:
        if self._filter is GIFilter.MAX_FRIENDSHIP:
            return [c for c in characters if isinstance(c, UnownedCharacter) or c.friendship == 10]

        if GIFilter.NOT_MAX_FRIENDSHIP is self._filter:
            return [c for c in characters if isinstance(c, UnownedCharacter) or c.friendship != 10]

        return characters

    def _apply_element_filters(
        self, characters: Sequence[GICharacter | HSRCharacter | ZZZCharacter | UnownedCharacter]
    ) -> Sequence[Character]:
        if not self._element_filters:
            return characters

        elements = [element_filter.value.lower() for element_filter in self._element_filters]
        if HSRElement.THUNDER in self._element_filters:
            elements.append("lightning")  # Hoyo seriously can't decide on a name

        result: list[Character] = []
        for character in characters:
            if isinstance(character.element, str):
                element = character.element.lower()
            else:
                element = character.element.name.lower()
            if element in elements:
                result.append(character)

        return result

    def _apply_path_filters(
        self, characters: Sequence[HSRCharacter | UnownedCharacter]
    ) -> Sequence[HSRCharacter | UnownedCharacter]:
        if not self._path_filters:
            return characters

        paths = [path_filter.value.lower() for path_filter in self._path_filters]
        return [c for c in characters if c.path.name.lower() in paths]

    def _apply_speciality_filters(
        self, characters: Sequence[ZZZCharacter]
    ) -> Sequence[ZZZCharacter]:
        if not self._speciality_filters:
            return characters

        specialities = [speciality_filter.value for speciality_filter in self._speciality_filters]
        return [c for c in characters if c.specialty.value in specialities]

    def _apply_faction_filters(self, characters: Sequence[ZZZCharacter]) -> Sequence[ZZZCharacter]:
        if not self._faction_filters:
            return characters

        return [c for c in characters if c.faction_name in self._faction_filters]

    def _apply_gi_sorter(
        self, characters: Sequence[GICharacter | UnownedCharacter]
    ) -> Sequence[GICharacter | UnownedCharacter]:
        if self._sorter is GISorter.ELEMENT or self._sorter is HSRSorter.ELEMENT:
            return sorted(characters, key=lambda c: c.element.lower())

        if self._sorter is GISorter.LEVEL or self._sorter is HSRSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self._sorter is GISorter.RARITY or self._sorter is HSRSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        if self._sorter is GISorter.FRIENDSHIP:
            return sorted(characters, key=lambda c: c.friendship, reverse=True)

        return sorted(characters, key=lambda c: c.constellation, reverse=True)

    def _apply_hsr_sorter(
        self, characters: Sequence[HSRCharacter | UnownedCharacter]
    ) -> Sequence[HSRCharacter | UnownedCharacter]:
        if self._sorter is HSRSorter.PATH:
            return sorted(characters, key=lambda c: c.path)

        if self._sorter is HSRSorter.EIDOLON:
            return sorted(characters, key=lambda c: c.rank, reverse=True)

        if self._sorter is HSRSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self._sorter is HSRSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        return sorted(characters, key=lambda c: c.element.lower())

    def _apply_zzz_sorter(self, characters: Sequence[ZZZCharacter]) -> Sequence[ZZZCharacter]:
        if self._sorter is ZZZSorter.ELEMENT:
            return sorted(characters, key=lambda c: c.element)

        if self._sorter is ZZZSorter.SPECIALTY:
            return sorted(characters, key=lambda c: c.specialty)

        if self._sorter is ZZZSorter.FACTION:
            return sorted(characters, key=lambda c: c.faction_name)

        if self._sorter is ZZZSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self._sorter is ZZZSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        return sorted(characters, key=lambda c: c.rank, reverse=True)

    def _apply_honkai_sorter(
        self, characters: Sequence[HonkaiCharacter]
    ) -> Sequence[HonkaiCharacter]:
        if self._sorter is HonkaiSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        return sorted(characters, key=lambda c: c.rarity, reverse=True)

    def _get_filtered_sorted_characters(self) -> Sequence[Character]:
        if self._game is Game.GENSHIN:
            characters = self._apply_gi_sorter(
                self._apply_element_filters(self._apply_gi_filter(self._gi_characters))  # pyright: ignore [reportArgumentType]
            )
        elif self._game is Game.STARRAIL:
            characters = self._apply_hsr_sorter(
                self._apply_element_filters(self._apply_path_filters(self._hsr_characters))  # pyright: ignore [reportArgumentType]
            )
        elif self._game is Game.ZZZ:
            characters = self._apply_zzz_sorter(
                self._apply_element_filters(
                    self._apply_speciality_filters(
                        self._apply_faction_filters(self._zzz_characters)
                    )  # pyright: ignore [reportArgumentType]
                )
            )
        elif self._game is Game.HONKAI:
            characters = self._apply_honkai_sorter(self._honkai_characters)
        else:
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

        if not characters:
            raise NoCharsFoundError
        return characters

    async def _draw_card(
        self,
        session: aiohttp.ClientSession,
        characters: Sequence[Character],
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> File:
        if self._game is Game.GENSHIN:
            pc_icons = await self._get_gi_pc_icons()
            talent_level_data = await JSONFile.read(f"talent_levels/gi_{self._account.uid}.json")

            file_ = await draw_gi_characters_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="characters.webp",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
                talent_level_data,
                pc_icons,
                self.translator,
            )
        elif self._game is Game.STARRAIL:
            pc_icons = {
                str(
                    c.id
                ): f"https://raw.githubusercontent.com/FortOfFans/HSR/main/spriteoutput/avatariconteam/{c.id}.png"
                for c in characters
            }
            file_ = await draw_hsr_characters_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="characters.webp",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
                pc_icons,
                self.translator,
            )
        elif self._game is Game.ZZZ:
            file_ = await draw_zzz_characters_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="characters.webp",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
                self.translator,
            )
        elif self._game is Game.HONKAI:
            file_ = await draw_honkai_suits_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="characters.webp",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
                self.translator,
            )
        else:
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

        return file_

    def _get_embed(self, char_num: int) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="characters.embed.title"),
        )
        embed.set_image(url="attachment://characters.webp")
        embed.add_acc_info(self._account)

        if self._game is Game.HONKAI:
            return embed

        if self._filter in {GIFilter.MAX_FRIENDSHIP, GIFilter.NOT_MAX_FRIENDSHIP}:
            total_chars = (
                sum(
                    1
                    for c in self._gi_characters
                    if GenshinElement(c.element.title()) in self._element_filters
                )
                if self._element_filters
                else len(self._gi_characters)
            )
            if self._filter is GIFilter.MAX_FRIENDSHIP:
                embed.add_field(
                    name=LocaleStr(
                        key="characters.embed.element_max_friendship",
                        element=[EnumStr(element) for element in self._element_filters],
                    )
                    if self._element_filters
                    else LocaleStr(key="characters.embed.max_friendship"),
                    value=f"{char_num}/{total_chars}",
                    inline=False,
                )
            else:
                embed.add_field(
                    name=LocaleStr(
                        key="characters.embed.element_not_max_friendship",
                        element=[EnumStr(element) for element in self._element_filters],
                    )
                    if self._element_filters
                    else LocaleStr(key="characters.embed.not_max_friendship"),
                    value=f"{char_num}/{total_chars}",
                    inline=False,
                )

        if self._element_filters and self._filter is GIFilter.NONE:
            total_chars = sum(
                self._element_char_counts[element.value.lower()]
                for element in self._element_filters
            )
            embed.add_field(
                name=LocaleStr(
                    key="characters.embed.filter_text",
                    filter=[EnumStr(element) for element in self._element_filters],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._path_filters and self._filter is GIFilter.NONE:
            total_chars = sum(
                self._path_char_counts[path.value.lower()] for path in self._path_filters
            )
            embed.add_field(
                name=LocaleStr(
                    key="characters.embed.filter_text",
                    filter=[EnumStr(path) for path in self._path_filters],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._faction_filters and self._filter is GIFilter.NONE:
            total_chars = sum(
                self._faction_char_counts[self._faction_l10n[faction].lower()]
                for faction in self._faction_filters
            )
            embed.add_field(
                name=LocaleStr(
                    key="characters.embed.filter_text",
                    filter="/".join(self._faction_filters),
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if (
            self._filter is GIFilter.NONE
            and not self._element_filters
            and not self._path_filters
            and not self._speciality_filters
            and not self._faction_filters
        ):
            total_chars = sum(self._element_char_counts.values())
            if self._game in {Game.GENSHIN, Game.STARRAIL}:
                # Traveler/Trailblazer
                total_chars += 1
            embed.add_field(
                name=LocaleStr(key="characters.embed.owned_characters"),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._game in GAME_FOOTERS:
            footer = LocaleStr(
                key="characters.level_order.footer",
                order=[LocaleStr(key=key) for key in GAME_FOOTERS[self._game]],
            ).translate(self.translator, self.locale)
            if self._game in {Game.STARRAIL, Game.ZZZ}:
                footer += "\n" + LocaleStr(key="characters.extra_detail.footer").translate(
                    self.translator, self.locale
                )
            embed.set_footer(text=footer)

        return embed

    def _add_items(self) -> None:
        if self._game is Game.GENSHIN:
            self.add_item(ShowOwnedOnly())
            self.add_item(GIFilterSelector())
            self.add_item(ElementFilterSelector(GenshinElement))
            self.add_item(SorterSelector(self._sorter, self._game))
            self.add_item(UpdateTalentData())
        elif self._game is Game.STARRAIL:
            self.add_item(ShowOwnedOnly())
            self.add_item(PathFilterSelector())
            self.add_item(ElementFilterSelector(HSRElement))
            self.add_item(SorterSelector(self._sorter, self._game))
        elif self._game is Game.ZZZ:
            self.add_item(ElementFilterSelector(ZZZElement))
            self.add_item(SpecialtyFilterSelector(self._zzz_characters))
            self.add_item(FactionFilterSelector(self._zzz_characters))
            self.add_item(SorterSelector(self._sorter, self._game))
        elif self._game is Game.HONKAI:
            self.add_item(SorterSelector(self._sorter, self._game))

    async def start(self, i: Interaction, *, show_first_time_msg: bool = False) -> None:
        if show_first_time_msg:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                description=LocaleStr(key="characters.first_time.embed.description"),
            ).set_author(
                icon_url=LOADING_ICON,
                name=LocaleStr(key="characters.first_time.title"),
            )
            await i.edit_original_response(embed=embed)

        client = self._account.client
        client.set_lang(self.locale)

        if self._game is Game.GENSHIN:
            self._gi_characters = list(await client.get_genshin_characters(self._account.uid))

            # Find traveler element and add 1 to the element char count
            for character in self._gi_characters:
                if character.id in TRAVELER_IDS:
                    self._element_char_counts[character.element.lower()] += 1
                    break

        elif self._game is Game.STARRAIL:
            self._hsr_characters = list(
                (await client.get_starrail_characters(self._account.uid)).avatar_list
            )

            # Find traiblazer element and path and add 1 to the count
            for character in self._hsr_characters:
                if character.id in TRAILBLAZER_IDS:
                    self._element_char_counts[character.element.lower()] += 1
                    self._path_char_counts[character.path.name.lower()] += 1
                    break

        elif self._game is Game.ZZZ:
            agents = await client.get_zzz_agents()
            self._zzz_characters = full_agents = list(
                await client.get_zzz_agent_info([agent.id for agent in agents])
            )
            client.set_lang(Locale.american_english)
            en_full_agents = list(await client.get_zzz_agent_info([agent.id for agent in agents]))
            self._faction_l10n = {
                agent.faction_name: en_agent.faction_name
                for agent, en_agent in zip(full_agents, en_full_agents, strict=False)
            }
        elif self._game is Game.HONKAI:
            self._honkai_characters = list(await client.get_honkai_battlesuits(self._account.uid))
        else:
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

        characters = self._get_filtered_sorted_characters()
        file_ = await self._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self._get_embed(len([c for c in characters if not isinstance(c, UnownedCharacter)]))

        self._add_items()
        await i.edit_original_response(attachments=[file_], view=self, embed=embed)
        self.message = await i.original_response()

    async def item_callback(
        self, i: Interaction, item: Button | Select, *, set_loading_state: bool = True
    ) -> None:
        characters = self._get_filtered_sorted_characters()
        if set_loading_state:
            await item.set_loading_state(i)
        file_ = await self._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self._get_embed(len([c for c in characters if not isinstance(c, UnownedCharacter)]))
        await item.unset_loading_state(i, attachments=[file_], embed=embed)


class GIFilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr(key="characters.filter.none"),
                value=GIFilter.NONE,
                default=True,
            ),
            SelectOption(
                label=LocaleStr(key="characters.filter.max_friendship"),
                value=GIFilter.MAX_FRIENDSHIP,
            ),
            SelectOption(
                label=LocaleStr(key="characters.filter.not_max_friendship"),
                value=GIFilter.NOT_MAX_FRIENDSHIP,
            ),
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.placeholder"),
            options=options,
        )

    async def callback(self, i: Interaction) -> None:
        self.view._filter = GIFilter(self.values[0])
        await self.view.item_callback(i, self)


class ElementFilterSelector(Select[CharactersView]):
    def __init__(self, elements: Iterable[GenshinElement | HSRElement | ZZZElement]) -> None:
        def get_element_emoji(element: GenshinElement | HSRElement | ZZZElement) -> str:
            if isinstance(element, GenshinElement):
                return get_gi_element_emoji(element)
            if isinstance(element, HSRElement):
                return get_hsr_element_emoji(element)
            return get_zzz_element_emoji(element)

        options = [
            SelectOption(
                label=EnumStr(element),
                value=element.value,
                emoji=get_element_emoji(element),
            )
            for element in elements
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.element.placeholder"),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        element_types: dict[Game, type[GenshinElement | HSRElement | ZZZElement]] = {
            Game.GENSHIN: GenshinElement,
            Game.STARRAIL: HSRElement,
            Game.ZZZ: ZZZElement,
        }
        if self.view._game not in element_types:
            msg = f"Element type not found for game {self.view._game}"
            raise KeyError(msg)

        element_type = element_types[self.view._game]
        self.view._element_filters = [element_type(value) for value in self.values]
        await self.view.item_callback(i, self)


class PathFilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(label=EnumStr(path), value=path.value, emoji=get_hsr_path_emoji(path))
            for path in HSRPath
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.path.placeholder"),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view._path_filters = [HSRPath(value) for value in self.values]
        await self.view.item_callback(i, self)


class SpecialtyFilterSelector(Select[CharactersView]):
    def __init__(self, characters: Sequence[ZZZCharacter]) -> None:
        options = [
            SelectOption(
                label=LocaleStr(key=speciality.name.lower()),
                value=str(speciality),
                emoji=ZZZ_SPECIALTY_EMOJIS[speciality],
            )
            for speciality in {character.specialty for character in characters}
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.specialty.placeholder"),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view._speciality_filters = [ZZZSpecialty(int(value)) for value in self.values]
        await self.view.item_callback(i, self)


class FactionFilterSelector(Select[CharactersView]):
    def __init__(self, characters: Sequence[ZZZCharacter]) -> None:
        options = [
            SelectOption(label=faction, value=faction)
            for faction in {character.faction_name for character in characters}
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.faction.placeholder"),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view._faction_filters = self.values
        await self.view.item_callback(i, self)


class SorterSelector(Select[CharactersView]):
    def __init__(self, current: Sorter, game: Game) -> None:
        sorters: dict[Game, type[Sorter]] = {
            Game.GENSHIN: GISorter,
            Game.STARRAIL: HSRSorter,
            Game.ZZZ: ZZZSorter,
            Game.HONKAI: HonkaiSorter,
        }
        if game not in sorters:
            msg = f"Sorter not found for game {game}"
            raise KeyError(msg)

        self._game = game
        self._sorter = sorters[game]

        super().__init__(
            placeholder=LocaleStr(key="characters.sorter.placeholder"),
            options=[
                SelectOption(
                    label=LocaleStr(key=f"characters.sorter.{sorter.value}"),
                    value=sorter.value,
                    default=sorter == current,
                )
                for sorter in self._sorter
            ],
        )

    async def callback(self, i: Interaction) -> None:
        self.view._sorter = self._sorter(self.values[0])
        await self.view.item_callback(i, self)


class UpdateTalentData(Button[CharactersView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="characters.update_talent_data"),
            style=ButtonStyle.blurple,
            row=3,
        )

    async def callback(self, i: Interaction) -> None:
        filename = f"talent_levels/gi_{self.view._account.uid}.json"
        talent_level_data: dict[str, str] = await JSONFile.read(filename)
        updated_at = datetime.datetime.fromisoformat(talent_level_data["updated_at"])
        if get_now() - updated_at < datetime.timedelta(minutes=30):
            raise ActionInCooldownError(available_time=updated_at + datetime.timedelta(minutes=30))

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(key="characters.update_talent_data.embed.description"),
        ).set_author(
            icon_url=LOADING_ICON,
            name=LocaleStr(key="characters.update_talent_data.title"),
        )
        self.view.clear_items()
        await i.response.edit_message(embed=embed, view=self.view, attachments=[])

        characters = [c for c in self.view._gi_characters if not isinstance(c, UnownedCharacter)]
        await self.view._account.client.update_gi_chara_talent_levels(characters)
        await self.view.start(i)


class ShowOwnedOnly(ToggleButton[CharactersView]):
    def __init__(self) -> None:
        super().__init__(
            current_toggle=True,
            toggle_label=LocaleStr(key="characters.show_owned_only"),
            row=4,
        )

    async def callback(self, i: Interaction) -> None:  # noqa: C901, PLR0912
        await super().callback(i)
        await self.set_loading_state(i)

        toggle = self.current_toggle

        if toggle:
            if self.view._game is Game.GENSHIN:
                self.view._gi_characters = [
                    c for c in self.view._gi_characters if not isinstance(c, UnownedCharacter)
                ]
            elif self.view._game is Game.STARRAIL:
                self.view._hsr_characters = [
                    c for c in self.view._hsr_characters if not isinstance(c, UnownedCharacter)
                ]
        else:  # noqa: PLR5501
            if self.view._game is Game.GENSHIN:
                current_chara_ids = {
                    str(c.id) for c in self.view._gi_characters if isinstance(c, GICharacter)
                }

                async with AmbrAPIClient(translator=self.view.translator) as client:
                    ambr_charas = await client.fetch_characters()

                for chara in ambr_charas:
                    if (
                        chara.beta
                        or contains_traveler_id(chara.id)
                        or chara.id in current_chara_ids
                        or (
                            chara.release is not None
                            and chara.release.replace(tzinfo=UTC_8) > get_now()
                        )
                    ):
                        continue

                    self.view._gi_characters.append(
                        UnownedCharacter(
                            id=chara.id, rarity=chara.rarity, element=chara.element.name
                        )
                    )

            elif self.view._game is Game.STARRAIL:
                current_chara_ids = {
                    c.id for c in self.view._hsr_characters if isinstance(c, HSRCharacter)
                }

                async with YattaAPIClient(translator=self.view.translator) as client:
                    yatta_charas = await client.fetch_characters()

                for chara in yatta_charas:
                    if (
                        chara.beta
                        or chara.id in TRAILBLAZER_IDS
                        or chara.id in current_chara_ids
                        or (
                            chara.release_at is not None
                            and chara.release_at.replace(tzinfo=UTC_8) > get_now()
                        )
                    ):
                        continue

                    self.view._hsr_characters.append(
                        UnownedCharacter(
                            id=str(chara.id),
                            rarity=chara.rarity,
                            element=chara.types.combat_type.name,
                            path=YATTA_PATH_TO_GPY_PATH[chara.types.path_type],
                        )
                    )

        await self.view.item_callback(i, self, set_loading_state=False)
