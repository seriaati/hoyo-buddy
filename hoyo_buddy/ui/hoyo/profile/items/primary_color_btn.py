from typing import TYPE_CHECKING

from discord import ButtonStyle, File, TextStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.exceptions import InvalidColorError
from hoyo_buddy.ui.components import Button, Modal, TextInput
from hoyo_buddy.utils import is_valid_hex_color

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class PrimaryColorModal(Modal):
    color = TextInput(
        label=LocaleStr("Color (hex code)", key="profile.primary_color_modal.color.label"),
        placeholder="#000000",
        style=TextStyle.short,
        min_length=7,
        max_length=7,
    )

    def __init__(self, current_color: str | None) -> None:
        super().__init__(
            title=LocaleStr("Change Card Color", key="profile.primary_color_modal.title")
        )
        self.color.default = current_color


class PrimaryColorButton(Button["ProfileView"]):
    def __init__(self, current_color: str | None, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr("Change Color", key="profile.primary_color.button.label"),
            style=ButtonStyle.blurple,
            row=2,
            custom_id="profile_primary_color",
            disabled=disabled,
        )
        self.current_color = current_color

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        # Open the color modal
        modal = PrimaryColorModal(self.current_color)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        color = modal.color.value
        if not color:
            return

        # Test if the color is valid
        passed = is_valid_hex_color(color)
        if not passed:
            raise InvalidColorError

        # Save the color to settings
        self.view._card_settings.custom_primary_color = modal.color.value
        await self.view._card_settings.save()

        # Redraw the card
        await self.set_loading_state(i)
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )
