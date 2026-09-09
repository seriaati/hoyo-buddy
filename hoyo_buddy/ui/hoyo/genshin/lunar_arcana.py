from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from hoyo_buddy import ui
from hoyo_buddy.constants import LUNAR_ARCANA_LOCKED_CARD_URL
from hoyo_buddy.db import draw_locale
from hoyo_buddy.draw.funcs.hoyo.genshin.lunar_arcana import LUNAR_ARCANA_NUMERALS
from hoyo_buddy.draw.main_funcs import draw_lunar_arcana_card
from hoyo_buddy.emojis import BACK
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput

if TYPE_CHECKING:
    from collections.abc import Sequence

    import genshin

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User

OVERVIEW_FILENAME = "lunar_arcana.png"


def _numeral(index: int) -> str:
    return LUNAR_ARCANA_NUMERALS[index] if index < len(LUNAR_ARCANA_NUMERALS) else ""


class LunarArcanaView(ui.LayoutView):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.overview_url = f"attachment://{OVERVIEW_FILENAME}"
        self._collection: genshin.models.LunarArcanaCollection | None = None

    @property
    def collection(self) -> genshin.models.LunarArcanaCollection:
        if self._collection is None:
            msg = "Lunar arcana collection is not fetched yet"
            raise ValueError(msg)
        return self._collection

    def show_overview(self) -> None:
        self.clear_items()
        self.add_item(
            ui.Container(
                ui.TextDisplay(f"-# {self.account.blurred_display}"),
                discord.ui.MediaGallery(discord.MediaGalleryItem(self.overview_url)),
                ui.ActionRow(BrowseCardsButton()),
            )
        )

    def show_card(self, index: int) -> None:
        card = self.collection.cards[index]
        if card.unlocked:
            status = LocaleStr(key="lunar_arcana_owned_count", count=card.unlock_count)
            image_url = card.icon
        else:
            status = LocaleStr(key="lunar_arcana_card_locked")
            image_url = LUNAR_ARCANA_LOCKED_CARD_URL

        self.clear_items()
        self.add_item(
            ui.Container(
                ui.TextDisplay(f"-# {self.account.blurred_display}"),
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="## {numeral} · {name}\n{status}",
                        numeral=_numeral(index),
                        name=card.name,
                        status=status,
                    )
                ),
                discord.ui.MediaGallery(discord.MediaGalleryItem(image_url)),
                ui.ActionRow(CardSelect(self.collection.cards, index)),
                ui.ActionRow(BackToOverviewButton()),
            )
        )

    def _remember_overview_url(self, message: discord.Message) -> None:
        """Use the uploaded image's CDN URL so later edits don't depend on attachment references."""
        for component in message.components:
            if not isinstance(component, discord.components.Container):
                continue
            for child in component.children:
                if isinstance(child, discord.components.MediaGalleryComponent) and child.items:
                    self.overview_url = child.items[0].media.url
                    return

    async def start(self, i: Interaction) -> None:
        client = self.account.client
        client.set_lang(self.locale)
        theater = await client.get_imaginarium_theater(self.account.uid)
        if theater.lunar_arcana_collection is None:
            raise FeatureNotImplementedError(platform=self.account.platform, game=Game.GENSHIN)

        self._collection = theater.lunar_arcana_collection
        overview = await draw_lunar_arcana_card(
            DrawInput(
                dark_mode=True,
                locale=draw_locale(self.locale, self.account),
                session=i.client.session,
                filename=OVERVIEW_FILENAME,
                executor=i.client.executor,
                loop=i.client.loop,
            ),
            self._collection,
        )

        self.show_overview()
        self.message = await i.edit_original_response(view=self, attachments=[overview])
        self._remember_overview_url(self.message)


class BrowseCardsButton(ui.Button[LunarArcanaView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="lunar_arcana_browse_button_label"),
            style=discord.ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        # clear_items() detaches this button from the view, so grab it first
        view = self.view
        view.show_card(0)
        await i.response.edit_message(view=view)


class BackToOverviewButton(ui.Button[LunarArcanaView]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="lunar_arcana_back_button_label"), emoji=BACK)

    async def callback(self, i: Interaction) -> None:
        view = self.view
        view.show_overview()
        await i.response.edit_message(view=view)


class CardSelect(ui.Select[LunarArcanaView]):
    def __init__(self, cards: Sequence[genshin.models.LunarArcanaCard], current: int) -> None:
        options = [
            ui.SelectOption(
                label=f"{_numeral(index)} · {card.name}",
                value=str(index),
                description=LocaleStr(key="lunar_arcana_owned_count", count=card.unlock_count)
                if card.unlocked
                else LocaleStr(key="lunar_arcana_card_locked"),
                default=index == current,
            )
            for index, card in enumerate(cards)
        ]
        super().__init__(
            options=options, placeholder=LocaleStr(key="lunar_arcana_select_placeholder")
        )

    async def callback(self, i: Interaction) -> None:
        view = self.view
        view.show_card(int(self.values[0]))
        await i.response.edit_message(view=view)
