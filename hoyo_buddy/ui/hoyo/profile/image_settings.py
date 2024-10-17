from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import enka
from discord import ButtonStyle, TextStyle
from genshin.models import ZZZFullAgent, ZZZPartialAgent
from seria.utils import read_json

from hoyo_buddy.constants import HSR_DEFAULT_ART_URL, ZZZ_DEFAULT_ART_URL
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD, DELETE, PHOTO_ADD
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import InvalidImageURLError, NSFWPromptError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import HoyolabGICharacter
from hoyo_buddy.ui import Button, Modal, PaginatorSelect, SelectOption, TextInput, View
from hoyo_buddy.ui.components import Select
from hoyo_buddy.utils import get_pixiv_proxy_img, is_image_url, test_url_validity, upload_image

from .btn_states import DISABLE_IMAGE, ZZZ_DISABLE_IMAGE
from .card_settings import get_card_settings
from .items.settings_chara_select import CharacterSelect as SettingsCharacterSelect

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale, Member, User

    from hoyo_buddy.db.models import CardSettings, Settings
    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction

    from .view import Character


async def get_team_image(user_id: int, character_id: str, *, game: Game) -> str | None:
    card_settings = await get_card_settings(user_id, character_id, game=game)
    return card_settings.current_team_image


def get_default_art(character: Character | ZZZFullAgent, *, is_team: bool) -> str:
    if isinstance(character, ZZZPartialAgent | ZZZFullAgent):
        if is_team:
            return character.banner_icon
        return ZZZ_DEFAULT_ART_URL.format(char_id=character.id)
    if isinstance(character, enka.gi.Character):
        if character.costume is not None:
            return character.costume.icon.gacha
        return character.icon.gacha
    if isinstance(character, HoyolabGICharacter):
        return character.icon.gacha
    return HSR_DEFAULT_ART_URL.format(char_id=character.id)


def get_default_collection(character_id: str, card_data: dict[str, Any], *, game: Game) -> list[str]:
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
        game: Game,
        is_team: bool,
        settings: Settings,
        *,
        author: User | Member,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.characters = characters
        self.user_id = author.id
        self.card_data = card_data
        self.is_team = is_team

        self.game = game
        self.selected_character_id = selected_character_id
        self.card_settings = card_settings
        self.settings = settings
        self.image_type: Literal["build_card_image", "team_card_image"] = (
            "team_card_image" if is_team else "build_card_image"
        )

        self._add_items()

    @property
    def disable_image_features(self) -> bool:
        return self.card_settings.template in DISABLE_IMAGE or (
            self.image_type == "build_card_image"
            and self.game is Game.ZZZ
            and self.card_settings.template in ZZZ_DISABLE_IMAGE
        )

    @property
    def disable_ai_features(self) -> bool:
        return self.game is Game.ZZZ or self.card_settings.template in DISABLE_IMAGE

    def _add_items(self) -> None:
        character = self._get_current_character()
        default_collection = get_default_collection(str(character.id), self.card_data, game=self.game)

        self.add_item(CharacterSelect(self.characters, self.selected_character_id, row=0))
        self.add_item(ImageTypeSelect(self.image_type, row=1))
        self.add_item(
            ImageSelect(
                current_image_url=self.card_settings.current_image,
                default_collection=default_collection,
                custom_images=self.card_settings.custom_images,
                template=self.card_settings.template,
                disabled=self.disable_image_features,
                row=2,
            )
        )
        self.add_item(GenerateAIArtButton(disabled=self.disable_ai_features, row=3))
        self.add_item(AddImageButton(row=3, disabled=self.disable_image_features))
        self.add_item(
            RemoveImageButton(
                disabled=self.card_settings.current_image is None
                or self.card_settings.current_image in default_collection,
                row=3,
            )
        )

    def _get_current_character(self) -> Character:
        return next(chara for chara in self.characters if str(chara.id) == self.selected_character_id)

    def get_current_image(self) -> str | None:
        if self.image_type == "build_card_image":
            return self.card_settings.current_image
        return self.card_settings.current_team_image

    def set_current_image(self, image_url: str | None) -> None:
        if self.image_type == "build_card_image":
            self.card_settings.current_image = image_url
        else:
            self.card_settings.current_team_image = image_url

    def get_settings_embed(self) -> DefaultEmbed:
        character = self._get_current_character()
        embed = DefaultEmbed(
            locale=self.locale,
            translator=self.translator,
            title=LocaleStr(key="card_settings.modifying_for", name=character.name),
        )

        image_url = self.get_current_image() or get_default_art(character, is_team=self.image_type == "team_card_image")
        embed.add_field(name=LocaleStr(key="card_settings.current_image"), value=image_url, inline=False)
        embed.set_image(url=image_url)
        embed.set_footer(text=LocaleStr(key="card_settings.footer"))
        return embed

    async def start(self, i: Interaction) -> None:
        embed = self.get_settings_embed()
        await i.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await i.original_response()


class CharacterSelect(SettingsCharacterSelect[ImageSettingsView]):
    async def callback(self, i: Interaction) -> None:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        self.view.selected_character_id = self.values[0]
        self.view.card_settings = await get_card_settings(self.view.user_id, self.values[0], game=self.view.game)
        default_arts = get_default_collection(self.values[0], self.view.card_data, game=self.view.game)
        custom_arts = self.view.card_settings.custom_images
        current_image = self.view.get_current_image()

        # Update other item styles
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=current_image, custom_images=custom_arts, default_collection=default_arts)

        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = current_image is None or current_image in default_arts

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


class RemoveImageButton(Button[ImageSettingsView]):
    def __init__(self, disabled: bool, row: int) -> None:
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

        if current_image in self.view.card_settings.custom_images:
            # For whatever reason, the current image may not be in the custom images list
            self.view.card_settings.custom_images.remove(current_image)

        # Update the current image URL
        self.view.set_current_image(None)
        self.view.card_settings.custom_images = list(set(self.view.card_settings.custom_images))
        await self.view.card_settings.save(update_fields=("custom_images", "current_image", "current_team_image"))

        # Update image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=None, custom_images=self.view.card_settings.custom_images)

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


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
        self, *, current_image: str | None, custom_images: list[str], default_collection: list[str] | None = None
    ) -> None:
        self.current_image_url = current_image
        self.custom_images = custom_images
        self.default_collection = default_collection or self.default_collection

        self.options_before_split = self.get_options()
        self.options = self.process_options()
        if current_image is not None:
            self.set_page_based_on_value(current_image)
        self.translate(self.view.locale, self.view.translator)

    def _get_select_option(self, image_url: str, num: int) -> SelectOption:
        label = (
            LocaleStr(key="profile.image_select.default_collection.label", num=num)
            if image_url in self.default_collection
            else LocaleStr(key="profile.image_select.custom_image.label", num=num)
        )
        return SelectOption(label=label, value=image_url, default=image_url == self.current_image_url)

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

    async def callback(self, i: Interaction) -> None:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()

        # Update the current image URL in db
        self.view.set_current_image(self.values[0] if self.values[0] != "none" else None)
        await self.view.card_settings.save(update_fields=("current_image", "current_team_image"))

        # Enable the remove image button if the image is custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = self.values[0] in self.default_collection or self.values[0] == "none"

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


class GenerateAIArtModal(Modal):
    prompt = TextInput(
        label=LocaleStr(key="profile.generate_ai_art_modal.prompt.label"),
        placeholder="navia(genshin impact), foaml dress, idol, beautiful dress, elegant, best quality, aesthetic...",
        style=TextStyle.paragraph,
        max_length=250,
    )

    negative_prompt = TextInput(
        label=LocaleStr(key="profile.generate_ai_art_modal.negative_prompt.label"),
        placeholder="bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs...",
        style=TextStyle.paragraph,
        max_length=200,
        required=False,
    )


class GenerateAIArtButton(Button[ImageSettingsView]):
    def __init__(self, disabled: bool, row: int) -> None:
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
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        prompt = modal.prompt.value
        negative_prompt = modal.negative_prompt.value
        nsfw_tags: list[str] = await read_json("hoyo_buddy/bot/data/nsfw_tags.json")
        if any(tag.lower() in prompt.lower() for tag in nsfw_tags):
            raise NSFWPromptError

        await self.set_loading_state(i)

        try:
            client = i.client.nai_client
            bytes_ = await client.generate_image(prompt, negative_prompt)
            url = await upload_image(i.client.session, image=bytes_)
        except Exception:
            await self.unset_loading_state(i)
            raise

        # Add the image URL to db
        self.view.card_settings.custom_images.append(url)
        self.view.set_current_image(url)
        await self.view.card_settings.save(update_fields=("custom_images", "current_image", "current_team_image"))

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=url, custom_images=self.view.card_settings.custom_images)

        # Enable the remove image button
        remove_img_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_img_btn.disabled = False

        embed = self.view.get_settings_embed()
        await self.unset_loading_state(i, embed=embed)


class AddImageModal(Modal):
    image_url = TextInput(
        label=LocaleStr(key="profile.add_image_modal.image_url.label"),
        placeholder="https://example.com/image.png",
        style=TextStyle.short,
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="profile.add_image.button.label"))


class AddImageButton(Button[ImageSettingsView]):
    def __init__(self, row: int, disabled: bool) -> None:
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
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
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
            await self.unset_loading_state(i)
            raise InvalidImageURLError
        passed = await test_url_validity(image_url, i.client.session)
        if not passed:
            await self.unset_loading_state(i)
            raise InvalidImageURLError

        if not image_url.startswith("https://iili.io"):
            # Upload the image to iili
            try:
                image_url = await upload_image(i.client.session, image_url=image_url)
            except Exception as e:
                await self.unset_loading_state(i)
                raise InvalidImageURLError from e

        # Add the image URL to db
        self.view.card_settings.custom_images.append(image_url)
        self.view.card_settings.custom_images = list(set(self.view.card_settings.custom_images))
        self.view.set_current_image(image_url)
        await self.view.card_settings.save(update_fields=("custom_images", "current_image", "current_team_image"))

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=image_url, custom_images=self.view.card_settings.custom_images)

        # Enable the remove image button
        self.view._item_states["profile_remove_image"] = False

        embed = self.view.get_settings_embed()
        await self.unset_loading_state(i, embed=embed)


class ImageTypeSelect(Select[ImageSettingsView]):
    def __init__(self, current: Literal["build_card_image", "team_card_image"], *, row: int) -> None:
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
            custom_images=self.view.card_settings.custom_images,
            default_collection=default_collection,
        )
        image_select.disabled = self.view.disable_image_features

        add_image_btn: AddImageButton = self.view.get_item("profile_add_image")
        add_image_btn.disabled = self.view.disable_image_features

        remove_image_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_btn.disabled = current_image is None or current_image in default_collection

        await i.response.edit_message(embed=embed, view=self.view)
