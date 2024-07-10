from __future__ import annotations

import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, TypeAlias

from discord import ButtonStyle
from genshin.models import Character as GICharacter
from genshin.models import StarRailDetailCharacter as HSRCharacter

from hoyo_buddy.bot.translator import EnumStr, LocaleStr
from hoyo_buddy.draw.main_funcs import draw_gi_characters_card, draw_hsr_characters_card
from hoyo_buddy.enums import Game, GenshinElement, HSRElement, HSRPath
from hoyo_buddy.hoyo.clients.gpy import GenshinClient

from ...constants import (
    TRAILBLAZER_IDS,
    TRAVELER_IDS,
    UTC_8,
    YATTA_PATH_TO_GPY_PATH,
    contains_traveler_id,
)
from ...db.models import JSONFile
from ...embeds import DefaultEmbed
from ...emojis import get_gi_element_emoji, get_hsr_element_emoji, get_hsr_path_emoji
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
    from discord import File, Locale, Member, User

    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.db.models import HoyoAccount
    from hoyo_buddy.types import Interaction

Character: TypeAlias = GICharacter | HSRCharacter | UnownedCharacter


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

        self._gi_characters: list[GICharacter | UnownedCharacter] = []
        self._hsr_characters: list[HSRCharacter | UnownedCharacter] = []

        self._filter: GIFilter = GIFilter.NONE
        self._element_filters: list[GenshinElement | HSRElement] = []
        self._path_filters: list[HSRPath] = []
        self._sorter: GISorter | HSRSorter

        if self._game is Game.GENSHIN:
            self._sorter = GISorter.ELEMENT
        elif self._game is Game.STARRAIL:
            self._sorter = HSRSorter.ELEMENT

    async def _get_pc_icons(self) -> dict[str, str]:
        pc_icons: dict[str, str] = await JSONFile.read("pc_icons.json")

        if any(str(c.id) not in pc_icons for c in self._gi_characters):
            await self._account.client.update_pc_icons()
            pc_icons = await JSONFile.read("pc_icons.json")

        async with AmbrAPIClient() as client:
            for chara in self._gi_characters:
                if str(chara.id) not in pc_icons:
                    pc_icons[str(chara.id)] = (
                        f"https://raw.githubusercontent.com/FortOfFans/GI/main/spriteoutput/avatariconteam/{chara.id}.png"
                    )
                    character_detail = await client.fetch_character_detail(str(chara.id))
                    pc_icons[str(chara.id)] = character_detail.icon
                    await JSONFile.write("pc_icons.json", pc_icons)

        return pc_icons

    async def _get_talent_level_data(self) -> dict[str, str]:
        filename = f"talent_levels/gi_{self._account.uid}.json"
        talent_level_data = await JSONFile.read(filename)

        charas_to_update: list[GICharacter] = []

        for chara in self._gi_characters:
            if (
                isinstance(chara, UnownedCharacter)
                or GenshinClient.convert_chara_id_to_ambr_format(chara) in talent_level_data
            ):
                continue
            charas_to_update.append(chara)

        if charas_to_update:
            await self._account.client.update_gi_chara_talent_levels(charas_to_update)
        updated = bool(charas_to_update)

        return await JSONFile.read(filename) if updated else talent_level_data

    def _apply_gi_filter(
        self, characters: Sequence[GICharacter | UnownedCharacter]
    ) -> Sequence[GICharacter | UnownedCharacter]:
        if self._filter is GIFilter.MAX_FRIENDSHIP:
            return [c for c in characters if isinstance(c, UnownedCharacter) or c.friendship == 10]

        if GIFilter.NOT_MAX_FRIENDSHIP is self._filter:
            return [c for c in characters if isinstance(c, UnownedCharacter) or c.friendship != 10]

        return characters

    def _apply_element_filters(self, characters: Sequence[Character]) -> Sequence[Character]:
        if not self._element_filters:
            return characters

        elements = [element_filter.value.lower() for element_filter in self._element_filters]
        if HSRElement.THUNDER in self._element_filters:
            elements.append("lightning")  # hoyo seriously can't decide on a name
        return [c for c in characters if c.element.lower() in elements]

    def _apply_path_filters(
        self, characters: Sequence[HSRCharacter | UnownedCharacter]
    ) -> Sequence[HSRCharacter | UnownedCharacter]:
        if not self._path_filters:
            return characters

        paths = [path_filter.value.lower() for path_filter in self._path_filters]
        return [c for c in characters if c.path.name.lower() in paths]

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

    def _get_gi_filtered_and_sorted_characters(
        self,
    ) -> Sequence[GICharacter | UnownedCharacter]:
        characters = self._apply_gi_sorter(
            self._apply_element_filters(self._apply_gi_filter(self._gi_characters))  # pyright: ignore [reportArgumentType]
        )
        if not characters:
            raise NoCharsFoundError
        return characters

    def _get_hsr_filtered_and_sorted_characters(
        self,
    ) -> Sequence[HSRCharacter | UnownedCharacter]:
        characters = self._apply_hsr_sorter(
            self._apply_element_filters(self._apply_path_filters(self._hsr_characters))  # pyright: ignore [reportArgumentType]
        )
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
        else:
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

        return file_

    def _get_embed(self, char_num: int) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="characters.embed.title"),
        )

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
                    key="characters.embed.element_filters",
                    element=[EnumStr(element) for element in self._element_filters],
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
                    key="characters.embed.path_filters",
                    path=[EnumStr(path) for path in self._path_filters],
                ),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._filter is GIFilter.NONE and not self._element_filters and not self._path_filters:
            total_chars = sum(self._element_char_counts.values()) + 1  # Traveler/Trailblazer
            embed.add_field(
                name=LocaleStr(key="characters.embed.owned_characters"),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        if self._game is Game.GENSHIN:
            embed.set_footer(
                text=LocaleStr(
                    key="characters.gi.embed.footer",
                    normal=LocaleStr(key="hsr.normal_attack"),
                    skill=LocaleStr(key="gi.skill"),
                    burst=LocaleStr(key="gi.burst"),
                )
            )
        elif self._game is Game.STARRAIL:
            embed.set_footer(
                text=LocaleStr(
                    key="characters.hsr.embed.footer",
                    normal=LocaleStr(key="hsr.normal_attack"),
                    skill=LocaleStr(key="hsr.skill"),
                    ultimate=LocaleStr(key="hsr.ultimate"),
                    talent=LocaleStr(key="hsr.talent"),
                )
            )
        else:
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

        embed.set_image(url="attachment://characters.webp")
        embed.add_acc_info(self._account)
        return embed

    def _add_items(self) -> None:
        self.add_item(ShowOwnedOnly())
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
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

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
        if self._game is Game.GENSHIN:
            self._gi_characters = list(await client.get_genshin_characters(self._account.uid))

            # Find traveler element and add 1 to the element char count
            for character in self._gi_characters:
                if character.id in TRAVELER_IDS:
                    self._element_char_counts[character.element.lower()] += 1
                    break

            characters = self._get_gi_filtered_and_sorted_characters()
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

            characters = self._get_hsr_filtered_and_sorted_characters()
        else:
            raise FeatureNotImplementedError(platform=self._account.platform, game=self._game)

        file_ = await self._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self._get_embed(len([c for c in characters if not isinstance(c, UnownedCharacter)]))

        self._add_items()
        await i.edit_original_response(attachments=[file_], view=self, embed=embed)
        self.message = await i.original_response()


class FilterSelector(Select[CharactersView]):
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
        characters = self.view._get_gi_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(
            len([c for c in characters if not isinstance(c, UnownedCharacter)])
        )
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class ElementFilterSelector(Select[CharactersView]):
    def __init__(self, elements: Iterable[GenshinElement | HSRElement]) -> None:
        options = [
            SelectOption(
                label=EnumStr(element),
                value=element.value,
                emoji=get_gi_element_emoji(element)
                if isinstance(element, GenshinElement)
                else get_hsr_element_emoji(element),
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
        if self.view._game is Game.GENSHIN:
            self.view._element_filters = [GenshinElement(value) for value in self.values]
            characters = self.view._get_gi_filtered_and_sorted_characters()
        elif self.view._game is Game.STARRAIL:
            self.view._element_filters = [HSRElement(value) for value in self.values]
            characters = self.view._get_hsr_filtered_and_sorted_characters()
        else:
            raise FeatureNotImplementedError(
                platform=self.view._account.platform, game=self.view._game
            )

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(
            len([c for c in characters if not isinstance(c, UnownedCharacter)])
        )
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


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
        characters = self.view._get_hsr_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(
            len([c for c in characters if not isinstance(c, UnownedCharacter)])
        )
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class GISorterSelector(Select[CharactersView]):
    def __init__(self, current: GISorter | HSRSorter) -> None:
        options = [
            SelectOption(
                label=LocaleStr(key=f"characters.sorter.{sorter.value}"),
                value=sorter.value,
                default=sorter == current,
            )
            for sorter in GISorter
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.sorter.placeholder"),
            options=options,
        )

    async def callback(self, i: Interaction) -> None:
        self.view._sorter = GISorter(self.values[0])
        characters = self.view._get_gi_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(
            len([c for c in characters if not isinstance(c, UnownedCharacter)])
        )
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class HSRSorterSelector(Select[CharactersView]):
    def __init__(self, current: GISorter | HSRSorter) -> None:
        options = [
            SelectOption(
                label=LocaleStr(key=f"characters.sorter.{sorter.value}"),
                value=sorter.value,
                default=sorter == current,
            )
            for sorter in HSRSorter
        ]
        super().__init__(
            placeholder=LocaleStr(key="characters.sorter.placeholder"), options=options
        )

    async def callback(self, i: Interaction) -> None:
        self.view._sorter = HSRSorter(self.values[0])
        characters = self.view._get_hsr_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(
            len([c for c in characters if not isinstance(c, UnownedCharacter)])
        )
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class UpdateTalentData(Button[CharactersView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="characters.update_talent_data"),
            style=ButtonStyle.green,
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

        if self.view._game is Game.GENSHIN:
            characters = self.view._get_gi_filtered_and_sorted_characters()
        elif self.view._game is Game.STARRAIL:
            characters = self.view._get_hsr_filtered_and_sorted_characters()
        else:
            raise FeatureNotImplementedError(
                platform=self.view._account.platform, game=self.view._game
            )

        file_ = await self.view._draw_card(
            i.client.session, characters, i.client.executor, i.client.loop
        )
        embed = self.view._get_embed(
            len([c for c in characters if not isinstance(c, UnownedCharacter)])
        )
        await self.unset_loading_state(i, attachments=[file_], embed=embed)
