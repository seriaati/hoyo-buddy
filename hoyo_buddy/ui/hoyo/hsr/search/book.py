from typing import TYPE_CHECKING, Any

from hoyo_buddy.exceptions import InvalidQueryError
from hoyo_buddy.hoyo.clients.yatta_client import YattaAPIClient
from hoyo_buddy.ui import Select, SelectOption, View

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import LocaleStr, Translator
    from hoyo_buddy.embeds import DefaultEmbed


class BookUI(View):
    def __init__(
        self,
        book_id: str,
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
        timeout: float | None = 180,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator, timeout=timeout)

        self.book_id = book_id
        self.series_embeds: dict[str, "DefaultEmbed"] = {}

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()

        async with YattaAPIClient(self.locale, self.translator) as api:
            try:
                book_id = int(self.book_id)
            except ValueError as e:
                raise InvalidQueryError from e

            book_detail = await api.fetch_book_detail(book_id)
            self.series_embeds = {
                str(series.id): api.get_book_series_embed(book_detail, series)
                for series in book_detail.series
            }
        if book_detail.series:
            self.add_item(
                SeriesSelector(
                    options=[
                        SelectOption(label=series.name, value=str(series.id), default=index == 0)
                        for index, series in enumerate(book_detail.series)
                    ]
                )
            )
        await i.edit_original_response(embed=list(self.series_embeds.values())[0], view=self)


class SeriesSelector(Select["BookUI"]):
    def __init__(
        self,
        *,
        placeholder: "LocaleStr | str | None" = None,
        options: list["SelectOption"],
    ) -> None:
        super().__init__(placeholder=placeholder, options=options)

    async def callback(self, i: "INTERACTION") -> Any:
        self.update_options_defaults()
        await i.response.edit_message(embed=self.view.series_embeds[self.values[0]], view=self.view)
