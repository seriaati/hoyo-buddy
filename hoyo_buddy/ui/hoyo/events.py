from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle
from discord.utils import format_dt

from hoyo_buddy.constants import UTC_8
from hoyo_buddy.db import HoyoAccount, get_dyk
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.components import Button, PaginatorSelect, Select, SelectOption, View
from hoyo_buddy.ui.paginator import Page, PaginatorView
from hoyo_buddy.utils import remove_html_tags

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin
    from discord import Locale

    from hoyo_buddy.types import Interaction, User


class EventsView(View):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)

        self.account = account
        self.anns: Sequence[genshin.models.Announcement] = []
        self.banner_ann_ids: list[int] = []
        self.ann_id: int = 0
        self.ann_type: str = ""

    def _add_items(self) -> None:
        self.add_item(EventSelector(self.anns))
        self.add_item(EventTypeSelector(self.anns, self.ann_type))
        self.add_item(ViewContentButton())

    def _get_ann(self, ann_id: int) -> genshin.models.Announcement:
        return next((ann for ann in self.anns if ann.id == ann_id), self.anns[0])

    def _get_ann_embed(self, ann: genshin.models.Announcement) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            title=remove_html_tags(ann.title),
            description=remove_html_tags(ann.content)[:200] + "...",
        )
        embed.set_author(name=ann.subtitle)
        embed.set_image(url=ann.banner or ann.img)
        embed.add_field(
            name=LocaleStr(key="events_view_start_date_embed_field"),
            value=format_dt(ann.start_time.replace(tzinfo=UTC_8), "R"),
        )
        embed.add_field(
            name=LocaleStr(key="events_view_end_date_embed_field"),
            value=format_dt(ann.end_time.replace(tzinfo=UTC_8), "R"),
        )
        return embed

    @property
    def first_ann(self) -> genshin.models.Announcement:
        anns = (
            [ann for ann in self.anns if ann.type_label == self.ann_type]
            if self.ann_type != "banners"
            else [ann for ann in self.anns if ann.id in self.banner_ann_ids]
        )
        return anns[0]

    async def _fetch_anns(self) -> None:
        client = self.account.client
        client.set_lang(self.locale)
        zh_client = ProxyGenshinClient(lang="zh-tw")

        if self.account.game is Game.ZZZ:
            self.anns = await client.get_zzz_announcements()
            zh_anns = await zh_client.get_zzz_announcements()
            keyword = "調頻"
        else:
            raise FeatureNotImplementedError(game=self.account.game)

        self.banner_ann_ids = [ann.id for ann in zh_anns if keyword in ann.title]
        self.ann_type = self.anns[0].type_label
        self.ann_id = self.anns[0].id

    async def start(self, i: Interaction) -> None:
        await self._fetch_anns()
        self._add_items()

        await i.followup.send(
            embed=self._get_ann_embed(self.first_ann), view=self, content=await get_dyk(i)
        )
        self.message = await i.original_response()


class EventSelector(PaginatorSelect[EventsView]):
    def __init__(self, anns: Sequence[genshin.models.Announcement]) -> None:
        anns = list({ann.id: ann for ann in anns}.values())
        super().__init__(
            custom_id="events_view_ann_select",
            placeholder=LocaleStr(key="events_view_ann_select_placeholder"),
            options=[self._get_ann_option(ann, i == 0) for i, ann in enumerate(anns) if ann.title],
        )

    def _get_ann_option(self, ann: genshin.models.Announcement, default: bool) -> SelectOption:
        start_time = ann.start_time.replace(tzinfo=UTC_8)
        end_time = ann.end_time.replace(tzinfo=UTC_8)
        return SelectOption(
            label=remove_html_tags(ann.title)[:100],
            value=str(ann.id),
            default=default,
            description=f"{start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}",
        )

    def set_options(self, anns: Sequence[genshin.models.Announcement]) -> None:
        self.options = [
            self._get_ann_option(ann, i == 0) for i, ann in enumerate(anns) if ann.title
        ]

    async def callback(self, i: Interaction) -> None:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view.ann_id = int(self.values[0])
        ann = self.view._get_ann(self.view.ann_id)
        embed = self.view._get_ann_embed(ann)

        self.update_options_defaults()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


class EventTypeSelector(Select[EventsView]):
    def __init__(self, anns: Sequence[genshin.models.Announcement], current: str) -> None:
        super().__init__(
            placeholder=LocaleStr(key="events_view_ann_type_select_placeholder"),
            options=[
                SelectOption(label=ann_type, value=ann_type, default=ann_type == current)
                for ann_type in self._get_ann_types(anns)
            ]
            + [
                SelectOption(
                    label=LocaleStr(key="events_view_banner_type_label"),
                    value="banners",
                    default=current == "banners",
                )
            ],
        )

    @staticmethod
    def _get_ann_types(anns: Sequence[genshin.models.Announcement]) -> list[str]:
        types = list({ann.type_label for ann in anns})
        types.sort()
        return types

    async def callback(self, i: Interaction) -> None:
        ann_type = self.values[0]
        self.view.ann_type = ann_type

        anns = (
            [ann for ann in self.view.anns if ann.type_label == ann_type]
            if ann_type != "banners"
            else [ann for ann in self.view.anns if ann.id in self.view.banner_ann_ids]
        )
        event_selector: EventSelector = self.view.get_item("events_view_ann_select")
        event_selector.set_options(anns)
        event_selector.translate(self.view.locale)

        self.update_options_defaults()
        embed = self.view._get_ann_embed(self.view.first_ann)
        await i.response.edit_message(embed=embed, view=self.view)


class ViewContentButton(Button[EventsView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="events_view_content_label"), style=ButtonStyle.blurple
        )

    async def callback(self, i: Interaction) -> None:
        ann = self.view._get_ann(self.view.ann_id)
        content = remove_html_tags(ann.content)
        if not content:
            self.disabled = True
            return await i.response.edit_message(view=self.view)

        # Split ann content by 2000 characters
        contents: list[str] = [content[i : i + 2000] for i in range(0, len(content), 2000)]
        pages = [Page(content=content) for content in contents]
        view = PaginatorView(pages, author=i.user, locale=self.view.locale)
        await view.start(i, ephemeral=True, followup=True)
        return None
