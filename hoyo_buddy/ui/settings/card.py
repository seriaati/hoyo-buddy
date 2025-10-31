from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from loguru import logger

from hoyo_buddy import emojis, ui
from hoyo_buddy.constants import EMPTY_CHAR, ZZZ_DISC_SUBSTATS
from hoyo_buddy.db.models import CardSettings
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import InvalidColorError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui.hoyo.profile.card_settings import get_default_color
from hoyo_buddy.ui.hoyo.profile.templates import (
    DISABLE_COLOR,
    DISABLE_DARK_MODE,
    DISABLE_IMAGE,
    TEMPLATE_AUTHORS,
    TEMPLATE_NAMES,
    TEMPLATE_PREVIEWS,
    TEMPLATES,
)
from hoyo_buddy.utils.misc import get_template_name, get_template_num, is_valid_hex_color
from hoyo_buddy.web_app.utils import get_gacha_icon

if TYPE_CHECKING:
    from hoyo_buddy.db.models.settings import Settings
    from hoyo_buddy.types import Interaction

    from .view import CardSettingsView  # noqa: F401


class HighlightSubstatSelector(ui.Select["CardSettingsView"]):
    def __init__(self, current: list[int], *, disabled: bool) -> None:
        options = self.get_options(current)
        super().__init__(
            placeholder=LocaleStr(key="card_settings_hl_substat_select_placeholder"),
            options=options,
            max_values=len(options),
            custom_id="card_settings_hl_substat_select",
            disabled=disabled,
        )

    @staticmethod
    def get_options(current: list[int]) -> list[ui.SelectOption]:
        options: list[ui.SelectOption] = []
        added: set[int] = set()

        for key, substat_id, append in ZZZ_DISC_SUBSTATS:
            if substat_id in added:
                continue

            added.add(substat_id)
            options.append(
                ui.SelectOption(
                    label=LocaleStr(key=key, append=append, data_game=Game.ZZZ),
                    value=str(substat_id),
                    default=substat_id in current,
                )
            )

        return options

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()
        self.view.card_settings.highlight_substats = [int(value) for value in self.values]
        await self.view.card_settings.save(update_fields=("highlight_substats",))

        await self.view.update(i)


class DarkModeButton(ui.EmojiToggleButton["CardSettingsView"]):
    def __init__(self, *, current: bool, disabled: bool) -> None:
        super().__init__(current=current, disabled=disabled)

    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.card_settings.dark_mode = self.current
        await self.view.card_settings.save(update_fields=("dark_mode",))

        await self.view.update(i)


class PrimaryColorModal(ui.Modal):
    color: ui.Label[ui.TextInput] = ui.Label(
        text=LocaleStr(key="profile.primary_color_modal.color.label"),
        component=ui.TextInput(
            placeholder="#000000",
            style=discord.TextStyle.short,
            min_length=7,
            max_length=7,
            required=False,
        ),
    )

    def __init__(self, current_color: str | None) -> None:
        super().__init__(title=LocaleStr(key="profile.primary_color_modal.title"))
        self.color.default = current_color


class SubstatRollButton(ui.EmojiToggleButton["CardSettingsView"]):
    def __init__(self, *, current: bool, disabled: bool) -> None:
        super().__init__(current=current, disabled=disabled)

    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.card_settings.show_substat_rolls = self.current
        await self.view.card_settings.save(update_fields=("show_substat_rolls",))

        await self.view.update(i)


class PrimaryColorButton(ui.Button["CardSettingsView"]):
    def __init__(self, current_color: str | None, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.primary_color.button.label"),
            style=discord.ButtonStyle.blurple,
            custom_id="profile_primary_color",
            disabled=disabled,
            emoji=emojis.PALETTE,
        )
        self.current_color = current_color

    async def callback(self, i: Interaction) -> None:
        # Open the color modal
        modal = PrimaryColorModal(self.current_color)
        modal.translate(self.view.locale)
        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        color = modal.color.value or None
        if color:
            # Test if the color is valid
            valid = is_valid_hex_color(color)
            if not valid:
                raise InvalidColorError

        # Save the color to settings
        self.view.card_settings.custom_primary_color = self.current_color = color
        await self.view.card_settings.save(update_fields=("custom_primary_color",))

        await self.view.update(i)


class ShowRankButton(ui.EmojiToggleButton["CardSettingsView"]):
    def __init__(self, *, current: bool, disabled: bool) -> None:
        super().__init__(current=current, disabled=disabled)

    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.card_settings.show_rank = self.current
        await self.view.card_settings.save(update_fields=("show_rank",))

        await self.view.update(i)


class TeamCardDarkModeButton(ui.EmojiToggleButton["CardSettingsView"]):
    def __init__(self, *, current: bool, disabled: bool) -> None:
        super().__init__(current=current, disabled=disabled)

    async def callback(self, i: Interaction) -> None:
        self.current = not self.current
        self.update_style()

        self.view.settings.team_card_dark_mode = self.current
        await self.view.settings.save(update_fields=("team_card_dark_mode",))

        await self.view.update(i)


class ApplyTemplateToAllButton(ui.Button["CardSettingsView"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="apply_label"),
            style=discord.ButtonStyle.blurple,
            custom_id="apply_template_to_all_chars",
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()

        # Set for current characters
        await CardSettings.filter(user_id=i.user.id, game=self.view.game).update(
            template=self.view.card_settings.template
        )

        # Set for future characters
        game = self.view.game
        if game is Game.GENSHIN:
            self.view.settings.gi_card_temp = self.view.card_settings.template
        elif game is Game.STARRAIL:
            self.view.settings.hsr_card_temp = self.view.card_settings.template
        elif game is Game.ZZZ:
            self.view.settings.zzz_card_temp = self.view.card_settings.template
        else:
            logger.error(f"Unknown game {game} for applying template to all characters")

        await self.view.settings.save(
            update_fields=("gi_card_temp", "hsr_card_temp", "zzz_card_temp")
        )

        self.emoji = emojis.CHECK
        self.label = None
        self.style = discord.ButtonStyle.green
        await i.edit_original_response(view=self.view)


class ApplyDarkThemeToAllButton(ui.Button["CardSettingsView"]):
    def __init__(self, *, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="apply_label"), style=discord.ButtonStyle.blurple, disabled=disabled
        )

    async def callback(self, i: Interaction) -> None:
        await i.response.defer()

        # Set for current characters
        await CardSettings.filter(user_id=i.user.id, game=self.view.game).update(
            dark_mode=self.view.card_settings.dark_mode
        )

        # Set for future characters
        game = self.view.game
        if game is Game.GENSHIN:
            self.view.settings.gi_dark_mode = self.view.card_settings.dark_mode
        elif game is Game.STARRAIL:
            self.view.settings.hsr_dark_mode = self.view.card_settings.dark_mode
        elif game is Game.ZZZ:
            self.view.settings.zzz_dark_mode = self.view.card_settings.dark_mode
        else:
            logger.error(f"Unknown game {game} for applying dark theme to all characters")

        await self.view.settings.save(
            update_fields=("gi_dark_mode", "hsr_dark_mode", "zzz_dark_mode")
        )

        self.emoji = emojis.CHECK
        self.label = None
        self.style = discord.ButtonStyle.green
        await i.edit_original_response(view=self.view)


class CardTemplateSelect(ui.Select["CardSettingsView"]):
    def __init__(self, current_template: str, *, game: Game) -> None:
        options: list[ui.SelectOption] = []

        templates = TEMPLATES[game]
        for template in templates:
            name = get_template_name(template)
            template_name = TEMPLATE_NAMES[name]  # localized name
            label = LocaleStr(key=template_name, num=get_template_num(template))

            description = LocaleStr(
                key="is_not_support_custom_image_desc"
                if DISABLE_IMAGE.get((game, template), True)
                else "is_support_custom_image_desc"
            )

            select_option = ui.SelectOption(
                label=label,
                description=description,
                value=template,
                default=current_template == template,
            )
            options.append(select_option)

        super().__init__(
            options=options,
            placeholder=LocaleStr(key="profile.card_template_select.placeholder"),
            custom_id="profile_card_template_select",
        )

    async def callback(self, i: Interaction) -> None:
        self.view.card_settings.template = self.values[0]
        await self.view.card_settings.save(update_fields=("template",))

        await self.view.update(i)


class CardSettingsContainer(ui.Container):
    def __init__(
        self, *, card_settings: CardSettings, settings: Settings, character_name: str, game: Game
    ) -> None:
        self.card_settings = card_settings
        self.settings = settings
        self.template = (game, card_settings.template)
        self.game = game
        self.character_id = card_settings.character_id
        self.character_name = character_name
        self.icon_url = get_gacha_icon(game=self.game, item_id=int(self.card_settings.character_id))

        default_color = get_default_color(
            card_settings.character_id,
            game=game,
            template=card_settings.template,
            dark_mode=card_settings.dark_mode,
            outfit_id=None,
        )

        if self.disable_color:
            color_desc = LocaleStr(key="card_settings.no_color")
        elif (
            card_settings.custom_primary_color is None
            or card_settings.custom_primary_color == default_color
        ):
            color_desc = LocaleStr(
                custom_str="{color} ({default_text})",
                color=card_settings.custom_primary_color or default_color,
                default_text=LocaleStr(key="card_settings.color_default"),
            )
        else:
            color_desc = card_settings.custom_primary_color

        super().__init__(
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="# {title}\n{desc}",
                        title=LocaleStr(key="card_settings.modifying_for", name=character_name),
                        desc=LocaleStr(key="card_settings_modifying_for_desc"),
                    )
                ),
                accessory=discord.ui.Thumbnail(media=self.icon_url),
            ),
            # Template
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}\n{desc}",
                    title=LocaleStr(key="card_settings.template"),
                    desc=LocaleStr(key="card_settings_template_desc"),
                )
            ),
            ui.ActionRow(CardTemplateSelect(current_template=card_settings.template, game=game)),
            discord.ui.MediaGallery(discord.MediaGalleryItem(TEMPLATE_PREVIEWS[self.template])),
            ui.TextDisplay(
                LocaleStr(
                    custom_str="-# {desc}\n{empty}",
                    desc=LocaleStr(
                        key="profile.card_template_select.diff_author.description",
                        author1=TEMPLATE_AUTHORS[get_template_name(card_settings.template)][0],
                        author2=TEMPLATE_AUTHORS[get_template_name(card_settings.template)][1],
                    ),
                    empty=EMPTY_CHAR,
                )
            ),
            # Color
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}\n{empty}",
                        title=LocaleStr(key="card_settings.card_color"),
                        desc=color_desc,
                        empty=EMPTY_CHAR,
                    )
                ),
                accessory=PrimaryColorButton(
                    current_color=card_settings.custom_primary_color, disabled=self.disable_color
                ),
            ),
            # Substat rolls
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}\n{empty}",
                        title=LocaleStr(key="profile_show_substat_rolls"),
                        desc=LocaleStr(key="profile_show_substat_rolls_desc"),
                        empty=EMPTY_CHAR,
                    )
                ),
                accessory=SubstatRollButton(
                    current=card_settings.show_substat_rolls,
                    disabled=self.disable_substat_roll_button,
                ),
            ),
            # Highlight substat selector
            ui.TextDisplay(
                LocaleStr(
                    custom_str="### {title}\n{desc}",
                    title=LocaleStr(key="card_settings_hl_special_stats_button_label"),
                    desc=LocaleStr(key="card_settings_hl_stats_desc"),
                )
            ),
            ui.ActionRow(
                HighlightSubstatSelector(
                    current=card_settings.highlight_substats,
                    disabled=self.disable_substat_roll_button,
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.small),
            # Show ranking
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}\n{empty}",
                        title=LocaleStr(key="profile_view_show_rank_button_label"),
                        desc=LocaleStr(key="profile_view_show_rank_desc"),
                        empty=EMPTY_CHAR,
                    )
                ),
                accessory=ShowRankButton(
                    current=card_settings.show_rank, disabled=self.disable_show_rank_button
                ),
            ),
            # Dark mode
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}\n{empty}",
                        title=LocaleStr(key="dark_theme"),
                        desc=LocaleStr(key="card_dark_theme_desc"),
                        empty=EMPTY_CHAR,
                    )
                ),
                accessory=DarkModeButton(
                    current=card_settings.dark_mode, disabled=self.disable_dark_mode
                ),
            ),
            # Team dark mode
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}\n{empty}",
                        title=LocaleStr(key="profile.team_dark_mode.button.label"),
                        desc=LocaleStr(key="team_card_dark_theme_desc"),
                        empty=EMPTY_CHAR,
                    )
                ),
                accessory=TeamCardDarkModeButton(
                    current=settings.team_card_dark_mode, disabled=self.disable_dark_mode
                ),
            ),
            # Apply template to all characters
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}\n{empty}",
                        title=LocaleStr(key="apply_template_to_all_chars"),
                        desc=LocaleStr(
                            key="apply_template_to_all_chars_desc",
                            template=LocaleStr(
                                key=TEMPLATE_NAMES[get_template_name(card_settings.template)],
                                num=get_template_num(card_settings.template),
                            ),
                        ),
                        empty=EMPTY_CHAR,
                    )
                ),
                accessory=ApplyTemplateToAllButton(),
            ),
            # Apply dark theme to all characters
            ui.Section(
                ui.TextDisplay(
                    LocaleStr(
                        custom_str="### {title}\n{desc}",
                        title=LocaleStr(key="apply_dark_theme_to_all_chars"),
                        desc=LocaleStr(
                            key="apply_dark_theme_to_all_chars_desc",
                            status=LocaleStr(
                                key="notif_modal.enabled.label"
                                if card_settings.dark_mode
                                else "disabled_label"
                            ),
                        ),
                    )
                ),
                accessory=ApplyDarkThemeToAllButton(disabled=self.disable_dark_mode),
            ),
            accent_color=card_settings.custom_primary_color or default_color,
        )

    @property
    def disable_color(self) -> bool:
        if self.template not in DISABLE_COLOR:
            logger.error(f"Template {self.template} not found in DISABLE_COLOR")
            return True
        return DISABLE_COLOR[self.template]

    @property
    def disable_dark_mode(self) -> bool:
        if self.template not in DISABLE_DARK_MODE:
            logger.error(f"Template {self.template} not found in DISABLE_DARK_MODE")
            return True
        return DISABLE_DARK_MODE[self.template]

    @property
    def disable_show_rank_button(self) -> bool:
        return self.game is not Game.GENSHIN or "hb" not in self.card_settings.template

    @property
    def disable_substat_roll_button(self) -> bool:
        return self.game is not Game.ZZZ
