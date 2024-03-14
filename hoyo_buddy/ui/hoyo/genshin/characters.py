import contextlib
import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from discord import ButtonStyle, InteractionResponded
from seria.utils import read_json

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.draw.main_funcs import draw_gi_character_card
from hoyo_buddy.enums import GenshinElement
from hoyo_buddy.hoyo.clients.gpy_client import (
    GI_TALENT_LEVEL_DATA_PATH,
    PC_ICON_DATA_PATH,
    GenshinClient,
)

from ....constants import TRAVELER_IDS
from ....embeds import DefaultEmbed
from ....emojis import get_gi_element_emoji
from ....exceptions import ActionInCooldownError, NoCharsFoundError
from ....icons import LOADING_ICON
from ....models import DrawInput
from ....utils import get_now
from ...components import Button, Select, SelectOption, View

if TYPE_CHECKING:
    from collections.abc import Sequence

    import aiohttp
    from discord import File, Locale, Member, User
    from genshin.models import Character

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.db.models import HoyoAccount


class Filter(StrEnum):
    NONE = "none"
    MAX_FRIENDSHIP = "max_friendship"
    NOT_MAX_FRIENDSHIP = "not_max_friendship"


class Sorter(StrEnum):
    ELEMENT = "element"
    LEVEL = "level"
    RARITY = "rarity"
    FRIENDSHIP = "friendship"
    CONSTELLATION = "constellation"


class CharactersView(View):
    def __init__(
        self,
        account: "HoyoAccount",
        dark_mode: bool,
        element_char_counts: dict[str, int],
        *,
        author: "User | Member | None",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._account = account
        self._dark_mode = dark_mode
        self._element_char_counts = element_char_counts
        self._characters: Sequence[Character] = []

        self._filter: Filter = Filter.NONE
        self._element_filters: list[GenshinElement] = []
        self._sorter: Sorter = Sorter.ELEMENT

    async def _get_pc_icons(self) -> dict[str, str]:
        pc_icons: dict[str, str] = await read_json(PC_ICON_DATA_PATH)

        if any(str(c.id) not in pc_icons for c in self._characters):
            await self._account.client.update_pc_icons()
            return await read_json(PC_ICON_DATA_PATH)

        return pc_icons

    async def _get_talent_level_data(self) -> dict[str, str]:
        filename = GI_TALENT_LEVEL_DATA_PATH.format(uid=self._account.uid)
        talent_level_data: dict[str, str] = await read_json(filename)

        updated = False
        for character in self._characters:
            if (
                GenshinClient.convert_character_id_to_ambr_format(character)
                not in talent_level_data
            ):
                updated = True
                await self._account.client.update_gi_talent_level_data(character)

        return await read_json(filename) if updated else talent_level_data

    def _apply_filter(self, characters: "Sequence[Character]") -> "Sequence[Character]":
        if Filter.MAX_FRIENDSHIP is self._filter:
            return [c for c in characters if c.friendship == 10]

        if Filter.NOT_MAX_FRIENDSHIP is self._filter:
            return [c for c in characters if c.friendship != 10]

        return characters

    def _apply_element_filters(self, characters: "Sequence[Character]") -> "Sequence[Character]":
        if not self._element_filters:
            return characters

        elements = [element_filter.value for element_filter in self._element_filters]
        return [c for c in characters if c.element.lower() in elements]

    def _apply_sorter(self, characters: "Sequence[Character]") -> "Sequence[Character]":
        if self._sorter is Sorter.ELEMENT:
            return sorted(characters, key=lambda c: c.element)

        if self._sorter is Sorter.LEVEL:
            return sorted(characters, key=lambda c: c.level, reverse=True)

        if self._sorter is Sorter.RARITY:
            return sorted(characters, key=lambda c: c.rarity, reverse=True)

        if self._sorter is Sorter.FRIENDSHIP:
            return sorted(characters, key=lambda c: c.friendship, reverse=True)

        return sorted(characters, key=lambda c: c.constellation, reverse=True)

    def _get_filtered_and_sorted_characters(self) -> "Sequence[Character]":
        characters = self._apply_sorter(
            self._apply_element_filters(self._apply_filter(self._characters))
        )
        if not characters:
            raise NoCharsFoundError
        return characters

    async def _draw_card(
        self, session: "aiohttp.ClientSession", characters: "Sequence[Character]"
    ) -> "File":
        pc_icons = await self._get_pc_icons()
        talent_level_data = await self._get_talent_level_data()

        file_ = await draw_gi_character_card(
            DrawInput(
                dark_mode=self._dark_mode,
                locale=self.locale,
                session=session,
                filename="characters.webp",
            ),
            characters,
            talent_level_data,
            pc_icons,
            self.translator,
        )
        return file_

    def _get_embed(self, char_num: int) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("Characters", key="characters.embed.title"),
        )

        if self._filter in {Filter.MAX_FRIENDSHIP, Filter.NOT_MAX_FRIENDSHIP}:
            total_chars = (
                sum(
                    1
                    for c in self._characters
                    if GenshinElement(c.element.lower()) in self._element_filters
                )
                if self._element_filters
                else len(self._characters)
            )
            if self._filter is Filter.MAX_FRIENDSHIP:
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

        if self._element_filters and self._filter is Filter.NONE:
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

        if self._filter is Filter.NONE and not self._element_filters:
            total_chars = sum(self._element_char_counts.values()) + 1  # Traveler
            embed.add_field(
                name=LocaleStr("Owned Characters", key="characters.embed.owned_characters"),
                value=f"{char_num}/{total_chars}",
                inline=False,
            )

        embed.set_image(url="attachment://characters.webp")
        return embed

    def _add_items(self) -> None:
        self.add_item(FilterSelector())
        self.add_item(ElementFilterSelector())
        self.add_item(SorterSelector())
        self.add_item(UpdateTalentData())

    async def start(self, i: "INTERACTION") -> None:
        with contextlib.suppress(InteractionResponded):
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
            await i.response.send_message(embed=embed)

        client = self._account.client
        self._characters = await client.get_genshin_characters(self._account.uid)

        # Find traveler element and add 1 to the element char count
        for character in self._characters:
            if character.id in TRAVELER_IDS:
                self._element_char_counts[character.element.lower()] += 1
                break

        characters = self._get_filtered_and_sorted_characters()
        file_ = await self._draw_card(i.client.session, characters)
        embed = self._get_embed(len(characters))

        self._add_items()
        await i.edit_original_response(attachments=[file_], view=self, embed=embed)


class FilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr("None", key="characters.filter.none"),
                value=Filter.NONE,
                default=True,
            ),
            SelectOption(
                label=LocaleStr("Max friendship", key="characters.filter.max_friendship"),
                value=Filter.MAX_FRIENDSHIP,
            ),
            SelectOption(
                label=LocaleStr("Not max friendship", key="characters.filter.not_max_friendship"),
                value=Filter.NOT_MAX_FRIENDSHIP,
            ),
        ]
        super().__init__(
            placeholder=LocaleStr("Select a filter...", key="characters.filter.placeholder"),
            options=options,
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._filter = Filter(self.values[0])
        characters = self.view._get_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(i.client.session, characters)
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class ElementFilterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr(element.value.title(), warn_no_key=False),
                value=element.value,
                emoji=get_gi_element_emoji(element),
            )
            for element in GenshinElement
        ]
        super().__init__(
            placeholder=LocaleStr(
                "Select element filters...", key="characters.filter.element.placeholder"
            ),
            options=options,
            min_values=0,
            max_values=len(options),
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._element_filters = [GenshinElement(value) for value in self.values]
        characters = self.view._get_filtered_and_sorted_characters()

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(i.client.session, characters)
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class SorterSelector(Select[CharactersView]):
    def __init__(self) -> None:
        options = [
            SelectOption(
                label=LocaleStr("Element", key="characters.sorter.element"),
                value=Sorter.ELEMENT,
                default=True,
            ),
            SelectOption(
                label=LocaleStr("Level", key="characters.sorter.level"), value=Sorter.LEVEL
            ),
            SelectOption(
                label=LocaleStr("Rarity", key="characters.sorter.rarity"), value=Sorter.RARITY
            ),
            SelectOption(
                label=LocaleStr("Friendship", key="characters.sorter.friendship"),
                value=Sorter.FRIENDSHIP,
            ),
            SelectOption(
                label=LocaleStr("Constellation", key="characters.sorter.constellation"),
                value=Sorter.CONSTELLATION,
            ),
        ]
        super().__init__(
            placeholder=LocaleStr("Select a sorter...", key="characters.sorter.placeholder"),
            options=options,
        )

    async def callback(self, i: "INTERACTION") -> None:
        characters = self.view._get_filtered_and_sorted_characters()
        self.view._sorter = Sorter(self.values[0])

        await self.set_loading_state(i)
        file_ = await self.view._draw_card(i.client.session, characters)
        embed = self.view._get_embed(len(characters))
        await self.unset_loading_state(i, attachments=[file_], embed=embed)


class UpdateTalentData(Button[CharactersView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Update Talent Level Data", key="characters.update_talent_data"),
            style=ButtonStyle.green,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
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

        for character in self.view._characters:
            await self.view._account.client.update_gi_talent_level_data(character)
        await self.view.start(i)
