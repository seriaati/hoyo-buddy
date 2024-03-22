from typing import TYPE_CHECKING

from discord import ButtonStyle
from seria.utils import split_list_to_chunks

from ...bot.translator import LocaleStr
from ...db.models import FarmNotify
from ...draw.main_funcs import draw_item_list_card
from ...embeds import DefaultEmbed
from ...emojis import ADD, DELETE
from ...hoyo.clients.ambr_client import AmbrAPIClient
from ...models import DrawInput, ItemWithTrailing
from ..components import Button, ToggleButton
from ..paginator import Page, PaginatorView

if TYPE_CHECKING:
    import aiohttp
    from discord import Locale, Member, User
    from discord.file import File

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator


class FarmNotifyView(PaginatorView):
    def __init__(
        self,
        farm_notify: "FarmNotify",
        dark_mode: bool,
        session: "aiohttp.ClientSession",
        *,
        author: "User | Member | None",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        self._split_item_ids = split_list_to_chunks(farm_notify.item_ids, 12)
        pages = [
            Page(
                embed=DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Farm Reminder List", key="farm_notify.title"),
                    description=LocaleStr(
                        "You will be reminded when the materials of characters/weapons in this list are farmable.",
                        key="farm_notify.description",
                    ),
                )
                .set_footer(
                    text=LocaleStr(
                        "Page {current_page}/{total_pages}",
                        key="page_footer",
                        current_page=i + 1,
                        total_pages=len(self._split_item_ids),
                    )
                )
                .set_image(url="attachment://farm_notify.webp")
            )
            for i in range(len(self._split_item_ids))
        ]

        self._notify = farm_notify
        self._dark_mode = dark_mode
        self._session = session
        self._item_names: dict[str, str] = {}
        self._item_icons: dict[str, str] = {}

        super().__init__(pages, author=author, locale=locale, translator=translator)

    def _add_buttons(self) -> None:
        super()._add_buttons()
        self.add_item(NotifyToggle(self._notify.enabled))
        self.add_item(AddItemButton())
        self.add_item(RemoveItemButton())

    async def _get_item_icon_and_names(self) -> None:
        async with AmbrAPIClient(self.locale, self.translator) as client:
            characters = await client.fetch_characters()
            weapons = await client.fetch_weapons()

        self._item_names = {c.id: c.name for c in characters} | {str(w.id): w.name for w in weapons}
        self._item_icons = {c.id: c.icon for c in characters} | {str(w.id): w.icon for w in weapons}

    async def _create_file(self) -> "File":
        items = [
            ItemWithTrailing(
                icon=self._item_icons[item_id],
                title=self._item_names[item_id],
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
            ),
            items,
        )

    async def start(self, i: "INTERACTION") -> None:
        if not self._notify.item_ids:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr(
                    "You have no items in your farm reminder list", key="farm_notify.empty"
                ),
                description=LocaleStr(
                    "Add items to your farm reminder list by using the </farm add> command",
                    key="farm_notify.empty_description",
                ),
            )
            return await i.response.send_message(embed=embed)

        await self._get_item_icon_and_names()
        await super().start(i)
        self.message = await i.original_response()


class AddItemButton(Button[FarmNotifyView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Add item", key="farm_notify.add_item"),
            style=ButtonStyle.blurple,
            emoji=ADD,
            row=1,
        )

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(
                "To add items, use the </farm add> command",
                key="farm_notify.add_item.embed.description",
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class RemoveItemButton(Button[FarmNotifyView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Remove item", key="farm_notify.remove_item"),
            style=ButtonStyle.red,
            emoji=DELETE,
            row=1,
        )

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            description=LocaleStr(
                "To remove items, use the </farm remove> command",
                key="farm_notify.remove_item.embed.description",
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class NotifyToggle(ToggleButton[FarmNotifyView]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr("Reminder", key="reminder_toggle"), row=1)

    async def callback(self, i: "INTERACTION") -> None:
        await super().callback(i, edit=True)
        await self.view._notify.fetch_related("account")
        await FarmNotify.filter(account_id=self.view._notify.account.id).update(
            enabled=self.current_toggle
        )
