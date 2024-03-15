from typing import TYPE_CHECKING

from discord import ButtonStyle, File, Locale, Member, User

from ....bot.translator import LocaleStr
from ....draw.main_funcs import draw_spiral_abyss_card
from ....exceptions import NoAbyssDataError
from ....models import DrawInput
from ...components import Button, View

if TYPE_CHECKING:
    from collections.abc import Sequence

    import aiohttp
    from genshin.models import Character, SpiralAbyss

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator

    from ....db.models import HoyoAccount


class AbyssView(View):
    def __init__(
        self,
        account: "HoyoAccount",
        dark_mode: bool,
        *,
        author: User | Member,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._dark_mode = dark_mode
        self._account = account
        self._previous = False

        self._abyss: dict[bool, "SpiralAbyss"] = {}
        self._characters: Sequence[Character] = []

    async def _fetch_data(self) -> None:
        client = self._account.client
        if self._previous not in self._abyss:
            self._abyss[self._previous] = await client.get_genshin_spiral_abyss(
                self._account.uid, previous=self._previous
            )
        if self._abyss[self._previous].max_floor == "0-0":
            raise NoAbyssDataError()
        if not self._characters:
            self._characters = await client.get_genshin_characters(self._account.uid)

    async def _draw_card(self, session: "aiohttp.ClientSession") -> File:
        assert self._abyss is not None

        return await draw_spiral_abyss_card(
            DrawInput(
                dark_mode=self._dark_mode,
                locale=self.locale,
                session=session,
                filename="abyss.webp",
            ),
            self._abyss[self._previous],
            self._characters,
            self.translator,
        )

    def _add_items(self) -> None:
        self.add_item(CurrentButton())
        self.add_item(PreviousButton())

    def _update_button_styles(self) -> None:
        current_btn: CurrentButton = self.get_item("abyss_current")
        previous_btn: PreviousButton = self.get_item("abyss_previous")

        if self._previous:
            previous_btn.style = ButtonStyle.blurple
            current_btn.style = ButtonStyle.gray
        else:
            previous_btn.style = ButtonStyle.gray
            current_btn.style = ButtonStyle.blurple

    async def update(self, session: "aiohttp.ClientSession") -> File:
        await self._fetch_data()
        file_ = await self._draw_card(session)
        self._update_button_styles()
        return file_

    async def start(self, i: "INTERACTION") -> None:
        await i.response.defer()

        await self._fetch_data()
        file_ = await self._draw_card(i.client.session)

        self._add_items()
        await i.edit_original_response(attachments=[file_], view=self)
        self.message = await i.original_response()


class CurrentButton(Button[AbyssView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Current Lunar Phase", key="abyss.current"),
            style=ButtonStyle.blurple,
            custom_id="abyss_current",
            row=0,
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._previous = False
        await self.set_loading_state(i)
        file_ = await self.view.update(i.client.session)
        await self.unset_loading_state(i, attachments=[file_])


class PreviousButton(Button[AbyssView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Previous Lunar Phase", key="abyss.previous"),
            style=ButtonStyle.gray,
            custom_id="abyss_previous",
            row=1,
        )

    async def callback(self, i: "INTERACTION") -> None:
        self.view._previous = True
        await self.set_loading_state(i)
        file_ = await self.view.update(i.client.session)
        await self.unset_loading_state(i, attachments=[file_])
