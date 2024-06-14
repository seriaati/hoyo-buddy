from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import DELETE
from hoyo_buddy.ui.components import Button

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import ProfileView  # noqa: F401
    from .image_select import ImageSelect


class RemoveImageButton(Button["ProfileView"]):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.remove_image.button.label"),
            style=ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
            row=3,
        )

    async def callback(self, i: Interaction) -> None:
        assert self.view.character_id is not None
        assert self.view._card_settings is not None

        # Disable self
        self.disabled = True

        await self.set_loading_state(i)

        # Remove the current image URL
        current_image = self.view._card_settings.current_image
        assert current_image is not None
        self.view._card_settings.custom_images.remove(current_image)

        # Update the current image URL
        self.view._card_settings.current_image = None
        await self.view._card_settings.save(update_fields=("custom_images", "current_image"))

        # Update image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.current_image_url = self.view._card_settings.current_image
        image_select.custom_images = self.view._card_settings.custom_images
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        image_select.translate(self.view.locale, self.view.translator)

        # Redraw the card
        await self.view.update(i, self)
