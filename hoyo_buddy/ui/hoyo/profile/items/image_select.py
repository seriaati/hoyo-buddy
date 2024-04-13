from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.ui.components import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401
    from .remove_img_btn import RemoveImageButton


class ImageSelect(PaginatorSelect["ProfileView"]):
    def __init__(
        self,
        current_image_url: str | None,
        default_collection: list[str],
        custom_images: list[str],
        template: str,
    ) -> None:
        self.current_image_url = current_image_url
        self.default_collection = default_collection
        self.custom_images = custom_images
        self.template = template

        super().__init__(
            self.generate_options(),
            placeholder=LocaleStr("Select an image", key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
            row=0,
            disabled=template == "hattvr1",
        )

    def generate_options(self) -> list[SelectOption]:
        """Generates a list of SelectOption objects based on the available image URLs.

        Returns:
            A list of SelectOption objects representing the available image options.
        """
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr("Official art", key="profile.image_select.none.label"),
                description=LocaleStr(
                    "Doesn't work with Hoyo Buddy's templates",
                    key="profile.image_select.none.description",
                ),
                value="none",
                default=self.current_image_url is None and "hb" not in self.template,
            )
        ]
        added_values: set[str] = set()

        for collection in [self.default_collection, self.custom_images]:
            for index, url in enumerate(collection, start=1):
                if url not in added_values:
                    options.append(self.get_image_url_option(url, index))
                    added_values.add(url)

        # HB templates don't wotk with official art, default image is always Hoyo Buddy Collection (1)
        if "hb" in self.template and self.current_image_url is None:
            options[1].default = True
        return options

    def get_image_url_option(self, image_url: str, num: int) -> SelectOption:
        """Returns a SelectOption object based on the provided image URL and number.

        Args:
            image_url (str): The URL of the image.
            num (int): The number associated with the image.

        Returns:
            SelectOption: The SelectOption object representing the image URL option.

        """
        label = (
            LocaleStr(
                "Hoyo Buddy Collection ({num})",
                key="profile.image_select.default_collection.label",
                num=num,
            )
            if image_url in self.default_collection
            else LocaleStr(
                "Custom Image ({num})",
                key="profile.image_select.custom_image.label",
                num=num,
            )
        )
        option = SelectOption(
            label=label,
            value=image_url,
            description=image_url[:100],
            default=image_url == self.current_image_url,
        )
        return option

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Update the current image URL in db
        self.view._card_settings.current_image = (
            None if self.values[0] == "none" else self.values[0]
        )
        await self.view._card_settings.save(update_fields=("current_image",))

        # Enable the remove image button if the image is custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = (
            self.values[0] in self.default_collection or self.values[0] == "none"
        )

        # Redraw the card
        await self.view.update(i, self)
