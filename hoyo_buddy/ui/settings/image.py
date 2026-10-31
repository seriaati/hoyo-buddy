from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal, cast

import aiohttp
import discord
from loguru import logger
from seria.utils import read_json
from tortoise.expressions import F

from hoyo_buddy import ui
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import (
    ANIMATED_CUSTOM_IMAGE_MAX_SIZE_MB,
    ANIMATED_IMAGE_EXTENSIONS,
    CUSTOM_IMAGE_MAX_SIZE_MB,
    FREE_AI_IMAGE_DAILY_LIMIT,
    FREE_CUSTOM_IMAGE_LIMIT,
    IMAGE_EXTENSIONS,
    MAYBE_ANIMATED_IMAGE_EXTENSIONS,
)
from hoyo_buddy.db import CustomImage, User
from hoyo_buddy.db.utils import get_default_color, is_supporter
from hoyo_buddy.draw.animation import convert_animation, is_animated
from hoyo_buddy.emojis import ADD, DELETE, EDIT, PHOTO, PHOTO_ADD
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import (
    AIImageLimitError,
    CustomImageLimitError,
    ImageFileTooLargeError,
    InvalidImageURLError,
    InvalidInputError,
    NotAnImageError,
    NSFWPromptError,
    SponsorPerkError,
)
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.hoyo.profile.image_settings import get_default_collection
from hoyo_buddy.ui.hoyo.profile.templates import DISABLE_IMAGE
from hoyo_buddy.utils import get_now, is_image_url, test_url_validity, upload_image
from hoyo_buddy.utils.gacha import get_gacha_icon

from .card import CardTemplateSelect

if TYPE_CHECKING:
    from hoyo_buddy.db.models import CardSettings
    from hoyo_buddy.types import Interaction

    from .view import CardSettingsView  # ruff:ignore[unused-import]

type ImageType = Literal["build_card_image", "team_card_image"]

ANIMATION_MIN_ZOOM = 10
ANIMATION_MAX_ZOOM = 400


async def check_custom_image_limit(user_id: int, character_id: str) -> None:
    if await is_supporter(user_id):
        return
    count = await CustomImage.filter(user_id=user_id, character_id=character_id).count()
    if count >= FREE_CUSTOM_IMAGE_LIMIT:
        raise CustomImageLimitError(FREE_CUSTOM_IMAGE_LIMIT)


async def check_ai_image_limit(user_id: int) -> None:
    if await is_supporter(user_id):
        return
    now = get_now()
    user = await User.get(id=user_id)
    if user.ai_image_date == now.date() and user.ai_image_count >= FREE_AI_IMAGE_DAILY_LIMIT:
        reset_time = datetime.datetime.combine(
            now.date() + datetime.timedelta(days=1), datetime.time(), tzinfo=now.tzinfo
        )
        raise AIImageLimitError(FREE_AI_IMAGE_DAILY_LIMIT, reset_time)


async def increment_ai_image_count(user_id: int) -> None:
    today = get_now().date()
    updated = await User.filter(id=user_id, ai_image_date=today).update(
        ai_image_count=F("ai_image_count") + 1
    )
    if not updated:
        await User.filter(id=user_id).update(ai_image_date=today, ai_image_count=1)


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
    ) -> None:
        self.current_image = current_image
        self.default_collection = default_collection
        self.custom_images = custom_images

        super().__init__(
            self.get_options(),
            placeholder=LocaleStr(key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
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
    image_file: ui.Label[ui.FileUpload] = ui.Label(
        text=LocaleStr(key="profile.add_image_modal.image_file.label"),
        description=LocaleStr(key="profile.add_image_modal.image_file.description"),
        component=ui.FileUpload(file_types=["image", "video"], required=False),
    )
    image_url: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="profile.add_image_modal.image_url.label"),
        description=LocaleStr(key="profile.add_image_modal.image_url.description"),
        component=ui.TextInput(placeholder="https://example.com/image.png", required=False),
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="profile.add_image.button.label"))


class AddImageButton(ui.Button["CardSettingsView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="profile.add_image.button.label"),
            style=discord.ButtonStyle.green,
            emoji=ADD,
            custom_id="profile_add_image",
        )

    async def callback(self, i: Interaction) -> None:
        await check_custom_image_limit(i.user.id, self.view.card_settings.character_id)

        modal = AddImageModal()
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        files = modal.image_file.component.values
        image_url = modal.image_url.value.strip()
        if not files and not image_url:
            raise InvalidInputError(LocaleStr(key="profile.add_image_modal.no_image"))

        await self.set_loading_state(i)

        if files:
            image_url, animated = await self._upload_file(i, files[0])
        else:
            image_url, animated = await self._upload_url(i, image_url)

        await CustomImage.create(
            user_id=i.user.id,
            character_id=self.view.card_settings.character_id,
            url=image_url,
            name=modal.name.value or None,
            animated=animated,
        )
        await self.view.set_current_image(image_url)
        await self.view.update(i)

    @staticmethod
    async def _upload_animation(i: Interaction, data: bytes) -> str | None:
        """Convert an animated upload to an animated WEBP and upload it, a sponsor perk.

        Returns:
            The animated WEBP's URL, or None if the upload isn't animated.
        """
        if not is_animated(data):
            return None
        if not await is_supporter(i.user.id):
            raise SponsorPerkError(
                message=LocaleStr(key="animated_custom_image_sponsor_perk_message")
            )

        try:
            webp = await i.client.loop.run_in_executor(i.client.executor, convert_animation, data)
        except (ValueError, OSError) as e:
            raise NotAnImageError from e
        return await upload_image(i.client.session, image=webp)

    async def _upload_file(self, i: Interaction, file: discord.Attachment) -> tuple[str, bool]:
        """Upload an image file.

        Returns:
            The image's URL and whether it's animated.
        """
        filename = file.filename.lower()
        if not filename.endswith((*IMAGE_EXTENSIONS, *ANIMATED_IMAGE_EXTENSIONS)):
            raise NotAnImageError

        if filename.endswith(MAYBE_ANIMATED_IMAGE_EXTENSIONS):
            if file.size > ANIMATED_CUSTOM_IMAGE_MAX_SIZE_MB * 1024 * 1024:
                raise ImageFileTooLargeError(ANIMATED_CUSTOM_IMAGE_MAX_SIZE_MB)
            url = await self._upload_animation(i, await file.read())
            if url is not None:
                return url, True

        if file.size > CUSTOM_IMAGE_MAX_SIZE_MB * 1024 * 1024:
            raise ImageFileTooLargeError(CUSTOM_IMAGE_MAX_SIZE_MB)
        return await upload_image(i.client.session, image_url=file.url), False

    async def _upload_url(self, i: Interaction, image_url: str) -> tuple[str, bool]:
        """Upload an image from its URL.

        Returns:
            The image's URL and whether it's animated.
        """
        if not is_image_url(image_url):
            raise InvalidImageURLError

        if image_url.lower().endswith(MAYBE_ANIMATED_IMAGE_EXTENSIONS):
            url = await self._upload_animation(i, await self._download(i, image_url))
            if url is not None:
                return url, True
        return await self._upload_image_url(i, image_url), False

    @staticmethod
    async def _download(i: Interaction, url: str) -> bytes:
        max_size = ANIMATED_CUSTOM_IMAGE_MAX_SIZE_MB * 1024 * 1024
        data = bytearray()
        try:
            async with i.client.session.get(url) as resp:
                if resp.status != 200:
                    raise InvalidImageURLError
                async for chunk in resp.content.iter_chunked(1024 * 1024):
                    data.extend(chunk)
                    if len(data) > max_size:
                        raise ImageFileTooLargeError(ANIMATED_CUSTOM_IMAGE_MAX_SIZE_MB)
        except aiohttp.ClientError as e:
            raise InvalidImageURLError from e
        return bytes(data)

    @staticmethod
    async def _upload_image_url(i: Interaction, image_url: str) -> str:
        if not is_image_url(image_url):
            raise InvalidImageURLError
        if not await test_url_validity(image_url, i.client.session):
            raise InvalidImageURLError

        if image_url.startswith("https://img.seria.moe/"):
            return image_url
        try:
            return await upload_image(i.client.session, image_url=image_url)
        except Exception as e:
            raise InvalidImageURLError from e


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
        await check_custom_image_limit(i.user.id, self.view.card_settings.character_id)
        await check_ai_image_limit(i.user.id)

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
        await increment_ai_image_count(i.user.id)
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


class AnimationPositionModal(ui.Modal):
    zoom: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="animation_position_modal.zoom.label"),
        description=LocaleStr(key="animation_position_modal.zoom.description"),
        component=ui.TextInput(
            is_digit=True, min_value=ANIMATION_MIN_ZOOM, max_value=ANIMATION_MAX_ZOOM, max_length=3
        ),
    )
    focus_x: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="animation_position_modal.focus_x.label"),
        description=LocaleStr(key="animation_position_modal.focus_x.description"),
        component=ui.TextInput(is_digit=True, min_value=0, max_value=100, max_length=3),
    )
    focus_y: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="animation_position_modal.focus_y.label"),
        description=LocaleStr(key="animation_position_modal.focus_y.description"),
        component=ui.TextInput(is_digit=True, min_value=0, max_value=100, max_length=3),
    )

    def __init__(self, image: CustomImage) -> None:
        super().__init__(title=LocaleStr(key="animation_position_button_label"))
        self.zoom.default = str(image.zoom)
        self.focus_x.default = str(image.focus_x)
        self.focus_y.default = str(image.focus_y)


class AnimationPositionButton(ui.Button["CardSettingsView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="animation_position_button_label"),
            custom_id="profile_animation_position",
            emoji=PHOTO,
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        image = next(
            (img for img in self.view.custom_images if img.url == self.view.current_image), None
        )
        if image is None:
            return

        modal = AnimationPositionModal(image)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        image.zoom = int(modal.zoom.value)
        image.focus_x = int(modal.focus_x.value)
        image.focus_y = int(modal.focus_y.value)
        await image.save(update_fields=("zoom", "focus_x", "focus_y"))
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
        is_animated = image_type == "build_card_image" and any(
            img.animated and img.url == current_image for img in custom_images
        )
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

        # Team cards have a single template that always supports custom images,
        # so template switching is only shown for build card images
        template_block: list[ui.TextDisplay | ui.ActionRow | discord.ui.Separator] = []
        if image_type == "build_card_image":
            template_block.extend(
                (
                    ui.TextDisplay(
                        LocaleStr(
                            custom_str="### {title}\n{desc}",
                            title=LocaleStr(key="card_settings.template"),
                            desc=self.template_status,
                        )
                    ),
                    ui.ActionRow(
                        CardTemplateSelect(current_template=card_settings.template, game=game)
                    ),
                    discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
                )
            )

        m3_art: list[ui.Section | discord.ui.Separator] = []
        if game is Game.ZZZ:
            m3_art.extend(
                (
                    discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
                    ui.Section(
                        ui.TextDisplay(
                            LocaleStr(
                                custom_str="### {title}\n{desc}",
                                title=LocaleStr(key="image_settings_use_m3_art"),
                                desc=LocaleStr(key="image_settings_use_m3_art_desc"),
                            )
                        ),
                        accessory=UseM3ArtButton(
                            current=card_settings.use_m3_art, disabled=self.disable_m3_art
                        ),
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
            *template_block,
            # Current image
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}", title=LocaleStr(key="card_settings.current_image")
                )
            ),
            ui.ActionRow(ImageTypeSelect(image_type)),
            *preview,
            ui.ActionRow(
                ImageSelect(
                    current_image=current_image,
                    default_collection=default_collection,
                    custom_images=custom_images,
                )
            ),
            ui.ActionRow(
                AddImageButton(),
                GenerateAIArtButton(disabled=self.disable_ai),
                EditImageButton(disabled=not is_custom),
                RemoveImageButton(disabled=not is_custom),
                AnimationPositionButton(disabled=not is_animated),
            ),
            *m3_art,
            accent_color=card_settings.custom_primary_color or default_color,
        )

    @property
    def template_status(self) -> LocaleStr:
        if self.disable_image:
            return LocaleStr(key="image_settings_template_not_supported")
        return LocaleStr(key="image_settings_template_supported")

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
        return not CONFIG.novelai or self.game is Game.ZZZ
