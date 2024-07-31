from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.emojis import SETTINGS
from hoyo_buddy.enums import CharacterType
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import Button, GoBackButton

from ..btn_states import DISABLE_AI_ART, DISABLE_COLOR, DISABLE_DARK_MODE, DISABLE_IMAGE_SELECT
from .add_img_btn import AddImageButton
from .card_settings_info_btn import CardSettingsInfoButton
from .card_template_select import CardTemplateSelect
from .dark_mode_btn import DarkModeButton
from .gen_ai_art_btn import GenerateAIArtButton
from .image_select import ImageSelect
from .primary_color_btn import PrimaryColorButton
from .remove_img_btn import RemoveImageButton
from .set_default_temp import SetCurTempAsDefaultButton

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import ProfileView  # noqa: F401


class CardSettingsButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="profile.card_settings.button.label"),
            disabled=True,
            custom_id="profile_card_settings",
            emoji=SETTINGS,
        )

    async def callback(self, i: Interaction) -> None:
        assert self.view._card_settings is not None
        assert self.view.character_id is not None

        go_back_button = GoBackButton(self.view.children)
        self.view.clear_items()
        self.view.add_item(go_back_button)

        default_arts: list[str] = self.view._card_data[self.view.character_id]["arts"]

        self.view.add_item(
            ImageSelect(
                self.view._card_settings.current_image,
                default_arts,
                self.view._card_settings.custom_images,
                self.view._card_settings.template,
                DISABLE_IMAGE_SELECT[self.view._card_settings.template],
            )
        )

        self.view.add_item(
            CardTemplateSelect(
                self.view._card_settings.template,
                self.view.character_type is CharacterType.CACHE,
                self.view.game,
            )
        )
        self.view.add_item(
            PrimaryColorButton(
                self.view._card_settings.custom_primary_color,
                DISABLE_COLOR[self.view._card_settings.template],
            )
        )
        self.view.add_item(SetCurTempAsDefaultButton())
        self.view.add_item(
            DarkModeButton(
                self.view._card_settings.dark_mode,
                DISABLE_DARK_MODE[self.view._card_settings.template],
            )
        )
        self.view.add_item(CardSettingsInfoButton())

        self.view.add_item(
            GenerateAIArtButton(disabled=DISABLE_AI_ART[self.view._card_settings.template])
        )
        self.view.add_item(AddImageButton())
        self.view.add_item(
            RemoveImageButton(
                self.view._card_settings.current_image in default_arts
                or not self.view._card_settings.current_image
            )
        )

        await i.response.edit_message(view=self.view)
