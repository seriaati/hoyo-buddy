from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import SETTINGS
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.components import Button, GoBackButton

from .....models import HoyolabHSRCharacter
from .add_img_btn import AddImageButton
from .card_settings_info_btn import CardSettingsInfoButton
from .card_template_select import CardTemplateSelect
from .dark_mode_btn import DarkModeButton
from .gen_ai_art_btn import GenerateAIArtButton
from .image_select import ImageSelect
from .primary_color_btn import PrimaryColorButton
from .remove_img_btn import RemoveImageButton

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class CardSettingsButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Card Settings", key="profile.card_settings.button.label"),
            disabled=True,
            custom_id="profile_card_settings",
            emoji=SETTINGS,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None
        assert self.view.character_id is not None

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(go_back_button)

        default_arts: list[str] = self.view._card_data[self.view.character_id]["arts"]
        character = next(c for c in self.view.characters if str(c.id) == self.view.character_id)

        self.view.add_item(
            ImageSelect(
                self.view._card_settings.current_image,
                default_arts,
                self.view._card_settings.custom_images,
                self.view._card_settings.template == "hattvr1",
            )
        )
        self.view.add_item(
            CardTemplateSelect(
                self.view._card_settings.template,
                self.view.character_id not in self.view.live_data_character_ids
                or isinstance(character, HoyolabHSRCharacter),
                self.view.game,
            )
        )
        self.view.add_item(
            PrimaryColorButton(
                self.view._card_settings.custom_primary_color,
                "hb" not in self.view._card_settings.template
                or self.view.game is not Game.STARRAIL,
            )
        )
        self.view.add_item(
            DarkModeButton(
                self.view._card_settings.dark_mode, "hb" not in self.view._card_settings.template
            )
        )
        self.view.add_item(CardSettingsInfoButton())

        self.view.add_item(GenerateAIArtButton())
        self.view.add_item(AddImageButton())
        self.view.add_item(
            RemoveImageButton(self.view._card_settings.current_image in default_arts)
        )

        await i.response.edit_message(view=self.view)
