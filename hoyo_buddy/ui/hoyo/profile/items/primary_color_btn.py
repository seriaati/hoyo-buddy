from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, TextStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.exceptions import InvalidColorError
from hoyo_buddy.ui.components import Button, Modal, TextInput
from hoyo_buddy.utils import is_valid_hex_color

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import ProfileView  # noqa: F401


class PrimaryColorModal(Modal):
    color = TextInput(
        label=LocaleStr(key="profile.primary_color_modal.color.label"),
        placeholder="#000000",
        style=TextStyle.short,
        min_length=7,
        max_length=7,
        required=False,
    )

    def __init__(self, current_color: str | None) -> None:
        super().__init__(title=LocaleStr(key="profile.primary_color_modal.title"))
        self.color.default = current_color


class PrimaryColorButton(Button["ProfileView"]):
    def __init__(self, current_color: str | None, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.primary_color.button.label"),
            style=ButtonStyle.blurple,
            row=2,
            custom_id="profile_primary_color",
            disabled=disabled,
        )
        self.current_color = current_color

    async def callback(self, i: Interaction) -> None:
        assert self.view._card_settings is not None

        # Open the color modal
        modal = PrimaryColorModal(self.current_color)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        color = modal.color.value or None
        if color:
            # Test if the color is valid
            passed = is_valid_hex_color(color)
            if not passed:
                raise InvalidColorError

        # Save the color to settings
        self.view._card_settings.custom_primary_color = self.current_color = color
        await self.view._card_settings.save(update_fields=("custom_primary_color",))

        await self.set_loading_state(i)

        # Redraw the card
        await self.view.update(i, self)
