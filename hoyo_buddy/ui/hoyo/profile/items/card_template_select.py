from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.components import Select, SelectOption

from ..btn_states import DISABLE_AI_ART, DISABLE_COLOR, DISABLE_DARK_MODE, DISABLE_IMAGE_SELECT

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401
    from .dark_mode_btn import DarkModeButton
    from .gen_ai_art_btn import GenerateAIArtButton
    from .image_select import ImageSelect
    from .primary_color_btn import PrimaryColorButton


class CardTemplateSelect(Select["ProfileView"]):
    def __init__(self, current_template: str, hb_only: bool, game: Game) -> None:
        src_templates = (1, 2, 3)
        enkac_templates = (1, 2)  # EnkaCard templates

        options: list[SelectOption] = []

        options.append(
            SelectOption(
                label=LocaleStr(
                    "Hoyo Buddy template {num}",
                    key="profile.card_template_select.hb.label",
                    num=1,
                ),
                description=LocaleStr(
                    "Designed and programmed by {author}",
                    key="profile.card_template_select.same_author.description",
                    author="@seriaati",
                ),
                value="hb1",
                default=current_template == "hb1",
            ),
        )

        if not hb_only:
            if game is Game.STARRAIL:
                for template_num in src_templates:
                    value = f"src{template_num}"
                    options.append(
                        SelectOption(
                            label=LocaleStr(
                                "StarRailCard template {num}",
                                key="profile.card_template_select.src.label",
                                num=template_num,
                            ),
                            description=LocaleStr(
                                "Designed and programmed by {author}",
                                key="profile.card_template_select.same_author.description",
                                author="@korzzex",
                            ),
                            value=value,
                            default=current_template == value,
                        ),
                    )
            else:
                options.extend(
                    [
                        SelectOption(
                            label=LocaleStr(
                                "Classic Enka template",
                                key="profile.card_template_select.enka_classic.label",
                            ),
                            description=LocaleStr(
                                "Designed by {author1} and programmed by {author2}",
                                key="profile.card_template_select.diff_author.description",
                                author1="@algoinde",
                                author2="@hattvr",
                            ),
                            value="hattvr1",
                            default=current_template == "hattvr1",
                        ),
                        SelectOption(
                            label=LocaleStr(
                                "ENCard template {num}",
                                key="profile.card_template_select.encard.label",
                                num=1,
                            ),
                            description=LocaleStr(
                                "Designed and programmed by {author}",
                                key="profile.card_template_select.same_author.description",
                                author="@korzzex",
                            ),
                            value="encard1",
                            default=current_template == "encard1",
                        ),
                    ]
                )
                for template_num in enkac_templates:
                    value = f"enkacard{template_num}"
                    options.append(
                        SelectOption(
                            label=LocaleStr(
                                "EnkaCard template {num}",
                                key="profile.card_template_select.enkacard.label",
                                num=template_num,
                            ),
                            description=LocaleStr(
                                "Designed by {author1} and programmed by {author2}",
                                key="profile.card_template_select.diff_author.description",
                                author1="@algoinde",
                                author2="@korzzex",
                            )
                            if template_num == 3
                            else LocaleStr(
                                "Designed and programmed by {author}",
                                key="profile.card_template_select.same_author.description",
                                author="@korzzex",
                            ),
                            value=value,
                            default=current_template == value,
                        ),
                    )

        super().__init__(
            options=options,
            placeholder=LocaleStr(
                "Select a template", key="profile.card_template_select.placeholder"
            ),
            row=1,
            custom_id="profile_card_template_select",
        )

    async def callback(self, i: INTERACTION) -> None:
        assert self.view._card_settings is not None

        # Save the setting to db
        self.view._card_settings.template = self.values[0]
        await self.view._card_settings.save(update_fields=("template",))

        self.update_options_defaults()

        change_color_btn: PrimaryColorButton = self.view.get_item("profile_primary_color")
        change_color_btn.disabled = DISABLE_COLOR[self.values[0]]

        dark_mode_btn: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_btn.disabled = DISABLE_DARK_MODE[self.values[0]]

        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.disabled = DISABLE_IMAGE_SELECT[self.values[0]]

        gen_ai_art_btn: GenerateAIArtButton = self.view.get_item("profile_generate_ai_art")
        gen_ai_art_btn.disabled = DISABLE_AI_ART[self.values[0]]

        await self.set_loading_state(i)

        # Redraw the card
        await self.view.update(i, self)
