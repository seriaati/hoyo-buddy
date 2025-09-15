from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import discord
from discord.utils import MISSING
from loguru import logger

from hoyo_buddy.bot.error_handler import get_error_embed
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.exceptions import InvalidInputError
from hoyo_buddy.l10n import LocaleStr, translator

from .label import Label
from .select import Select
from .text_display import TextDisplay
from .text_input import TextInput

if TYPE_CHECKING:
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

__all__ = ("Modal",)


class Modal(discord.ui.Modal):
    def __init__(self, *, title: LocaleStr | str, custom_id: str = MISSING) -> None:
        super().__init__(
            title=title if isinstance(title, str) else "#NoTrans",
            timeout=600,
            custom_id=self.__class__.__name__ if custom_id is MISSING else custom_id,
        )
        self.locale_str_title = title

    async def on_error(self, i: Interaction, error: Exception) -> None:
        locale = await get_locale(i)
        embed, recognized = get_error_embed(error, locale)
        if not recognized:
            i.client.capture_exception(error)

        if not i.response.is_done():
            await i.response.send_message(embed=embed, ephemeral=True)
        else:
            await i.followup.send(embed=embed, ephemeral=True)

    async def on_submit(self, i: Interaction) -> None:
        self.validate_inputs()
        with contextlib.suppress(discord.NotFound):
            await i.response.defer()
        self.stop()

    def translate(self, locale: Locale) -> None:
        self.title = translator.translate(self.locale_str_title, locale, max_length=45)

        for item in self.children:
            if isinstance(item, (Label, Select, TextInput, TextDisplay)):
                item.translate(locale)

    def validate_inputs(self) -> None:
        """Validates all TextInput children of the modal. Raises InvalidInputError if any input is invalid."""
        for item in self.children:
            component = item.component if isinstance(item, Label) else item

            if isinstance(component, TextInput) and component.is_digit:
                if isinstance(item, Label):
                    item_text = item.text
                elif isinstance(item, TextInput):
                    item_text = item.label
                else:
                    logger.error(f"Unable to get item_text for component: {type(item)}")
                    item_text = ""

                try:
                    value = int(component.value)
                except ValueError as e:
                    raise InvalidInputError(
                        LocaleStr(key="invalid_input.input_needs_to_be_int", input=item_text)
                    ) from e

                if component.max_value is not None and value > component.max_value:
                    raise InvalidInputError(
                        LocaleStr(
                            key="invalid_input.input_out_of_range.max_value",
                            input=item_text,
                            max_value=component.max_value,
                        )
                    )

                if component.min_value is not None and value < component.min_value:
                    raise InvalidInputError(
                        LocaleStr(
                            key="invalid_input.input_out_of_range.min_value",
                            input=item_text,
                            min_value=component.min_value,
                        )
                    )
