from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import enka
from discord import ButtonStyle, TextStyle
from genshin.models import ZZZFullAgent, ZZZPartialAgent
from loguru import logger
from seria.utils import read_json

from hoyo_buddy.constants import (
    HSR_DEFAULT_ART_URL,
    PLAYER_BOY_GACHA_ART,
    PLAYER_GIRL_GACHA_ART,
    ZZZ_M3_ART_URL,
    ZZZ_M6_ART_URL,
)
from hoyo_buddy.db import CustomImage
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD, DELETE, EDIT, PHOTO_ADD
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import InvalidImageURLError, NSFWPromptError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import HoyolabGICharacter, HoyolabHSRCharacter, ZZZEnkaCharacter
from hoyo_buddy.ui import (
    Button,
    Label,
    Modal,
    PaginatorSelect,
    Select,
    SelectOption,
    TextInput,
    ToggleButton,
    View,
)
from hoyo_buddy.utils import get_pixiv_proxy_img, is_image_url, test_url_validity, upload_image

from .card_settings import get_card_settings
from .items.settings_chara_select import CharacterSelect as SettingsCharacterSelect
from .templates import DISABLE_IMAGE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Member, User

    from hoyo_buddy.db import CardSettings, Settings
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import Character


async def get_team_image(user_id: int, character_id: str, *, game: Game) -> str | None:
    card_settings = await get_card_settings(user_id, character_id, game=game)
    return card_settings.current_team_image


def get_default_art(
    character: Character | ZZZFullAgent, *, is_team: bool, use_m3_art: bool = False
) -> str:
    if isinstance(character, ZZZPartialAgent | ZZZFullAgent | ZZZEnkaCharacter):
        if is_team:
            return character.banner_icon
        if use_m3_art:
            return ZZZ_M3_ART_URL.format(char_id=character.id)
        return ZZZ_M6_ART_URL.format(char_id=character.id)

    if isinstance(character, enka.gi.Character | HoyolabGICharacter):
        if character.costume is not None:
            return character.costume.icon.gacha
        if "10000005" in str(character.id):  # PlayerBoy
            return PLAYER_BOY_GACHA_ART
        if "10000007" in str(character.id):  # PlayerGirl
            return PLAYER_GIRL_GACHA_ART
        return character.icon.gacha

    if isinstance(character, enka.hsr.Character | HoyolabHSRCharacter):  # pyright: ignore[reportUnnecessaryIsInstance]
        return HSR_DEFAULT_ART_URL.format(char_id=character.id)

    msg = f"Unsupported character type: {type(character)}"
    raise TypeError(msg)


def get_default_collection(
    character_id: str, card_data: dict[str, Any], *, game: Game
) -> list[str]:
    if game is Game.ZZZ:
        return []
    try:
        return card_data[character_id]["arts"]
    except KeyError:
        return []


class ImageSettingsView(View):
    def __init__(
        self,
        characters: Sequence[Character],
        selected_character_id: str,
        card_data: dict[str, Any],
        card_settings: CardSettings,
        custom_images: list[CustomImage],
        game: Game,
        settings: Settings,
        *,
        is_team: bool,
        author: User | Member,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.characters = characters
        self.user_id = author.id
        self.card_data = card_data

        self.game = game
        self.selected_character_id = selected_character_id
        self.card_settings = card_settings
        self.custom_images = custom_images
        self.settings = settings
        self.image_type: Literal["build_card_image", "team_card_image"] = (
            "team_card_image" if is_team else "build_card_image"
        )

        self._add_items()

    @property
    def template(self) -> tuple[Game, str]:
        return self.game, self.card_settings.template

    @property
    def disable_image(self) -> bool:
        if self.image_type == "team_card_image":
            return False
        if self.template not in DISABLE_IMAGE:
            logger.error(f"Template {self.template} not found in DISABLE_IMAGE")
            return True
        return DISABLE_IMAGE[self.template]

    @property
    def disable_m3_art(self) -> bool:
        if self.game is not Game.ZZZ:
            return True
        if self.image_type == "team_card_image":
            return True
        return self.card_settings.template != "hb2"

    @property
    def disable_ai(self) -> bool:
        return self.game is Game.ZZZ or self.disable_image

    def _add_items(self) -> None:
        character = self._get_current_character()
        default_collection = get_default_collection(
            str(character.id), self.card_data, game=self.game
        )
        current_image = self.get_current_image()

        self.add_item(CharacterSelect(self.characters, self.selected_character_id, row=0))
        self.add_item(ImageTypeSelect(self.image_type, row=1))
        self.add_item(
            ImageSelect(
                current_image_url=current_image,
                default_collection=default_collection,
                custom_images=self.custom_images,
                template=self.card_settings.template,
                disabled=self.disable_image,
                row=2,
            )
        )
        self.add_item(GenerateAIArtButton(disabled=self.disable_ai, row=3))
        self.add_item(AddImageButton(row=3, disabled=self.disable_image))
        self.add_item(EditImageButton(disabled=self.disable_image or current_image is None, row=3))
        self.add_item(
            RemoveImageButton(
                disabled=current_image is None or current_image in default_collection, row=3
            )
        )
        self.add_item(
            UseM3ArtButton(
                current=self.card_settings.use_m3_art, disabled=self.disable_m3_art, row=4
            )
        )

    def _get_current_character(self) -> Character:
        character = next(
            (chara for chara in self.characters if str(chara.id) == self.selected_character_id),
            None,
        )
        if character is None:
            msg = f"Character with ID {self.selected_character_id} not found"
            raise ValueError(msg)
        return character

    def get_current_image(self) -> str | None:
        if self.image_type == "build_card_image":
            return self.card_settings.current_image
        return self.card_settings.current_team_image

    async def set_current_image(self, image_url: str | None) -> None:
        if self.image_type == "build_card_image":
            self.card_settings.current_image = image_url
            await self.card_settings.save(update_fields=("current_image",))
        else:
            self.card_settings.current_team_image = image_url
            await self.card_settings.save(update_fields=("current_team_image",))

    async def refresh_custom_images(self) -> None:
        self.custom_images = await CustomImage.filter(
            user_id=self.user_id, character_id=self.selected_character_id
        ).all()

    def get_settings_embed(self) -> DefaultEmbed:
        character = self._get_current_character()
        embed = DefaultEmbed(
            locale=self.locale,
            title=LocaleStr(key="card_settings.modifying_for", name=character.name),
            description=LocaleStr(key="card_settings.description"),
        )

        image_url = self.get_current_image() or get_default_art(
            character,
            is_team=self.image_type == "team_card_image"
            or (self.card_settings.template == "hb4" and self.game is Game.ZZZ),
            use_m3_art=self.card_settings.use_m3_art,
        )
        embed.add_field(
            name=LocaleStr(key="card_settings.current_image"), value=image_url, inline=False
        )
        embed.set_image(url=image_url)
        embed.set_footer(text=LocaleStr(key="card_settings.footer"))
        return embed

    async def start(self, i: Interaction) -> None:
        embed = self.get_settings_embed()
        await i.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await i.original_response()


class CharacterSelect(SettingsCharacterSelect[ImageSettingsView]):
    async def callback(self, i: Interaction) -> Any:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        self.view.selected_character_id = self.values[0]
        self.view.card_settings = await get_card_settings(
            self.view.user_id, self.values[0], game=self.view.game
        )
        default_arts = get_default_collection(
            self.values[0], self.view.card_data, game=self.view.game
        )
        current_image = self.view.get_current_image()

        # Update other item styles
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(
            current_image=current_image,
            custom_images=self.view.custom_images,
            default_collection=default_arts,
        )

        # Disable the edit and remove image button if the image is not custom
        is_not_custom = current_image is None or current_image in default_arts
        edit_image_button: EditImageButton = self.view.get_item("profile_edit_image")
        edit_image_button.disabled = is_not_custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = is_not_custom

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


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
        current_image = self.view.get_current_image()
        if current_image is None:
            return

        # Update the current image URL
        await self.view.set_current_image(None)

        # Remove the image from the db
        await CustomImage.filter(
            user_id=i.user.id, url=current_image, character_id=self.view.selected_character_id
        ).delete()
        self.view.custom_images = [
            img for img in self.view.custom_images if img.url != current_image
        ]

        # Update image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=None, custom_images=self.view.custom_images)

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


class EditImageModal(Modal):
    name: Label[TextInput] = Label(
        text=LocaleStr(key="nickname_modal_label"),
        component=TextInput(required=False, max_length=100),
    )

    def __init__(self, current_name: str | None) -> None:
        super().__init__(title=LocaleStr(key="edit_nickname_modal_title"))
        self.name.default = current_name


class EditImageButton(Button[ImageSettingsView]):
    def __init__(self, *, disabled: bool, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="edit_nickname_modal_title"),
            custom_id="profile_edit_image",
            emoji=EDIT,
            row=row,
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        image_url = self.view.get_current_image()
        current_name = next(
            (img.name for img in self.view.custom_images if img.url == image_url), ""
        )
        modal = EditImageModal(current_name)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        # Add the image URL to db
        await CustomImage.filter(user_id=i.user.id, url=image_url).update(
            name=modal.name.value or None
        )
        await self.view.refresh_custom_images()

        # Update image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=image_url, custom_images=self.view.custom_images)

        embed = self.view.get_settings_embed()
        await i.edit_original_response(embed=embed, view=self.view)


class ImageSelect(PaginatorSelect[ImageSettingsView]):
    def __init__(
        self,
        current_image_url: str | None,
        default_collection: list[str],
        custom_images: list[CustomImage],
        template: str,
        *,
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
        custom_images: list[CustomImage],
        default_collection: list[str] | None = None,
    ) -> None:
        self.current_image_url = current_image
        self.custom_images = custom_images
        self.default_collection = default_collection or self.default_collection

        self.options_before_split = self.get_options()
        self.options = self.process_options()
        if current_image is not None:
            self.set_page_based_on_value(current_image)
        self.translate(self.view.locale)

    def _get_select_option(self, image: str | CustomImage, num: int) -> SelectOption:
        image_url = image.url if isinstance(image, CustomImage) else image

        if image_url in self.default_collection:
            label = LocaleStr(key="profile.image_select.default_collection.label", num=num)
        elif isinstance(image, CustomImage) and image.name:
            label = image.name
        else:
            label = LocaleStr(key="profile.image_select.custom_image.label", num=num)

        return SelectOption(
            label=label, value=image_url, default=image_url == self.current_image_url
        )

    def get_options(self) -> list[SelectOption]:
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr(key="profile.image_select.none.label"),
                value="none",
                default=self.current_image_url is None,
            )  # Official art option
        ]
        added_values: set[str] = set()

        for collection in (self.default_collection, self.custom_images):
            num = 1
            for image in collection:
                if image not in added_values:
                    options.append(self._get_select_option(image, num))
                    added_values.add(image.url if isinstance(image, CustomImage) else image)

                    if isinstance(image, str) or not image.name:
                        num += 1

        return options

    async def callback(self, i: Interaction) -> Any:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()

        # Update the current image URL in db
        await self.view.set_current_image(self.values[0] if self.values[0] != "none" else None)

        # Disable the edit and remove image button if the image is not custom
        is_not_custom = self.values[0] in self.default_collection or self.values[0] == "none"
        edit_image_button: EditImageButton = self.view.get_item("profile_edit_image")
        edit_image_button.disabled = is_not_custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = is_not_custom

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


class GenerateAIArtModal(Modal):
    prompt: Label[TextInput] = Label(
        text=LocaleStr(key="profile.generate_ai_art_modal.prompt.label"),
        component=TextInput(
            placeholder="navia(genshin impact), foaml dress, idol, beautiful dress, elegant, best quality, aesthetic...",
            style=TextStyle.paragraph,
            max_length=250,
        ),
    )

    negative_prompt: Label[TextInput] = Label(
        text=LocaleStr(key="profile.generate_ai_art_modal.negative_prompt.label"),
        component=TextInput(
            placeholder="bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs...",
            style=TextStyle.paragraph,
            max_length=200,
            required=False,
        ),
    )


class GenerateAIArtButton(Button[ImageSettingsView]):
    def __init__(self, *, disabled: bool, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.generate_ai_art.button.label"),
            style=ButtonStyle.blurple,
            custom_id="profile_generate_ai_art",
            disabled=disabled,
            row=row,
            emoji=PHOTO_ADD,
        )

    async def callback(self, i: Interaction) -> None:
        modal = GenerateAIArtModal(title=LocaleStr(key="profile.generate_ai_art.button.label"))
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        prompt = modal.prompt.value
        negative_prompt = modal.negative_prompt.value
        nsfw_tags: list[str] = await read_json("hoyo_buddy/bot/data/nsfw_tags.json")
        if any(tag.lower() in prompt.lower() for tag in nsfw_tags):
            raise NSFWPromptError

        await self.set_loading_state(i)

        client = i.client.nai_client
        if client is None:
            msg = "NAI client is not initialized. Please check your configuration."
            raise ValueError(msg)

        bytes_ = await client.generate_image(prompt, negative_prompt)
        url = await upload_image(i.client.session, image=bytes_)

        # Add the image URL to db
        await CustomImage.create(
            user_id=i.user.id, character_id=self.view.selected_character_id, url=url
        )
        await self.view.refresh_custom_images()
        await self.view.set_current_image(url)

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=url, custom_images=self.view.custom_images)

        # Enable the edit and remove image button
        edit_img_btn: EditImageButton = self.view.get_item("profile_edit_image")
        edit_img_btn.disabled = False
        remove_img_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_img_btn.disabled = False

        embed = self.view.get_settings_embed()
        await self.unset_loading_state(i, embed=embed)


class AddImageModal(Modal):
    name: Label[TextInput] = Label(
        text=LocaleStr(key="nickname_modal_label"),
        component=TextInput(required=False, max_length=100),
    )
    image_url: Label[TextInput] = Label(
        text=LocaleStr(key="profile.add_image_modal.image_url.label"),
        component=TextInput(placeholder="https://example.com/image.png"),
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="profile.add_image.button.label"))


class AddImageButton(Button[ImageSettingsView]):
    def __init__(self, row: int, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.add_image.button.label"),
            style=ButtonStyle.green,
            emoji=ADD,
            row=row,
            disabled=disabled,
            custom_id="profile_add_image",
        )

    async def callback(self, i: Interaction) -> None:
        # Open the modal
        modal = AddImageModal()
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        await self.set_loading_state(i)

        image_url = modal.image_url.value
        image_url = image_url.strip()

        # Pixiv image support
        if "i.pximg.net" in image_url:
            image_url = await get_pixiv_proxy_img(i.client.session, image_url)

        # Check if the image URL is valid
        passed = is_image_url(image_url)
        if not passed:
            raise InvalidImageURLError
        passed = await test_url_validity(image_url, i.client.session)
        if not passed:
            raise InvalidImageURLError

        if not image_url.startswith("https://img.seria.moe/"):
            try:
                image_url = await upload_image(i.client.session, image_url=image_url)
            except Exception as e:
                raise InvalidImageURLError from e

        # Add the image URL to db
        await CustomImage.create(
            user_id=i.user.id,
            character_id=self.view.selected_character_id,
            url=image_url,
            name=modal.name.value or None,
        )
        await self.view.refresh_custom_images()
        await self.view.set_current_image(image_url)

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=image_url, custom_images=self.view.custom_images)

        # Enable the edit image and remove image buttons
        self.view.item_states["profile_edit_image"] = False
        self.view.item_states["profile_remove_image"] = False

        embed = self.view.get_settings_embed()
        await self.unset_loading_state(i, embed=embed)


class ImageTypeSelect(Select[ImageSettingsView]):
    def __init__(
        self, current: Literal["build_card_image", "team_card_image"], *, row: int
    ) -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=LocaleStr(key="card_settings.build_card_image"),
                    value="build_card_image",
                    default=current == "build_card_image",
                ),
                SelectOption(
                    label=LocaleStr(key="card_settings.team_card_image"),
                    value="team_card_image",
                    default=current == "team_card_image",
                ),
            ],
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        self.view.image_type = self.values[0]  # pyright: ignore[reportAttributeAccessIssue]
        embed = self.view.get_settings_embed()
        self.update_options_defaults()

        image_select: ImageSelect = self.view.get_item("profile_image_select")
        current_image = self.view.get_current_image()
        default_collection = get_default_collection(
            self.view.selected_character_id, self.view.card_data, game=self.view.game
        )
        image_select.update(
            current_image=current_image,
            custom_images=self.view.custom_images,
            default_collection=default_collection,
        )
        image_select.disabled = self.view.disable_image

        add_image_btn: AddImageButton = self.view.get_item("profile_add_image")
        add_image_btn.disabled = self.view.disable_image

        use_m3_art_btn: UseM3ArtButton = self.view.get_item("profile_use_m3_art")
        use_m3_art_btn.disabled = self.view.disable_m3_art

        # Disable the edit and remove image button if the image is not custom
        is_not_custom = current_image is None or current_image in default_collection
        edit_image_btn: EditImageButton = self.view.get_item("profile_edit_image")
        edit_image_btn.disabled = is_not_custom
        remove_image_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_btn.disabled = is_not_custom

        await i.response.edit_message(embed=embed, view=self.view)


class UseM3ArtButton(ToggleButton[ImageSettingsView]):
    def __init__(self, row: int, *, current: bool, disabled: bool) -> None:
        super().__init__(
            toggle_label=LocaleStr(key="image_settings_use_m3_art"),
            current_toggle=current,
            row=row,
            disabled=disabled,
            custom_id="profile_use_m3_art",
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=False)
        self.view.card_settings.use_m3_art = not self.view.card_settings.use_m3_art
        await self.view.card_settings.save(update_fields=("use_m3_art",))

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
