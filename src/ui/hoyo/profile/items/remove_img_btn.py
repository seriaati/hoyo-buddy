from typing import TYPE_CHECKING

from discord import ButtonStyle, File

from src.bot.translator import LocaleStr
from src.emojis import DELETE
from src.ui.components import Button

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401
    from .image_select import ImageSelect


class RemoveImageButton(Button["ProfileView"]):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr("Remove Custom Image", key="profile.remove_image.button.label"),
            style=ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view.character_id is not None
        assert self.view._card_settings is not None
        assert self.view._card_settings.current_image is not None

        await self.set_loading_state(i)

        # Remove the current image URL from db
        self.view._card_settings.custom_images.remove(self.view._card_settings.current_image)
        self.view._card_settings.current_image = None
        await self.view._card_settings.save()

        # Update the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        image_select.update_options_defaults(values=["none"])
        image_select.translate(self.view.locale, self.view.translator)

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )
