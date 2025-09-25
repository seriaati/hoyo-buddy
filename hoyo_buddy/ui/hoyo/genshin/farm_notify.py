from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle
from seria.utils import split_list_to_chunks

from hoyo_buddy.db import FarmNotify
from hoyo_buddy.draw.main_funcs import draw_item_list_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD, DELETE
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient, ItemCategory
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput, ItemWithTrailing
from hoyo_buddy.ui import Button, Page, PaginatorView, ToggleButton

if TYPE_CHECKING:
    from discord import Member, User
    from discord.file import File

    from hoyo_buddy.types import Interaction


class FarmNotifyView(PaginatorView):
    def __init__(
        self,
        farm_notify: FarmNotify,
        draw_input: DrawInput,
        *,
        author: User | Member | None,
        locale: Locale,
    ) -> None:
        self._split_item_ids = split_list_to_chunks(farm_notify.item_ids, 12)
        pages = [
            Page(
                embed=DefaultEmbed(
                    locale,
                    title=LocaleStr(key="farm_notify.title"),
                    description=LocaleStr(key="farm_notify.description"),
                )
                .set_footer(
                    text=LocaleStr(
                        key="page_footer", current_page=i + 1, total_pages=len(self._split_item_ids)
                    )
                )
                .add_acc_info(farm_notify.account)
                .set_image(url="attachment://farm_notify.png")
            )
            for i in range(len(self._split_item_ids))
        ]

        self._notify = farm_notify
        self._draw_input = draw_input

        self._item_names: dict[str, str] = {}  # Item id to name
        self._item_icons: dict[str, str] = {}  # Item id to icon

        super().__init__(pages, author=author, locale=locale)

    def _add_buttons(self) -> None:
        super()._add_buttons()
        self.add_item(NotifyToggle(current_toggle=self._notify.enabled))
        self.add_item(AddItemButton())
        self.add_item(RemoveItemButton())

    async def _fetch_item_icons(self) -> None:
        async with AmbrAPIClient(self.locale) as client:
            characters = await client.fetch_characters()
            weapons = await client.fetch_weapons()

        self._item_icons = {c.id: c.icon for c in characters} | {str(w.id): w.icon for w in weapons}

    async def _create_file(self) -> File:
        items = [
            ItemWithTrailing(
                icon=self._item_icons.get(item_id),
                title=self._item_names.get(str(item_id), item_id),
                trailing="-",
            )
            for item_id in self._split_item_ids[self._current_page]
        ]
        return await draw_item_list_card(self._draw_input, items)

    async def start(self, i: Interaction) -> None:
        if not self._notify.item_ids:
            embed = DefaultEmbed(
                self.locale,
                title=LocaleStr(key="farm_notify.empty"),
                description=LocaleStr(key="farm_notify.empty_description"),
            )
            embed.add_acc_info(self._notify.account)
            return await i.followup.send(embed=embed)

        character_choices = i.client.search_autofill[Game.GENSHIN][ItemCategory.CHARACTERS]
        characters = character_choices.get(self.locale, character_choices[Locale.american_english])

        weapon_choices = i.client.search_autofill[Game.GENSHIN][ItemCategory.WEAPONS]
        weapons = weapon_choices.get(self.locale, weapon_choices[Locale.american_english])

        for choice in characters:
            self._item_names[choice.value] = choice.name
        for choice in weapons:
            self._item_names[choice.value] = choice.name

        await self._fetch_item_icons()
        await super().start(i)
        self.message = await i.original_response()
        return None


class AddItemButton(Button[FarmNotifyView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="farm_notify.add_item"), style=ButtonStyle.blurple, emoji=ADD, row=1
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale, description=LocaleStr(key="farm_notify.add_item.embed.description")
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class RemoveItemButton(Button[FarmNotifyView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="farm_notify.remove_item"),
            style=ButtonStyle.red,
            emoji=DELETE,
            row=1,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale, description=LocaleStr(key="farm_notify.remove_item.embed.description")
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class NotifyToggle(ToggleButton[FarmNotifyView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="reminder_toggle"), row=1)

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        await self.view._notify.fetch_related("account")
        await FarmNotify.filter(account_id=self.view._notify.account.id).update(
            enabled=self.current_toggle
        )
