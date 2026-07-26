from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, cast

import discord
from loguru import logger
from seria.utils import read_json

from hoyo_buddy import ui
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import EMPTY_CHAR
from hoyo_buddy.db import CustomImage
from hoyo_buddy.db.utils import get_default_color
from hoyo_buddy.emojis import ADD, DELETE, EDIT, PHOTO_ADD
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import InvalidImageURLError, NSFWPromptError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.hoyo.profile.image_settings import get_default_collection
from hoyo_buddy.ui.hoyo.profile.templates import DISABLE_IMAGE, TEMPLATE_NAMES
from hoyo_buddy.utils import is_image_url, test_url_validity, upload_image
from hoyo_buddy.utils.gacha import get_gacha_icon
from hoyo_buddy.utils.misc import get_template_name, get_template_num

from .card import CardTemplateSelect

if TYPE_CHECKING:
    from hoyo_buddy.db.models import CardSettings
    from hoyo_buddy.types import Interaction

    from .view import CardSettingsView  # ruff:ignore[unused-import]

type ImageType = Literal["build_card_image", "team_card_image"]


class ImageTypeSelect(ui.Select["CardSettingsView"]):
    def __init__(self, current: ImageType) -> None:
        super().__init__(
            options=[
                ui.SelectOption(
                    label=LocaleStr(key="card_settings.build_card_image"),
                    value="build_card_image",
                    default=current == "build_card_image",
                ),
                ui.SelectOption(
                    label=LocaleStr(key="card_settings.team_card_image"),
                    value="team_card_image",
                    default=current == "team_card_image",
                ),
            ],
            custom_id="image_settings_image_type",
        )

    async def callback(self, i: Interaction) -> None:
        self.view.image_type = cast("ImageType", self.values[0])
        await self.view.update(i)


class ImageSelect(ui.PaginatorSelect["CardSettingsView"]):
    def __init__(
        self,
        *,
        current_image: str | None,
        default_collection: list[str],
        custom_images: list[CustomImage],
        disabled: bool,
    ) -> None:
        self.current_image = current_image
        self.default_collection = default_collection
        self.custom_images = custom_images

        super().__init__(
            self.get_options(),
            placeholder=LocaleStr(key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
            disabled=disabled,
        )
        if current_image is not None:
            self.set_page_based_on_value(current_image)
            self.options = self.process_options()

    def _get_select_option(self, image: str | CustomImage, num: int) -> ui.SelectOption:
        image_url = image.url if isinstance(image, CustomImage) else image

        if image_url in self.default_collection:
            label = LocaleStr(key="profile.image_select.default_collection.label", num=num)
        elif isinstance(image, CustomImage) and image.name:
            label = image.name
        else:
            label = LocaleStr(key="profile.image_select.custom_image.label", num=num)

        return ui.SelectOption(
            label=label, value=image_url, default=image_url == self.current_image
        )

    def get_options(self) -> list[ui.SelectOption]:
        options: list[ui.SelectOption] = [
            ui.SelectOption(
                label=LocaleStr(key="profile.image_select.none.label"),
                value="none",
                default=self.current_image is None,
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

        await self.view.set_current_image(self.values[0] if self.values[0] != "none" else None)
        await self.view.update(i)
        return None


class AddImageModal(ui.Modal):
    name: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="nickname_modal_label"),
        component=ui.TextInput(required=False, max_length=100),
    )
    image_url: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="profile.add_image_modal.image_url.label"),
        component=ui.TextInput(placeholder="https://example.com/image.png"),
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="profile.add_image.button.label"))


class AddImageButton(ui.Button["CardSettingsView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.add_image.button.label"),
            style=discord.ButtonStyle.green,
            emoji=ADD,
            disabled=disabled,
            custom_id="profile_add_image",
        )

    async def callback(self, i: Interaction) -> None:
        modal = AddImageModal()
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        await self.set_loading_state(i)

        image_url = modal.image_url.value.strip()

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

        await CustomImage.create(
            user_id=i.user.id,
            character_id=self.view.card_settings.character_id,
            url=image_url,
            name=modal.name.value or None,
        )
        await self.view.set_current_image(image_url)
        await self.view.update(i)


class GenerateAIArtModal(ui.Modal):
    prompt: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="profile.generate_ai_art_modal.prompt.label"),
        component=ui.TextInput(
            placeholder="navia(genshin impact), foaml dress, idol, beautiful dress, elegant, best quality, aesthetic...",
            style=discord.TextStyle.paragraph,
            max_length=250,
        ),
    )

    negative_prompt: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="profile.generate_ai_art_modal.negative_prompt.label"),
        component=ui.TextInput(
            placeholder="bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs...",
            style=discord.TextStyle.paragraph,
            max_length=200,
            required=False,
        ),
    )


class GenerateAIArtButton(ui.Button["CardSettingsView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.generate_ai_art.button.label"),
            style=discord.ButtonStyle.blurple,
            custom_id="profile_generate_ai_art",
            disabled=disabled,
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

        await CustomImage.create(
            user_id=i.user.id, character_id=self.view.card_settings.character_id, url=url
        )
        await self.view.set_current_image(url)
        await self.view.update(i)


class EditImageModal(ui.Modal):
    name: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="nickname_modal_label"),
        component=ui.TextInput(required=False, max_length=100),
    )

    def __init__(self, current_name: str | None) -> None:
        super().__init__(title=LocaleStr(key="edit_nickname_modal_title"))
        self.name.default = current_name


class EditImageButton(ui.Button["CardSettingsView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="edit_nickname_modal_title"),
            custom_id="profile_edit_image",
            emoji=EDIT,
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        image_url = self.view.current_image
        current_name = next(
            (img.name for img in self.view.custom_images if img.url == image_url), ""
        )
        modal = EditImageModal(current_name)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        await CustomImage.filter(user_id=i.user.id, url=image_url).update(
            name=modal.name.value or None
        )
        await self.view.update(i)


class RemoveImageButton(ui.Button["CardSettingsView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.remove_image.button.label"),
            style=discord.ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
        )

    async def callback(self, i: Interaction) -> None:
        current_image = self.view.current_image
        if current_image is None:
            return

        await self.view.set_current_image(None)
        await CustomImage.filter(
            user_id=i.user.id, url=current_image, character_id=self.view.card_settings.character_id
        ).delete()

        await self.view.update(i)


class UseM3ArtButton(ui.EmojiToggleButton["CardSettingsView"]):
    def __init__(self, *, current: bool, disabled: bool) -> None:
        super().__init__(current=current, disabled=disabled, custom_id="profile_use_m3_art")

    async def callback(self, i: Interaction) -> None:
        self.view.card_settings.use_m3_art = not self.view.card_settings.use_m3_art
        await self.view.card_settings.save(update_fields=("use_m3_art",))

        await self.view.update(i)


class ImageSettingsContainer(ui.Container):
    def __init__(
        self,
        *,
        card_settings: CardSettings,
        character_name: str,
        game: Game,
        gacha_data: dict[str, dict[str, str]],
        custom_images: list[CustomImage],
        image_type: ImageType,
        default_art: str | None,
    ) -> None:
        self.card_settings = card_settings
        self.game = game
        self.template = (game, card_settings.template)
        self.image_type = image_type

        current_image = (
            card_settings.current_image
            if image_type == "build_card_image"
            else card_settings.current_team_image
        )
        default_collection = get_default_collection(card_settings.character_id, game=game)
        is_custom = current_image is not None and current_image not in default_collection
        preview_url = current_image or default_art
        icon_url = get_gacha_icon(item_id=int(card_settings.character_id), gacha_data=gacha_data)

        default_color = get_default_color(
            card_settings.character_id,
            game=game,
            template=card_settings.template,
            dark_mode=card_settings.dark_mode,
            outfit_id=None,
        )

        preview: list[discord.ui.MediaGallery] = (
            [discord.ui.MediaGallery(discord.MediaGalleryItem(preview_url))] if preview_url else []
        )

        m3_art: list[ui.Section] = []
        if game is Game.ZZZ:
            m3_art.append(
                ui.Section(
                    ui.TextDisplay(
                        LocaleStr(
                            custom_str="### {title}\n{desc}\n{empty}",
                            title=LocaleStr(key="image_settings_use_m3_art"),
                            desc=LocaleStr(key="image_settings_use_m3_art_desc"),
                            empty=EMPTY_CHAR,
                        )
                    ),
                    accessory=UseM3ArtButton(
                        current=card_settings.use_m3_art, disabled=self.disable_m3_art
                    ),
                )
            )

        super().__init__(
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="# {title}\n{desc}",
                        title=LocaleStr(key="image_settings_modifying_for", name=character_name),
                        desc=LocaleStr(key="image_settings_modifying_for_desc"),
                    )
                ),
                accessory=discord.ui.Thumbnail(media=icon_url),
            ),
            # Template
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}\n{desc}",
                    title=LocaleStr(key="card_settings.template"),
                    desc=self.template_status,
                )
            ),
            ui.ActionRow(CardTemplateSelect(current_template=card_settings.template, game=game)),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Current image
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}\n{desc}",
                    title=LocaleStr(key="card_settings.current_image"),
                    desc=LocaleStr(key="card_settings.description"),
                )
            ),
            ui.ActionRow(ImageTypeSelect(image_type)),
            *preview,
            ui.ActionRow(
                ImageSelect(
                    current_image=current_image,
                    default_collection=default_collection,
                    custom_images=custom_images,
                    disabled=self.disable_image,
                )
            ),
            ui.ActionRow(
                AddImageButton(disabled=self.disable_image),
                GenerateAIArtButton(disabled=self.disable_ai),
                EditImageButton(disabled=self.disable_image or not is_custom),
                RemoveImageButton(disabled=not is_custom),
            ),
            *m3_art,
            accent_color=card_settings.custom_primary_color or default_color,
        )

    @property
    def template_status(self) -> LocaleStr:
        template_name = LocaleStr(
            key=TEMPLATE_NAMES[get_template_name(self.card_settings.template)],
            num=get_template_num(self.card_settings.template),
        )
        if self.image_type == "team_card_image":
            return LocaleStr(key="image_settings_team_image_note")
        if self.disable_image:
            return LocaleStr(
                key="image_settings_template_not_supported",
                template=template_name,
                supported_label=LocaleStr(key="is_support_custom_image_desc"),
            )
        return LocaleStr(key="image_settings_template_supported", template=template_name)

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
        if self.game is not Game.ZZZ or self.image_type == "team_card_image":
            return True
        return self.card_settings.template != "hb2"

    @property
    def disable_ai(self) -> bool:
        return not CONFIG.novelai or self.game is Game.ZZZ or self.disable_image
