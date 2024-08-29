from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale
from seria.utils import split_list_to_chunks

from hoyo_buddy.enums import Game

from ...db.models import FarmNotify
from ...draw.main_funcs import draw_item_list_card
from ...embeds import DefaultEmbed
from ...emojis import ADD, DELETE
from ...hoyo.clients.ambr import AmbrAPIClient, ItemCategory
from ...l10n import LocaleStr
from ...models import DrawInput, ItemWithTrailing
from ..components import Button, ToggleButton
from ..paginator import Page, PaginatorView

if TYPE_CHECKING:
    import asyncio
    import concurrent.futures

    import aiohttp
    from discord import Member, User
    from discord.file import File

    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction


class FarmNotifyView(PaginatorView):
    def __init__(
        self,
        farm_notify: FarmNotify,
        dark_mode: bool,
        session: aiohttp.ClientSession,
        executor: concurrent.futures.ProcessPoolExecutor,
        loop: asyncio.AbstractEventLoop,
        *,
        author: User | Member | None,
        locale: Locale,
        translator: Translator,
    ) -> None:
        self._split_item_ids = split_list_to_chunks(farm_notify.item_ids, 12)
        pages = [
            Page(
                embed=DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="farm_notify.title"),
                    description=LocaleStr(key="farm_notify.description"),
                )
                .set_footer(
                    text=LocaleStr(
                        key="page_footer",
                        current_page=i + 1,
                        total_pages=len(self._split_item_ids),
                    ),
                )
                .add_acc_info(farm_notify.account)
                .set_image(url="attachment://farm_notify.webp"),
            )
            for i in range(len(self._split_item_ids))
        ]

        self._notify = farm_notify
        self._dark_mode = dark_mode
        self._session = session
        self._item_names: dict[str, str] = {}
        self._item_icons: dict[str, str] = {}

        super().__init__(pages, author=author, locale=locale, translator=translator)

        self._executor = executor
        self._loop = loop

    def _add_buttons(self) -> None:
        super()._add_buttons()
        self.add_item(NotifyToggle(self._notify.enabled))
        self.add_item(AddItemButton())
        self.add_item(RemoveItemButton())

    async def _fetch_item_icons(self) -> None:
        async with AmbrAPIClient(self.locale, self.translator) as client:
            characters = await client.fetch_characters()
            weapons = await client.fetch_weapons()

        self._item_icons = {c.id: c.icon for c in characters} | {str(w.id): w.icon for w in weapons}

    async def _create_file(self) -> File:
        items = [
            ItemWithTrailing(
                icon=self._item_icons.get(item_id),
                title=self._item_names.get(str(item_id), item_id),
                trailing="",
            )
            for item_id in self._split_item_ids[self._current_page]
        ]
        return await draw_item_list_card(
            DrawInput(
                dark_mode=self._dark_mode,
                locale=self.locale,
                session=self._session,
                filename="farm_notify.webp",
                executor=self._executor,
                loop=self._loop,
            ),
            items,
        )

    async def start(self, i: Interaction) -> None:
        if not self._notify.item_ids:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr(key="farm_notify.empty"),
                description=LocaleStr(key="farm_notify.empty_description"),
            )
            embed.add_acc_info(self._notify.account)
            return await i.followup.send(embed=embed)

        character_choices = i.client.autocomplete_choices[Game.GENSHIN][ItemCategory.CHARACTERS]
        try:
            characters = character_choices[self.locale]
        except KeyError:
            characters = character_choices[Locale.american_english]

        weapon_choices = i.client.autocomplete_choices[Game.GENSHIN][ItemCategory.WEAPONS]
        try:
            weapons = weapon_choices[self.locale]
        except KeyError:
            weapons = weapon_choices[Locale.american_english]

        for name, id_ in characters.items():
            self._item_names[id_] = name
        for name, id_ in weapons.items():
            self._item_names[id_] = name

        await self._fetch_item_icons()
        await super().start(i)
        self.message = await i.original_response()
        return None


class AddItemButton(Button[FarmNotifyView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="farm_notify.add_item"),
            style=ButtonStyle.blurple,
            emoji=ADD,
            row=1,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(key="farm_notify.add_item.embed.description"),
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
            self.view.locale,
            self.view.translator,
            description=LocaleStr(key="farm_notify.remove_item.embed.description"),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class NotifyToggle(ToggleButton[FarmNotifyView]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="reminder_toggle"), row=1)

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        await self.view._notify.fetch_related("account")
        await FarmNotify.filter(account_id=self.view._notify.account.id).update(
            enabled=self.current_toggle,
        )
