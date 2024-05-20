from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from discord import ButtonStyle
from seria.utils import read_json

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.draw.main_funcs import draw_gi_characters_card, draw_hsr_characters_card
from hoyo_buddy.enums import Game, GenshinElement, HSRElement, HSRPath
from hoyo_buddy.hoyo.clients.gpy_client import (
    GI_TALENT_LEVEL_DATA_PATH,
    PC_ICON_DATA_PATH,
    GenshinClient,
)

from ...constants import TRAILBLAZER_IDS, TRAVELER_IDS
from ...embeds import DefaultEmbed
from ...emojis import get_gi_element_emoji, get_hsr_element_emoji, get_hsr_path_emoji
from ...exceptions import ActionInCooldownError, NoCharsFoundError
from ...icons import LOADING_ICON
from ...models import DrawInput
from ...utils import get_now
from ..components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures
    from collections.abc import Iterable, Sequence

    import aiohttp
    from discord import File, Locale, Member, User
    from genshin.models import Character as GenshinCharacter
    from genshin.models import StarRailDetailCharacter as StarRailCharacter

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.db.models import HoyoAccount


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


class CharactersView(View):
    def __init__(
        self,
        account: HoyoAccount,
        dark_mode: bool,
        element_char_counts: dict[str, int],
        path_char_counts: dict[str, int],
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
        self._gi_characters: Sequence[GenshinCharacter] = []
        self._hsr_characters: Sequence[StarRailCharacter] = []

        self._filter: GIFilter = GIFilter.NONE
        self._element_filters: list[GenshinElement | HSRElement] = []
        self._path_filters: list[HSRPath] = []
        self._sorter: GISorter | HSRSorter
        if self._game is Game.GENSHIN:
            self._sorter = GISorter.ELEMENT
        elif self._game is Game.STARRAIL:
            self._sorter = HSRSorter.ELEMENT

    async def _get_pc_icons(self) -> dict[str, str]:
        pc_icons: dict[str, str] = await read_json(PC_ICON_DATA_PATH)

        if any(str(c.id) not in pc_icons for c in self._gi_characters):
            await self._account.client.update_pc_icons()
            return await read_json(PC_ICON_DATA_PATH)

        return pc_icons

    async def _get_talent_level_data(self) -> dict[str, str]:
        filename = GI_TALENT_LEVEL_DATA_PATH.format(uid=self._account.uid)
        talent_level_data: dict[str, str] = await read_json(filename)

        characters_to_update = [
            c
            for c in self._gi_characters
            if GenshinClient.convert_chara_id_to_ambr_format(c) not in talent_level_data
        ]
        if characters_to_update:
            await self._account.client.update_gi_chara_talent_levels(characters_to_update)
        updated = bool(characters_to_update)

        return await read_json(filename) if updated else talent_level_data

    def _apply_gi_filter(
        self, characters: Sequence[GenshinCharacter]
    ) -> Sequence[GenshinCharacter]:
        if GIFilter.MAX_FRIENDSHIP is self._filter:
            return [c for c in characters if c.friendship == 10]

        if GIFilter.NOT_MAX_FRIENDSHIP is self._filter:
            return [c for c in characters if c.friendship != 10]

        return characters

    def _apply_element_filters(
        self, characters: Sequence[GenshinCharacter | StarRailCharacter]
    ) -> Sequence[GenshinCharacter | StarRailCharacter]:
        if not self._element_filters:
            return characters

        elements = [element_filter.value for element_filter in self._element_filters]
        return [c for c in characters if c.element.lower() in elements]

    def _apply_path_filters(
        self, characters: Sequence[StarRailCharacter]
    ) -> Sequence[StarRailCharacter]:
        if not self._path_filters:
            return characters

        paths = [path_filter.value for path_filter in self._path_filters]
        return [c for c in characters if c.path.name.lower() in paths]

    def _apply_gi_sorter(
        self, characters: Sequence[GenshinCharacter]
    ) -> Sequence[GenshinCharacter]:
        if self._sorter is GISorter.ELEMENT or self._sorter is HSRSorter.ELEMENT:
            return sorted(characters, key=lambda c: c.element)

        if self._sorter is GISorter.LEVEL or self._sorter is HSRSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self._sorter is GISorter.RARITY or self._sorter is HSRSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        if self._sorter is GISorter.FRIENDSHIP:
            return sorted(characters, key=lambda c: c.friendship, reverse=True)

        return sorted(characters, key=lambda c: c.constellation, reverse=True)

    def _apply_hsr_sorter(
        self, characters: Sequence[StarRailCharacter]
    ) -> Sequence[StarRailCharacter]:
        if self._sorter is HSRSorter.PATH:
            return sorted(characters, key=lambda c: c.path)

        if self._sorter is HSRSorter.EIDOLON:
            return sorted(characters, key=lambda c: c.rank, reverse=True)

        if self._sorter is HSRSorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self._sorter is HSRSorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        return sorted(characters, key=lambda c: c.element)

    def _get_gi_filtered_and_sorted_characters(
        self,
    ) -> Sequence[GenshinCharacter]:
        characters = self._apply_gi_sorter(
            self._apply_element_filters(self._apply_gi_filter(self._gi_characters))  # pyright: ignore [reportArgumentType]
        )
        if not characters:
            raise NoCharsFoundError
        return characters

    def _get_hsr_filtered_and_sorted_characters(
        self,
    ) -> Sequence[StarRailCharacter]:
        characters = self._apply_hsr_sorter(
            self._apply_element_filters(self._apply_path_filters(self._hsr_characters))  # pyright: ignore [reportArgumentType]
        )
        if not characters:
            raise NoCharsFoundError
        return characters

    async def _draw_card(
        self,
        session: aiohttp.ClientSession,
        characters: Sequence[GenshinCharacter | StarRailCharacter],
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
    ) -> File:
        if self._game is Game.GENSHIN:
            pc_icons = await self._get_pc_icons()
            talent_level_data = await self._get_talent_level_data()

            file_ = await draw_gi_characters_card(
                DrawInput(
                    dark_mode=self._dark_mode,
                    locale=self.locale,
                    session=session,
                    filename="characters.webp",
                    executor=executor,
                    loop=loop,
                ),
                characters,  # type: ignore [reportArgumentType]
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
                characters,  # type: ignore [reportArgumentType]
                pc_icons,
                self.translator,
            )
        else:
            raise NotImplementedError

        return file_

    def _get_embed(self, char_num: int) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("Character Overview", key="characters.embed.title"),
        )

        if self._filter in {GIFilter.MAX_FRIENDSHIP, GIFilter.NOT_MAX_FRIENDSHIP}:
            total_chars = (
                sum(
                    1
                    for c in self._gi_characters
                    if GenshinElement(c.element.lower()) in self._element_filters
                )
                if self._element_filters
                else len(self._gi_characters)
            )
            if self._filter is GIFilter.MAX_FRIENDSHIP:
                embed.add_field(
                    name=LocaleStr(
                        "Max Friendship {element} Characters",
                        key="characters.embed.element_max_friendship",
                        element=[
                            LocaleStr(element.value.title(), warn_no_key=False)
                            for element in self._element_filters
                        ],
                    )
                    if self._element_filters
                    else LocaleStr(
                        "Max Friendship Characters", key="characters.embed.max_friendship"
                    ),
                    value=f"{char_num}/{total_chars}",
                    inline=False,
                )
            else:
                embed.add_field(
                    name=LocaleStr(
                        "Not Max Friendship {element} Characters",
                        key="characters.embed.element_not_max_friendship",
                        element=[
                            LocaleStr(element.value.title(), warn_no_key=False)
                            for element in self._element_filters
                        ],
                    )
                    if self._element_filters
                    else LocaleStr(
                        "Not Max Friendship Characters", key="characters.embed.not_max_friendship"
                    ),
                    value=f"{char_num}/{total_chars}",
                    inline=False,
                )

        if self._element_filters and self._filter is GIFilter.NONE:
            total_chars = sum(
                self._element_char_counts[element.value] for element in self._element_filters
            )
            embed.add_field(
                name=LocaleStr(
                    "{element} Characters",
                    key="characters.embed.element_filters",
                    element=[
                        LocaleStr(element.value.title(), warn_no_key=False)
                        for element in self._element_filters
                    ],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._path_filters and self._filter is GIFilter.NONE:
            total_chars = sum(self._path_char_counts[path.value] for path in self._path_filters)
            embed.add_field(
                name=LocaleStr(
                    "{path} Characters",
                    key="characters.embed.path_filters",
                    path=[
                        LocaleStr(path.value.title().replace("_", " "), warn_no_key=False)
                        for path in self._path_filters
                    ],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._filter is GIFilter.NONE and not self._element_filters and not self._path_filters:
            total_chars = sum(self._element_char_counts.values()) + 1  # Traveler/Trailblazer
            embed.add_field(
                name=LocaleStr("Owned Characters", key="characters.embed.owned_characters"),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._game is Game.GENSHIN:
            embed.set_footer(
                text=LocaleStr(
                    "Level order: Normal ATK/Skill/Burst",
                    key="characters.gi.embed.footer",
                )
            )
        elif self._game is Game.STARRAIL:
            embed.set_footer(
                text=LocaleStr(
                    (
                        "Level order: Basic ATK/Skill/Ultimate/Talent\n"
                        "Use /profile to view details of a character"
                    ),
                    key="characters.hsr.embed.footer",
                )
            )
        else:
            raise NotImplementedError

        embed.set_image(url="attachment://characters.webp")
        embed.add_acc_info(self._account)
        return embed

    def _add_items(self) -> None:
        if self._game is Game.GENSHIN:
            self.add_item(FilterSelector())
            self.add_item(ElementFilterSelector(GenshinElement))
            self.add_item(GISorterSelector(self._sorter))
            self.add_item(UpdateTalentData())
        elif self._game is Game.STARRAIL:
            self.add_item(PathFilterSelector())
            self.add_item(ElementFilterSelector(HSRElement))
            self.add_item(HSRSorterSelector(self._sorter))
        else:
            raise NotImplementedError

    async def start(self, i: INTERACTION, *, show_first_time_msg: bool = False) -> None:
        if show_first_time_msg:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                description=LocaleStr(
                    (
                        "If this is your first time using this command, this may take a while.\n"
                        "This is because the command needs to fetch data from many sources.\n"
                        "It should be faster next time you use this command.\n"
                        "Please be patient and wait for the resources to be fetched."
                    ),
                    key="characters.first_time.embed.description",
                ),
            ).set_author(
                icon_url=LOADING_ICON,
                name=LocaleStr("Fetching resources...", key="characters.first_time.title"),
            )
            await i.edit_original_response(embed=embed)

        client = self._account.client
        if self._game is Game.GENSHIN:
            self._gi_characters = await client.get_genshin_characters(self._account.uid)

            # Find traveler element and add 1 to the element char count
            for character in self._gi_characters:
                if character.id in TRAVELER_IDS:
                    self._element_char_counts[character.element.lower()] += 1
                    break

            characters = self._get_gi_filtered_and_sorted_characters()
        elif self._game is Game.STARRAIL:
            self._hsr_characters = (
                await client.get_starrail_characters(self._account.uid)
            ).avatar_list

            # Find traiblazer element and path and add 1 to the count
            for character in self._hsr_characters:
                if character.id in TRAILBLAZER_IDS:
                    self._element_char_counts[character.element.lower()] += 1
                    self._path_char_counts[character.path.name.lower()] += 1
                    break

            characters = self._get_hsr_filtered_and_sorted_characters()
        else:
            raise NotImplementedError

        file_ = await self._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self._get_embed(len(characters))

        self._add_items()
        await i.edit_original_response(attachments=[file_], view=self, embed=embed)
        self.message = await i.original_response()


class FilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr("None", key="characters.filter.none"),
                value=GIFilter.NONE,
                default=True,
            ),
            SelectOption(
                label=LocaleStr("Max friendship", key="characters.filter.max_friendship"),
                value=GIFilter.MAX_FRIENDSHIP,
            ),
            SelectOption(
                label=LocaleStr("Not max friendship", key="characters.filter.not_max_friendship"),
                value=GIFilter.NOT_MAX_FRIENDSHIP,
            ),
        ]
        super().__init__(
            placeholder=LocaleStr("Select a filter...", key="characters.filter.placeholder"),
            options=options,
        )

    async def callback(self, i: INTERACTION) -> None:
        self.view._filter = GIFilter(self.values[0])
        characters = self.view._get_gi_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class ElementFilterSelector(Select[CharactersView]):
    def __init__(self, elements: Iterable[GenshinElement | HSRElement]) -> None:
        options = [
            SelectOption(
                label=LocaleStr(element.value.title(), warn_no_key=False),
                value=element.value,
                emoji=get_gi_element_emoji(element)
                if isinstance(element, GenshinElement)
                else get_hsr_element_emoji(element),
            )
            for element in elements
        ]
        super().__init__(
            placeholder=LocaleStr(
                "Select element filters...", key="characters.filter.element.placeholder"
            ),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: INTERACTION) -> None:
        if self.view._game is Game.GENSHIN:
            self.view._element_filters = [GenshinElement(value) for value in self.values]
            characters = self.view._get_gi_filtered_and_sorted_characters()
        elif self.view._game is Game.STARRAIL:
            self.view._element_filters = [HSRElement(value) for value in self.values]
            characters = self.view._get_hsr_filtered_and_sorted_characters()
        else:
            raise NotImplementedError

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class PathFilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr(path.value.title().replace("_", " "), warn_no_key=False),
                value=path.value,
                emoji=get_hsr_path_emoji(path),
            )
            for path in HSRPath
        ]
        super().__init__(
            placeholder=LocaleStr(
                "Select path filters...", key="characters.filter.path.placeholder"
            ),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: INTERACTION) -> None:
        self.view._path_filters = [HSRPath(value) for value in self.values]
        characters = self.view._get_hsr_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class GISorterSelector(Select[CharactersView]):
    def __init__(self, current: GISorter | HSRSorter) -> None:
        options = [
            SelectOption(
                label=LocaleStr(sorter.name.title(), key=f"characters.sorter.{sorter.value}"),
                value=sorter.value,
                default=sorter == current,
            )
            for sorter in GISorter
        ]
        super().__init__(
            placeholder=LocaleStr("Select a sorter...", key="characters.sorter.placeholder"),
            options=options,
        )

    async def callback(self, i: INTERACTION) -> None:
        self.view._sorter = GISorter(self.values[0])
        characters = self.view._get_gi_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class HSRSorterSelector(Select[CharactersView]):
    def __init__(self, current: GISorter | HSRSorter) -> None:
        options = [
            SelectOption(
                label=LocaleStr(sorter.name.title(), key=f"characters.sorter.{sorter.value}"),
                value=sorter.value,
                default=sorter == current,
            )
            for sorter in HSRSorter
        ]
        super().__init__(
            placeholder=LocaleStr("Select a sorter...", key="characters.sorter.placeholder"),
            options=options,
        )

    async def callback(self, i: INTERACTION) -> None:
        self.view._sorter = HSRSorter(self.values[0])
        characters = self.view._get_hsr_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class UpdateTalentData(Button[CharactersView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Update talent level data", key="characters.update_talent_data"),
            style=ButtonStyle.green,
            row=3,
        )

    async def callback(self, i: INTERACTION) -> None:
        filename = GI_TALENT_LEVEL_DATA_PATH.format(uid=self.view._account.uid)
        talent_level_data: dict[str, str] = await read_json(filename)
        updated_at = datetime.datetime.fromisoformat(talent_level_data["updated_at"])
        if get_now() - updated_at < datetime.timedelta(minutes=30):
            raise ActionInCooldownError(available_time=updated_at + datetime.timedelta(minutes=30))

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(
                "This may take a while, if you own a lot of characters, this can take even longer. Please be patient.",
                key="characters.update_talent_data.embed.description",
            ),
        ).set_author(
            icon_url=LOADING_ICON,
            name=LocaleStr(
                "Updating talent level data...", key="characters.update_talent_data.title"
            ),
        )
        self.view.clear_items()
        await i.response.edit_message(embed=embed, view=self.view, attachments=[])

        await self.view._account.client.update_gi_chara_talent_levels(self.view._gi_characters)
        await self.view.start(i)
