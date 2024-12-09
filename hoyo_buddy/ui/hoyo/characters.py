from __future__ import annotations

import itertools
from enum import StrEnum
from typing import TYPE_CHECKING, Final, TypeAlias

import enka
import genshin
import hakushin
from discord import ButtonStyle, Locale
from genshin.models import FullBattlesuit as HonkaiCharacter
from genshin.models import GenshinDetailCharacter as GICharacter
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
from hoyo_buddy.ui import (
    Button,
    GoBackButton,
    Modal,
    Page,
    PaginatorView,
    Select,
    SelectOption,
    TextInput,
    ToggleButton,
)

from ...constants import (
    AMBR_WEAPON_TYPES,
    CHARACTER_MAX_LEVEL,
    HSR_TEAM_ICON_URL,
    TRAILBLAZER_IDS,
    TRAVELER_IDS,
    UTC_8,
    YATTA_PATH_TO_GPY_PATH,
    contains_traveler_id,
)
from ...db.models import JSONFile, draw_locale, get_dyk
from ...embeds import DefaultEmbed
from ...emojis import (
    FILTER,
    GROUP,
    ZZZ_SPECIALTY_EMOJIS,
    get_gi_element_emoji,
    get_hsr_element_emoji,
    get_hsr_path_emoji,
    get_zzz_element_emoji,
)
from ...exceptions import FeatureNotImplementedError, NoCharsFoundError
from ...hoyo.clients.ambr import AmbrAPIClient
from ...hoyo.clients.yatta import YattaAPIClient
from ...models import DrawInput, UnownedGICharacter, UnownedHSRCharacter, UnownedZZZCharacter
from ...utils import get_now

if TYPE_CHECKING:
    from asyncio import AbstractEventLoop
    from collections.abc import Iterable, Sequence
    from concurrent.futures import ThreadPoolExecutor

    import aiohttp
    from discord import File, Member, User

    from hoyo_buddy.db.models import HoyoAccount
    from hoyo_buddy.types import Interaction


GAME_FOOTERS: Final[dict[Game, tuple[str, ...]]] = {
    Game.GENSHIN: ("hsr.normal_attack", "gi.skill", "gi.burst"),
    Game.STARRAIL: ("hsr.normal_attack", "hsr.skill", "hsr.ultimate", "hsr.talent"),
    Game.ZZZ: ("zzz.basic", "zzz.dodge", "zzz.assist", "zzz.special", "zzz.chain", "zzz.core"),
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


UnownedCharacter: TypeAlias = UnownedGICharacter | UnownedZZZCharacter | UnownedHSRCharacter
Character: TypeAlias = (
    GICharacter | HSRCharacter | UnownedCharacter | ZZZCharacter | HonkaiCharacter
)
Sorter: TypeAlias = GISorter | HSRSorter | ZZZSorter | HonkaiSorter


class CharactersView(PaginatorView):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        element_char_counts: dict[str, int],
        path_char_counts: dict[str, int],
        faction_char_counts: dict[str, int],
        *,
        session: aiohttp.ClientSession,
        executor: ThreadPoolExecutor,
        loop: AbstractEventLoop,
        author: User | Member | None,
        locale: Locale,
    ) -> None:
        super().__init__([], set_loading_state=True, author=author, locale=locale)
        self._session = session
        self._executor = executor
        self._loop = loop

        self.account = account
        self.game = account.game
        self.dark_mode = dark_mode
        self.dyk = ""

        self.element_char_counts = element_char_counts
        self.path_char_counts = path_char_counts
        self.faction_char_counts = faction_char_counts

        self.gi_characters: list[GICharacter | UnownedGICharacter] = []
        self.hsr_characters: list[HSRCharacter | UnownedHSRCharacter] = []
        self.zzz_characters: list[ZZZCharacter | UnownedZZZCharacter] = []
        self.honkai_characters: list[HonkaiCharacter] = []

        self.filter: GIFilter = GIFilter.NONE
        self.element_filters: list[GenshinElement | HSRElement | ZZZElement] = []
        self.path_filters: list[HSRPath] = []
        self.weapon_type_filters: list[int] = []

        self.speciality_filters: list[ZZZSpecialty] = []
        self.faction_filters: list[str] = []
        self.faction_l10n: dict[str, str] = {}

        self.sorter: Sorter = None  # pyright: ignore[reportAttributeAccessIssue]
        if self.game is Game.GENSHIN:
            self.sorter = GISorter.ELEMENT
        elif self.game is Game.STARRAIL:
            self.sorter = HSRSorter.ELEMENT
        elif self.game is Game.ZZZ:
            self.sorter = ZZZSorter.ELEMENT
        elif self.game is Game.HONKAI:
            self.sorter = HonkaiSorter.LEVEL

        self.available_rarities: set[str] = set()
        self.rarities: list[str] = []

        self.show_owned_only = True
        self.show_max_level_only = False
        self.characters_per_page = 32

    async def _get_gi_pc_icons(self) -> dict[str, str]:
        pc_icons = await JSONFile.read("pc_icons.json")

        is_missing = any(
            "yatta.moe" in pc_icons.get(str(c.id), "") or str(c.id) not in pc_icons
            for c in self.gi_characters
        )
        if is_missing and self.account.platform is Platform.HOYOLAB:
            await self.account.client.update_pc_icons()

        is_missing = any(str(c.id) not in pc_icons for c in self.gi_characters)
        if is_missing:
            async with AmbrAPIClient() as client:
                ambr_charas = await client.fetch_characters()
                for chara in self.gi_characters:
                    if str(chara.id) in pc_icons:
                        continue
                    ambr_chara = next((c for c in ambr_charas if c.id == str(chara.id)), None)
                    if ambr_chara is None:
                        continue
                    pc_icons[str(chara.id)] = ambr_chara.icon
                await JSONFile.write("pc_icons.json", pc_icons)

            pc_icons = await JSONFile.read("pc_icons.json")

        return pc_icons

    def _apply_gi_filter(
        self, characters: Sequence[GICharacter | UnownedGICharacter]
    ) -> Sequence[GICharacter | UnownedGICharacter]:
        if self.filter is GIFilter.MAX_FRIENDSHIP:
            return [
                c for c in characters if isinstance(c, UnownedGICharacter) or c.friendship == 10
            ]

        if GIFilter.NOT_MAX_FRIENDSHIP is self.filter:
            return [
                c for c in characters if isinstance(c, UnownedGICharacter) or c.friendship != 10
            ]

        return characters

    def _apply_element_filters(
        self, characters: Sequence[GICharacter | HSRCharacter | ZZZCharacter | UnownedCharacter]
    ) -> Sequence[Character]:
        if not self.element_filters:
            return characters

        elements = [element_filter.value.lower() for element_filter in self.element_filters]
        if HSRElement.THUNDER in self.element_filters:
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

    def _apply_weapon_type_filters(
        self, characters: Sequence[GICharacter | UnownedGICharacter]
    ) -> Sequence[GICharacter | UnownedGICharacter]:
        if not self.weapon_type_filters:
            return characters

        return [c for c in characters if int(c.weapon_type) in self.weapon_type_filters]

    def _apply_path_filters(
        self, characters: Sequence[HSRCharacter | UnownedHSRCharacter]
    ) -> Sequence[HSRCharacter | UnownedHSRCharacter]:
        if not self.path_filters:
            return characters

        paths = [path_filter.value.lower() for path_filter in self.path_filters]
        return [c for c in characters if c.path.name.lower() in paths]

    def _apply_speciality_filters(
        self, characters: Sequence[ZZZCharacter | UnownedZZZCharacter]
    ) -> Sequence[ZZZCharacter | UnownedZZZCharacter]:
        if not self.speciality_filters:
            return characters

        specialities = [speciality_filter.value for speciality_filter in self.speciality_filters]
        return [c for c in characters if c.specialty.value in specialities]

    def _apply_faction_filters(
        self, characters: Sequence[ZZZCharacter | UnownedZZZCharacter]
    ) -> Sequence[ZZZCharacter | UnownedZZZCharacter]:
        if not self.faction_filters:
            return characters

        return [c for c in characters if c.faction_name in self.faction_filters]

    def _apply_gi_sorter(
        self, characters: Sequence[GICharacter | UnownedGICharacter]
    ) -> Sequence[GICharacter | UnownedGICharacter]:
        if self.sorter is GISorter.ELEMENT or self.sorter is HSRSorter.ELEMENT:
            return sorted(characters, key=lambda c: c.element.lower())

        if self.sorter is GISorter.LEVEL or self.sorter is HSRSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self.sorter is GISorter.RARITY or self.sorter is HSRSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        if self.sorter is GISorter.FRIENDSHIP:
            return sorted(characters, key=lambda c: c.friendship, reverse=True)

        return sorted(characters, key=lambda c: c.constellation, reverse=True)

    def _apply_hsr_sorter(
        self, characters: Sequence[HSRCharacter | UnownedHSRCharacter]
    ) -> Sequence[HSRCharacter | UnownedHSRCharacter]:
        if self.sorter is HSRSorter.PATH:
            return sorted(characters, key=lambda c: c.path)

        if self.sorter is HSRSorter.EIDOLON:
            return sorted(characters, key=lambda c: c.rank, reverse=True)

        if self.sorter is HSRSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self.sorter is HSRSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        return sorted(characters, key=lambda c: c.element.lower())

    def _apply_zzz_sorter(
        self, characters: Sequence[ZZZCharacter | UnownedZZZCharacter]
    ) -> Sequence[ZZZCharacter | UnownedZZZCharacter]:
        if self.sorter is ZZZSorter.ELEMENT:
            return sorted(characters, key=lambda c: c.element)

        if self.sorter is ZZZSorter.SPECIALTY:
            return sorted(characters, key=lambda c: c.specialty)

        if self.sorter is ZZZSorter.FACTION:
            return sorted(characters, key=lambda c: c.faction_name)

        if self.sorter is ZZZSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self.sorter is ZZZSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        return sorted(characters, key=lambda c: c.rank, reverse=True)

    def _apply_honkai_sorter(
        self, characters: Sequence[HonkaiCharacter]
    ) -> Sequence[HonkaiCharacter]:
        if self.sorter is HonkaiSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        return sorted(characters, key=lambda c: c.rarity, reverse=True)

    def get_filtered_sorted_characters(self) -> Sequence[Character]:
        if self.game is Game.GENSHIN:
            characters = self._apply_gi_sorter(
                self._apply_element_filters(
                    self._apply_weapon_type_filters(self._apply_gi_filter(self.gi_characters))
                )  # pyright: ignore [reportArgumentType]
            )
        elif self.game is Game.STARRAIL:
            characters = self._apply_hsr_sorter(
                self._apply_element_filters(self._apply_path_filters(self.hsr_characters))  # pyright: ignore [reportArgumentType]
            )
        elif self.game is Game.ZZZ:
            characters = self._apply_zzz_sorter(
                self._apply_element_filters(
                    self._apply_speciality_filters(self._apply_faction_filters(self.zzz_characters))  # pyright: ignore [reportArgumentType]
                )
            )
        elif self.game is Game.HONKAI:
            characters = self._apply_honkai_sorter(self.honkai_characters)
        else:
            raise FeatureNotImplementedError(platform=self.account.platform, game=self.game)

        if self.show_max_level_only:
            max_level = CHARACTER_MAX_LEVEL.get(self.game)
            if max_level is None:
                msg = f"Max level not found for game {self.game}"
                raise KeyError(msg)

            characters = [c for c in characters if c.level == max_level]

        characters = [c for c in characters if str(c.rarity) in self.rarities]

        if not characters:
            raise NoCharsFoundError

        return characters

    async def _draw_card(self, characters: Sequence[Character]) -> File:
        session, loop, executor = self._session, self._loop, self._executor
        locale = draw_locale(self.locale, self.account)

        if self.game is Game.GENSHIN:
            pc_icons = await self._get_gi_pc_icons()

            async with enka.GenshinClient() as client:
                talent_orders = {
                    character_id: character_info["SkillOrder"]
                    for character_id, character_info in client._assets.character_data.items()
                }

            file_ = await draw_gi_characters_card(
                DrawInput(
                    dark_mode=self.dark_mode,
                    locale=locale,
                    session=session,
                    filename="characters.png",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
                pc_icons,
                talent_orders,
            )
        elif self.game is Game.STARRAIL:
            pc_icons = {str(c.id): HSR_TEAM_ICON_URL.format(char_id=c.id) for c in characters}
            file_ = await draw_hsr_characters_card(
                DrawInput(
                    dark_mode=self.dark_mode,
                    locale=locale,
                    session=session,
                    filename="characters.png",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
                pc_icons,
            )
        elif self.game is Game.ZZZ:
            file_ = await draw_zzz_characters_card(
                DrawInput(
                    dark_mode=self.dark_mode,
                    locale=locale,
                    session=session,
                    filename="characters.png",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
            )
        elif self.game is Game.HONKAI:
            file_ = await draw_honkai_suits_card(
                DrawInput(
                    dark_mode=self.dark_mode,
                    locale=locale,
                    session=session,
                    filename="characters.png",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # pyright: ignore [reportArgumentType]
            )
        else:
            raise FeatureNotImplementedError(platform=self.account.platform, game=self.game)

        return file_

    def _get_embed(self, char_num: int) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, title=LocaleStr(key="characters.embed.title"))
        embed.set_image(url="attachment://characters.png")
        embed.add_acc_info(self.account)

        if self.game is Game.HONKAI:
            return embed

        if self.filter in {GIFilter.MAX_FRIENDSHIP, GIFilter.NOT_MAX_FRIENDSHIP}:
            total_chars = (
                sum(
                    1
                    for c in self.gi_characters
                    if GenshinElement(c.element.title()) in self.element_filters
                )
                if self.element_filters
                else len(self.gi_characters)
            )
            if self.filter is GIFilter.MAX_FRIENDSHIP:
                embed.add_field(
                    name=LocaleStr(
                        key="characters.embed.element_max_friendship",
                        element=[EnumStr(element) for element in self.element_filters],
                    )
                    if self.element_filters
                    else LocaleStr(key="characters.embed.max_friendship"),
                    value=f"{char_num}/{total_chars}",
                    inline=False,
                )
            else:
                embed.add_field(
                    name=LocaleStr(
                        key="characters.embed.element_not_max_friendship",
                        element=[EnumStr(element) for element in self.element_filters],
                    )
                    if self.element_filters
                    else LocaleStr(key="characters.embed.not_max_friendship"),
                    value=f"{char_num}/{total_chars}",
                    inline=False,
                )

        if self.element_filters and self.filter is GIFilter.NONE:
            total_chars = sum(
                self.element_char_counts[element.value.lower()] for element in self.element_filters
            )
            embed.add_field(
                name=LocaleStr(
                    key="characters.embed.filter_text",
                    filter=[EnumStr(element) for element in self.element_filters],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self.path_filters and self.filter is GIFilter.NONE:
            total_chars = sum(
                self.path_char_counts[path.name.lower()] for path in self.path_filters
            )
            embed.add_field(
                name=LocaleStr(
                    key="characters.embed.filter_text",
                    filter=[EnumStr(path) for path in self.path_filters],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self.faction_filters and self.filter is GIFilter.NONE:
            total_chars = sum(
                self.faction_char_counts[self.faction_l10n[faction].lower()]
                for faction in self.faction_filters
            )
            embed.add_field(
                name=LocaleStr(
                    key="characters.embed.filter_text", filter="/".join(self.faction_filters)
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if (
            self.filter is GIFilter.NONE
            and not self.element_filters
            and not self.path_filters
            and not self.speciality_filters
            and not self.faction_filters
        ):
            total_chars = sum(self.element_char_counts.values())
            embed.add_field(
                name=LocaleStr(
                    key="characters_embed_max_level_characters"
                    if self.show_max_level_only
                    else "characters.embed.owned_characters"
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self.game in GAME_FOOTERS:
            footer = LocaleStr(
                key="characters.level_order.footer",
                order=[LocaleStr(key=key) for key in GAME_FOOTERS[self.game]],
            ).translate(self.locale)
            if self.game in {Game.STARRAIL, Game.ZZZ}:
                footer += "\n" + LocaleStr(key="characters.extra_detail.footer").translate(
                    self.locale
                )
            embed.set_footer(text=footer)

        return embed

    def _add_items(self) -> None:
        items: list[Select | Button] = [RarityFilterSelector(self.available_rarities)]

        if self.game is Game.GENSHIN:
            options = WeaponTypeFilter.generate_options(
                {
                    1: "genshin_weapon_type_name_sword_one_hand",
                    11: "genshin_weapon_type_name_claymore",
                    10: "genshin_weapon_type_name_catalyst",
                    12: "genshin_weapon_type_name_bow",
                    13: "genshin_weapon_type_name_pole",
                }
            )
            items.extend(
                [
                    GIFilterSelector(),
                    ElementFilterSelector(GenshinElement),
                    WeaponTypeFilter(options),
                ]
            )
        elif self.game is Game.STARRAIL:
            items.extend([ElementFilterSelector(HSRElement), PathFilterSelector()])
        elif self.game is Game.ZZZ:
            items.extend(
                [
                    ElementFilterSelector(ZZZElement),
                    SpecialtyFilterSelector(self.zzz_characters),
                    FactionFilterSelector(self.zzz_characters),
                ]
            )

        chunked_items = itertools.batched(items, 4)
        for num, chunk in enumerate(chunked_items, 1):
            self.add_item(FilterButton(num, chunk))

        self.add_item(CharactersPerPageButton())

        if self.game in {Game.GENSHIN, Game.STARRAIL, Game.ZZZ}:
            self.add_item(ShowOwnedOnly(current_toggle=self.show_owned_only))
            self.add_item(ShowMaxLevelOnly(current_toggle=self.show_max_level_only))
        elif self.game is Game.HONKAI:
            self.add_item(ShowMaxLevelOnly(current_toggle=self.show_max_level_only))

        self.add_item(SorterSelector(self.sorter, self.game))

    def _set_pages(self, characters: Sequence[Character], *, embed: DefaultEmbed) -> None:
        page_num = len(list(itertools.batched(characters, self.characters_per_page)))
        self.pages = [Page(content=self.dyk, embed=embed) for _ in range(page_num)]

    async def _create_file(self) -> File:
        characters = self.get_filtered_sorted_characters()
        chunked_chars = list(itertools.batched(characters, self.characters_per_page))
        chars = chunked_chars[self._current_page]
        return await self._draw_card(chars)

    async def start(self, i: Interaction) -> None:
        self.dyk = await get_dyk(i)
        client = self.account.client
        client.set_lang(self.locale)

        if self.game is Game.GENSHIN:
            self.gi_characters = list(
                (await client.get_genshin_detailed_characters(self.account.uid)).characters
            )

            # Find traveler element and add 1 to the element char count
            for character in self.gi_characters:
                if character.id in TRAVELER_IDS:
                    self.element_char_counts[character.element.lower()] += 1
                    break

        elif self.game is Game.STARRAIL:
            self.hsr_characters = list(
                (await client.get_starrail_characters(self.account.uid)).avatar_list
            )

            # Find traiblazer element and path and add 1 to the count
            for character in self.hsr_characters:
                if character.id in TRAILBLAZER_IDS:
                    self.element_char_counts[character.element.lower()] += 1
                    self.path_char_counts[character.path.name.lower()] += 1
                    break

        elif self.game is Game.ZZZ:
            agents = await client.get_zzz_agents()
            full_agents = list(await client.get_zzz_agent_info([agent.id for agent in agents]))
            self.zzz_characters = full_agents  # pyright: ignore[reportAttributeAccessIssue]

            client.set_lang(Locale.american_english)
            en_full_agents = list(await client.get_zzz_agent_info([agent.id for agent in agents]))
            self.faction_l10n = {
                agent.faction_name: en_agent.faction_name
                for agent, en_agent in zip(full_agents, en_full_agents, strict=False)
            }
        elif self.game is Game.HONKAI:
            self.honkai_characters = list(await client.get_honkai_battlesuits(self.account.uid))

        self.available_rarities = {
            str(c.rarity)
            for c in self.gi_characters
            + self.hsr_characters
            + self.zzz_characters
            + self.honkai_characters
        }
        self.rarities = list(self.available_rarities.copy())
        await self.update(i)

    async def update(self, i: Interaction) -> None:
        characters = self.get_filtered_sorted_characters()
        embed = self._get_embed(len([c for c in characters if not isinstance(c, UnownedCharacter)]))
        self._set_pages(characters, embed=embed)

        self.clear_items()
        self._add_buttons()
        self._add_items()
        self.current_page = 0
        await super().start(i)


class GIFilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr(key="characters.filter.none"), value=GIFilter.NONE, default=True
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
            placeholder=LocaleStr(key="characters.filter.placeholder"), options=options
        )

    async def callback(self, i: Interaction) -> None:
        self.view.filter = GIFilter(self.values[0])
        await i.response.defer()


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
                label=EnumStr(element), value=element.value, emoji=get_element_emoji(element)
            )
            for element in elements
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.element.placeholder"),
            options=options,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        element_types: dict[Game, type[GenshinElement | HSRElement | ZZZElement]] = {
            Game.GENSHIN: GenshinElement,
            Game.STARRAIL: HSRElement,
            Game.ZZZ: ZZZElement,
        }
        if self.view.game not in element_types:
            msg = f"Element type not found for game {self.view.game}"
            raise KeyError(msg)

        element_type = element_types[self.view.game]
        self.view.element_filters = [element_type(value) for value in self.values]
        await i.response.defer()


class PathFilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(label=EnumStr(path), value=path.value, emoji=get_hsr_path_emoji(path))
            for path in HSRPath
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.path.placeholder"),
            options=options,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view.path_filters = [HSRPath(value) for value in self.values]
        await i.response.defer()


class SpecialtyFilterSelector(Select[CharactersView]):
    def __init__(self, characters: Sequence[ZZZCharacter | UnownedZZZCharacter]) -> None:
        specialty_names = {
            ZZZSpecialty.ANOMALY: "ProfessionName_ElementAbnormal",
            ZZZSpecialty.ATTACK: "ProfessionName_PowerfulAttack",
            ZZZSpecialty.DEFENSE: "ProfessionName_Defence",
            ZZZSpecialty.STUN: "ProfessionName_BreakStun",
            ZZZSpecialty.SUPPORT: "ProfessionName_Support",
        }
        options = [
            SelectOption(
                label=LocaleStr(key=specialty_names[speciality], data_game=Game.ZZZ),
                value=str(speciality),
                emoji=ZZZ_SPECIALTY_EMOJIS[speciality],
            )
            for speciality in {character.specialty for character in characters}
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.specialty.placeholder"),
            options=options,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view.speciality_filters = [ZZZSpecialty(int(value)) for value in self.values]
        await i.response.defer()


class FactionFilterSelector(Select[CharactersView]):
    def __init__(self, characters: Sequence[ZZZCharacter | UnownedZZZCharacter]) -> None:
        options = [
            SelectOption(label=faction, value=faction)
            for faction in {
                character.faction_name for character in characters if character.faction_name
            }
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.faction.placeholder"),
            options=options,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view.faction_filters = self.values
        await i.response.defer()


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
        await self.set_loading_state(i)
        self.view.sorter = self._sorter(self.values[0])
        await self.view.update(i)


class ShowOwnedOnly(ToggleButton[CharactersView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle=current_toggle,
            toggle_label=LocaleStr(key="characters.show_owned_only"),
            row=2,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=False)
        await self.set_loading_state(i)
        self.view.show_owned_only = toggle = self.current_toggle

        if toggle:
            if self.view.game is Game.GENSHIN:
                self.view.gi_characters = [
                    c for c in self.view.gi_characters if not isinstance(c, UnownedGICharacter)
                ]
            elif self.view.game is Game.STARRAIL:
                self.view.hsr_characters = [
                    c for c in self.view.hsr_characters if not isinstance(c, UnownedHSRCharacter)
                ]
            elif self.view.game is Game.ZZZ:
                self.view.zzz_characters = [
                    c for c in self.view.zzz_characters if not isinstance(c, UnownedZZZCharacter)
                ]

        elif self.view.game is Game.GENSHIN:
            current_chara_ids = {
                str(c.id) for c in self.view.gi_characters if isinstance(c, GICharacter)
            }

            async with AmbrAPIClient() as client:
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

                self.view.gi_characters.append(
                    UnownedGICharacter(
                        id=chara.id,
                        rarity=chara.rarity,
                        element=chara.element.name,
                        weapon_type=AMBR_WEAPON_TYPES[chara.weapon_type],
                    )
                )

        elif self.view.game is Game.STARRAIL:
            current_chara_ids = {
                c.id for c in self.view.hsr_characters if isinstance(c, HSRCharacter)
            }

            async with YattaAPIClient() as client:
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

                self.view.hsr_characters.append(
                    UnownedHSRCharacter(
                        id=chara.id,
                        rarity=chara.rarity,
                        element=chara.types.combat_type.name,
                        path=YATTA_PATH_TO_GPY_PATH[chara.types.path_type],
                    )
                )

        elif self.view.game is Game.ZZZ:
            current_chara_ids = {
                c.id for c in self.view.zzz_characters if isinstance(c, ZZZCharacter)
            }

            async with hakushin.HakushinAPI(hakushin.Game.ZZZ) as client:
                zzz_charas = await client.fetch_characters()
                new = await client.fetch_new()

                for chara in zzz_charas:
                    if (
                        chara.id in current_chara_ids
                        or chara.rarity is None
                        or chara.element is None
                        or chara.id in new.character_ids
                    ):
                        continue

                    chara_detail = await client.fetch_character_detail(chara.id)

                    self.view.zzz_characters.append(
                        UnownedZZZCharacter(
                            id=chara.id,
                            rarity=chara.rarity,
                            element=genshin.models.ZZZElementType(chara.element.value),
                            specialty=genshin.models.ZZZSpecialty(chara.specialty.value),
                            faction_name=chara_detail.faction.name,
                            banner_icon=f"https://act-webstatic.hoyoverse.com/game_record/zzz/role_vertical_painting/role_vertical_painting_{chara.id}.png",
                        )
                    )

        await self.view.update(i)


class ShowMaxLevelOnly(ToggleButton[CharactersView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(
            current_toggle=current_toggle,
            toggle_label=LocaleStr(key="characters_view_show_max_level_only"),
            row=2,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=False)
        await self.set_loading_state(i)
        self.view.show_max_level_only = self.current_toggle
        await self.view.update(i)


class RarityFilterSelector(Select[CharactersView]):
    def __init__(self, rarities: set[str]) -> None:
        options = [
            SelectOption(label=str(rarity), value=str(rarity), default=True)
            for rarity in sorted(rarities, reverse=True)
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.filter.rarity.placeholder"),
            options=options,
            max_values=len(options),
        )

    async def callback(self, i: Interaction) -> None:
        self.view.rarities = self.values
        await i.response.defer()


class WeaponTypeFilter(Select[CharactersView]):
    def __init__(self, options: list[SelectOption]) -> None:
        super().__init__(
            placeholder=LocaleStr(key="weapon_type_filter_placeholder"),
            options=options,
            max_values=len(options),
        )

    @staticmethod
    def generate_options(types: dict[int, str]) -> list[SelectOption]:
        return [
            SelectOption(label=LocaleStr(key=mi18n_key, mi18n_game=Game.GENSHIN), value=str(type_))
            for type_, mi18n_key in types.items()
        ]

    async def callback(self, i: Interaction) -> None:
        self.view.weapon_type_filters = [int(value) for value in self.values]
        await i.response.defer()


class CustomGoBackButton(GoBackButton[CharactersView]):
    async def callback(self, i: Interaction) -> None:
        await self.set_loading_state(i)
        await self.view.update(i)


class FilterButton(Button[CharactersView]):
    def __init__(self, _: int, items: Sequence[Button | Select]) -> None:
        super().__init__(
            label=LocaleStr(key="gacha_view_filter_button_label"),
            style=ButtonStyle.blurple,
            emoji=FILTER,
            row=1,
        )
        self._items = items

    async def callback(self, i: Interaction) -> None:
        back_button = CustomGoBackButton(self.view.children)
        self.view.clear_items()

        for item in self._items:
            self.view.add_item(item)
        self.view.add_item(back_button)

        await i.response.edit_message(view=self.view)


class CharactersPerPageModal(Modal):
    num = TextInput(
        label=LocaleStr(key="characters_per_page_num_label"), is_digit=True, min_value=1
    )

    def __init__(self, current_num: int, total_num: int) -> None:
        super().__init__(title=LocaleStr(key="characters_per_page_modal_title"))
        self.num.default = str(current_num)
        self.num.max_value = total_num


class CharactersPerPageButton(Button[CharactersView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="characters_per_page_modal_title"),
            style=ButtonStyle.blurple,
            row=1,
            emoji=GROUP,
        )

    async def callback(self, i: Interaction) -> None:
        modal = CharactersPerPageModal(
            self.view.characters_per_page, len(self.view.get_filtered_sorted_characters())
        )
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)

        timed_out = await modal.wait()
        if timed_out:
            return

        await self.set_loading_state(i)
        self.view.characters_per_page = int(modal.num.value)
        await self.view.update(i)
