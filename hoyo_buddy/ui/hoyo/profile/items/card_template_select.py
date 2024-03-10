from typing import TYPE_CHECKING

from discord import File

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.components import Select, SelectOption

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401
    from .dark_mode_btn import DarkModeButton
    from .image_select import ImageSelect
    from .primary_color_btn import PrimaryColorButton


class CardTemplateSelect(Select["ProfileView"]):
    def __init__(self, current_template: str, is_live: bool, game: Game) -> None:
        hb_templates = (1,)
        src_templates = (1, 2, 3)
        enkac_templates = (1, 2, 3, 5, 7)  # EnkaCard2 templates

        options: list[SelectOption] = []

        for template_num in hb_templates:
            value = f"hb{template_num}"
            options.append(
                SelectOption(
                    label=LocaleStr(
                        "Hoyo Buddy Template {num}",
                        key="profile.card_template_select.hb.label",
                        num=template_num,
                    ),
                    description=LocaleStr(
                        "Designed and programmed by {author}",
                        key="profile.card_template_select.same_author.description",
                        author="@seriaati",
                    ),
                    value=value,
                    default=current_template == value,
                ),
            )
        if is_live:
            if game is Game.STARRAIL:
                for template_num in src_templates:
                    value = f"src{template_num}"
                    options.append(
                        SelectOption(
                            label=LocaleStr(
                                "StarRailCard Template {num}",
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
                                "Classic Enka Template",
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
                                "ENCard Template {num}",
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
                                "EnkaCard Template {num}",
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
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        # Save the setting to db
        self.view._card_settings.template = self.values[0]
        await self.view._card_settings.save()

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Disable the color button if the template is not Hoyo Buddy or the game is not StarRail
        change_color_btn: PrimaryColorButton = self.view.get_item("profile_primary_color")
        change_color_btn.disabled = (
            "hb" not in self.values[0] or self.view.game is not Game.STARRAIL
        )

        # Disable the dark mode button if the template is not Hoyo Buddy
        dark_mode_btn: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_btn.disabled = "hb" not in self.values[0]

        # Disable the image select if the template is hattvr1
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.disabled = self.values[0] == "hattvr1"

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )
