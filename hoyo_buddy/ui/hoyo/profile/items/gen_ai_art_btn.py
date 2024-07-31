from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, TextStyle
from seria.utils import read_json

from hoyo_buddy.exceptions import GuildOnlyFeatureError, NSFWPromptError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, Modal, TextInput
from hoyo_buddy.utils import upload_image

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from .image_select import ImageSelect
    from .remove_img_btn import RemoveImageButton


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


class GenerateAIArtButton(Button):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.generate_ai_art.button.label"),
            style=ButtonStyle.blurple,
            row=3,
            custom_id="profile_generate_ai_art",
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        if i.guild is None:
            raise GuildOnlyFeatureError

        modal = GenerateAIArtModal(title=LocaleStr(key="profile.generate_ai_art_modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if not modal.prompt.value:
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
        self.view._card_settings.custom_images.append(url)
        self.view._card_settings.current_image = url
        await self.view._card_settings.save(update_fields=("custom_images", "current_image"))

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        # Set the new image as the default (selected) option
        image_select.update_options_defaults(values=[url])
        image_select.translate(self.view.locale, self.view.translator)

        # Enable the remove image button
        remove_img_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_img_btn.disabled = False

        # Redraw the card
        await self.view.update(i, self)
