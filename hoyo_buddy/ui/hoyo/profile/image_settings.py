from __future__ import annotations

from enum import StrEnum
from typing import Any

from discord import ButtonStyle, Interaction, Locale

from hoyo_buddy.db.models import CardSettings
from hoyo_buddy.embeds import Embed
from hoyo_buddy.emojis import DELETE
from hoyo_buddy.l10n import EnumStr, LocaleStr, Translator
from hoyo_buddy.types import User
from hoyo_buddy.ui.components import Button, PaginatorSelect, Select, SelectOption, View


class ImageType(StrEnum):
    BUILD_CARD = "build_card"
    TEAM_CARD = "team_card"
    TEAM_CARD_BACKGROUND = "team_card_background"


class ImageSettingsView(View):
    def __init__(
        self, card_settings: CardSettings, *, author: User, locale: Locale, translator: Translator
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.card_settings = card_settings
        self.image_type = ImageType.BUILD_CARD

    def get_settings_embed(self) -> Embed:
        card_settings = self.card_settings
        character = self._get_current_character()

        color = card_settings.custom_primary_color or get_default_color(character, self._card_data)
        embed = Embed(
            locale=self.locale,
            translator=self.translator,
            title=LocaleStr(key="card_settings.modifying_for", name=character.name),
            color=int(color.lstrip("#"), 16) if color is not None else 6649080,
        )
        default_str = LocaleStr(key="card_settings.color_default").translate(
            self.translator, self.locale
        )
        if color is not None:
            value = self._get_color_markdown(color)
            if card_settings.custom_primary_color is None:
                value += f" ({default_str})"
        else:
            value = LocaleStr(key="card_settings.no_color")

        embed.add_field(name=LocaleStr(key="card_settings.card_color"), value=value, inline=False)
        image_url = card_settings.current_image or get_default_art(character)
        embed.set_image(url=image_url)
        embed.add_field(
            name=LocaleStr(key="card_settings.current_image"), value=image_url, inline=False
        )

        embed.set_footer(text=LocaleStr(key="card_settings.footer"))
        return embed


class ImageSelect(PaginatorSelect[ImageSettingsView]):
    def __init__(
        self,
        current_image_url: str | None,
        default_collection: list[str],
        custom_images: list[str],
        template: str,
        disabled: bool,
        row: int,
    ) -> None:
        self.current_image_url = current_image_url
        self.default_collection = default_collection
        self.custom_images = custom_images
        self.template = template

        super().__init__(
            self.get_options(),
            placeholder=LocaleStr(key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
            disabled=disabled,
            row=row,
        )

    def update(
        self,
        *,
        current_image: str | None,
        custom_images: list[str],
        default_collection: list[str] | None = None,
    ) -> None:
        self.current_image_url = current_image
        self.custom_images = custom_images
        self.default_collection = default_collection or self.default_collection

        self.options_before_split = self.get_options()
        self.options = self.process_options()
        if current_image is not None:
            self.set_page_based_on_value(current_image)
        self.translate(self.view.locale, self.view.translator)

    def get_options(self) -> list[SelectOption]:
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr(key="profile.image_select.none.label"),
                value="none",
                default=self.current_image_url is None,
            )
        ]
        added_values: set[str] = set()

        for collection in [self.default_collection, self.custom_images]:
            for index, url in enumerate(collection, start=1):
                if url not in added_values:
                    options.append(self._get_select_option(url, index))
                    added_values.add(url)

        return options

    def _get_select_option(self, image_url: str, num: int) -> SelectOption:
        label = (
            LocaleStr(key="profile.image_select.default_collection.label", num=num)
            if image_url in self.default_collection
            else LocaleStr(key="profile.image_select.custom_image.label", num=num)
        )
        return SelectOption(
            label=label, value=image_url, default=image_url == self.current_image_url
        )

    async def callback(self, i: Interaction) -> None:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()

        # Update the current image URL in db
        self.view.card_settings.current_image = None if self.values[0] == "none" else self.values[0]
        await self.view.card_settings.save(update_fields=("current_image",))

        # Enable the remove image button if the image is custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = (
            self.values[0] in self.default_collection or self.values[0] == "none"
        )

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


class ImageTypeSelector(Select[ImageSettingsView]):
    def __init__(self) -> None:
        super().__init__(
            options=[SelectOption(label=EnumStr(type_), value=type_) for type_ in ImageType],
            placeholder=LocaleStr(key="image_type_select_placeholder"),
        )

    async def callback(self, i: Interaction) -> Any:
        self.view.image_type = ImageType(self.values[0])


class RemoveImageButton(Button[ImageSettingsView]):
    def __init__(self, *, disabled: bool, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.remove_image.button.label"),
            style=ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        # Disable self
        self.disabled = True

        # Remove the current image URL
        current_image = self.view.card_settings.current_image
        if current_image is None:
            return

        if current_image in self.view.card_settings.custom_images:
            # For whatever reason, the current image may not be in the custom images list
            self.view.card_settings.custom_images.remove(current_image)

        # Update the current image URL
        self.view.card_settings.current_image = None
        self.view.card_settings.custom_images = list(set(self.view.card_settings.custom_images))
        await self.view.card_settings.save(update_fields=("custom_images", "current_image"))

        # Update image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=None, custom_images=self.view.card_settings.custom_images)

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
