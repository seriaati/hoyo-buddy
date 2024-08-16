from __future__ import annotations

from typing import TYPE_CHECKING

import genshin
from discord import ButtonStyle
from discord.utils import format_dt

from hoyo_buddy.constants import UTC_8, locale_to_gpy_lang
from hoyo_buddy.db.models import get_dyk
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.l10n import LocaleStr, Translator
from hoyo_buddy.ui.components import Button, Select, SelectOption, View
from hoyo_buddy.ui.paginator import Page, PaginatorView
from hoyo_buddy.utils import ephemeral, format_ann_content

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale

    from hoyo_buddy.types import Interaction, User


class EventsView(View):
    def __init__(
        self,
        game: Game,
        *,
        author: User,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._game = game
        self.anns: Sequence[genshin.models.Announcement] = []
        self.ann_id: int = 0
        self.ann_type: str = ""

    def _add_items(self) -> None:
        self.add_item(EventSelector(self.anns))
        self.add_item(EventTypeSelector(self.anns, self.ann_type))
        self.add_item(ViewContentButton())

    def _get_ann(self, ann_id: int) -> genshin.models.Announcement:
        return next(ann for ann in self.anns if ann.id == ann_id)

    def _get_ann_embed(self, ann: genshin.models.Announcement) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, self.translator, title=format_ann_content(ann.title))
        embed.set_author(name=ann.subtitle)
        embed.set_image(url=ann.banner)
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
        anns = [ann for ann in self.anns if ann.type_label == self.ann_type]
        return anns[0]

    async def _fetch_anns(self) -> None:
        client = genshin.Client(lang=locale_to_gpy_lang(self.locale))
        if self._game is Game.GENSHIN:
            self.anns = await client.get_genshin_announcements()
        elif self._game is Game.STARRAIL:
            self.anns = await client.get_starrail_announcements()
        elif self._game is Game.ZZZ:
            self.anns = await client.get_zzz_announcements()
        else:
            raise FeatureNotImplementedError(game=self._game)

        self.ann_type = self.anns[0].type_label
        self.ann_id = self.anns[0].id

    async def start(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))
        await self._fetch_anns()
        self._add_items()

        await i.followup.send(
            embed=self._get_ann_embed(self.first_ann), view=self, content=await get_dyk(i)
        )
        self.message = await i.original_response()


class EventSelector(Select[EventsView]):
    def __init__(self, anns: Sequence[genshin.models.Announcement]) -> None:
        super().__init__(
            custom_id="events_view_ann_select",
            placeholder=LocaleStr(key="events_view_ann_select_placeholder"),
            options=[self._get_ann_option(ann, i == 0) for i, ann in enumerate(anns)],
        )

    def _get_ann_option(self, ann: genshin.models.Announcement, default: bool) -> SelectOption:
        return SelectOption(
            label=format_ann_content(ann.title)[:100], value=str(ann.id), default=default
        )

    def set_options(self, anns: Sequence[genshin.models.Announcement]) -> None:
        self.options = [self._get_ann_option(ann, i == 0) for i, ann in enumerate(anns)]

    async def callback(self, i: Interaction) -> None:
        self.view.ann_id = int(self.values[0])
        ann = self.view._get_ann(self.view.ann_id)
        embed = self.view._get_ann_embed(ann)

        self.update_options_defaults()
        await i.response.edit_message(embed=embed, view=self.view)


class EventTypeSelector(Select[EventsView]):
    def __init__(self, anns: Sequence[genshin.models.Announcement], current: str) -> None:
        ann_types = self._get_ann_types(anns)
        super().__init__(
            placeholder=LocaleStr(key="events_view_ann_type_select_placeholder"),
            options=[
                SelectOption(label=ann_type, value=ann_type, default=ann_type == current)
                for ann_type in ann_types
            ],
        )

    def _get_ann_types(self, anns: Sequence[genshin.models.Announcement]) -> list[str]:
        return list({ann.type_label for ann in anns})

    async def callback(self, i: Interaction) -> None:
        ann_type = self.values[0]
        self.view.ann_type = ann_type

        anns = [ann for ann in self.view.anns if ann.type_label == ann_type]
        event_selector: EventSelector = self.view.get_item("events_view_ann_select")
        event_selector.set_options(anns)

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
        # Split ann content by 2000 characters
        content = format_ann_content(ann.content)
        contents: list[str] = [content[i : i + 2000] for i in range(0, len(content), 2000)]
        pages = [Page(content=content) for content in contents]
        view = PaginatorView(
            pages, author=i.user, locale=self.view.locale, translator=self.view.translator
        )
        await view.start(i, ephemeral=True, followup=True)
