from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any

import enka
from discord import ButtonStyle, TextStyle
from genshin.models import ZZZPartialAgent
from loguru import logger
from tortoise.exceptions import IntegrityError

from hoyo_buddy.constants import ZZZ_DISC_SUBSTATS
from hoyo_buddy.db import CardSettings, Settings
from hoyo_buddy.embeds import DefaultEmbed, Embed
from hoyo_buddy.emojis import PALETTE
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import InvalidColorError
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, ToggleButton, View
from hoyo_buddy.utils import is_valid_hex_color

from .items.settings_chara_select import CharacterSelect as SettingsCharacterSelect
from .templates import (
    DISABLE_COLOR,
    DISABLE_DARK_MODE,
    DISABLE_IMAGE,
    TEMPLATE_AUTHORS,
    TEMPLATE_NAMES,
    TEMPLATE_PREVIEWS,
    TEMPLATES,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Member, User

    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction

    from .view import Character


async def get_card_settings(user_id: int, character_id: str, *, game: Game) -> CardSettings:
    card_settings = await CardSettings.get_or_none(
        user_id=user_id, character_id=character_id, game=game
    )
    if card_settings is None:
        card_settings = await CardSettings.get_or_none(user_id=user_id, character_id=character_id)

    if card_settings is None:
        user_settings = await Settings.get(user_id=user_id)
        templates = {
            Game.GENSHIN: user_settings.gi_card_temp,
            Game.STARRAIL: user_settings.hsr_card_temp,
            Game.ZZZ: user_settings.zzz_card_temp,
        }
        template = templates.get(game)
        if template is None:
            msg = f"Game {game!r} does not have its table column for default card template."
            raise ValueError(msg)

        try:
            card_settings = await CardSettings.create(
                user_id=user_id,
                character_id=character_id,
                dark_mode=False,
                template=template,
                game=game,
            )
        except IntegrityError:
            card_settings = await CardSettings.get(
                user_id=user_id, character_id=character_id, game=game
            )
    elif card_settings.game is None:
        card_settings.game = game
        await card_settings.save(update_fields=("game",))

    return card_settings


def get_default_color(character: Character, card_data: dict[str, Any]) -> str | None:
    chara_key = str(character.id)
    with contextlib.suppress(KeyError):
        if isinstance(character, ZZZPartialAgent):
            return card_data[chara_key]["color"]
        if isinstance(character, enka.hsr.Character):
            return card_data[chara_key]["primary"]
    return None


class CardSettingsView(View):
    def __init__(
        self,
        characters: Sequence[Character],
        selected_character_id: str,
        card_data: dict[str, Any],
        card_settings: CardSettings,
        game: Game,
        settings: Settings,
        *,
        hb_template_only: bool,
        is_team: bool,
        author: User | Member,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)

        self._characters = characters
        self._user_id = author.id
        self._card_data = card_data
        self._hb_template_only = hb_template_only
        self._is_team = is_team

        self.game = game
        self.selected_character_id = selected_character_id
        self.card_settings = card_settings
        self.settings = settings

    @staticmethod
    def _get_color_markdown(color: str) -> str:
        return f"[{color}](https://www.colorhexa.com/{color[1:]})"

    @staticmethod
    def _get_color_image(color: str) -> str:
        return f"https://singlecolorimage.com/get/{color[1:]}/100x100"

    @property
    def template(self) -> tuple[Game, str]:
        return self.game, self.card_settings.template

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

    def _add_items(self) -> None:
        self.add_item(CharacterSelect(self._characters, self.selected_character_id, row=0))

        row = 1
        self.add_item(
            CardTemplateSelect(
                self.card_settings.template, hb_only=self._hb_template_only, game=self.game, row=row
            )
        )

        if self.game is Game.ZZZ:
            row = 2
            self.add_item(HighlightSubstatSelector(self.card_settings.highlight_substats, row=row))

        self.add_item(
            PrimaryColorButton(
                self.card_settings.custom_primary_color, disabled=self.disable_color, row=row + 1
            )
        )
        self.add_item(SetCurTempAsDefaultButton(row=row + 1))

        self.add_item(
            DarkModeButton(
                current_toggle=self.card_settings.dark_mode,
                disabled=self.disable_dark_mode,
                row=row + 2,
            )
        )
        self.add_item(
            SubstatRolls(
                current_toggle=self.card_settings.show_substat_rolls,
                disabled=self.disable_substat_roll_button,
                row=row + 2,
            )
        )
        self.add_item(
            ShowRankButton(
                current_toggle=self.card_settings.show_rank,
                disabled=self.disable_show_rank_button,
                row=row + 2,
            )
        )
        self.add_item(
            HighlightSpecialStats(
                current_toggle=self.card_settings.highlight_special_stats,
                disabled=self.disable_substat_roll_button,
                row=row + 2,
            )
        )

    def _get_current_character(self) -> Character:
        character = next(
            (chara for chara in self._characters if str(chara.id) == self.selected_character_id),
            None,
        )
        if character is None:
            msg = f"Character with id {self.selected_character_id!r} not found."
            raise ValueError(msg)
        return character

    def get_settings_embed(self) -> Embed:
        card_settings = self.card_settings
        character = self._get_current_character()

        author1, author2 = TEMPLATE_AUTHORS[card_settings.template.rstrip("1234567890")]
        if author1 == author2:
            description = LocaleStr(
                key="profile.card_template_select.same_author.description", author=author1
            )
        else:
            description = LocaleStr(
                key="profile.card_template_select.diff_author.description",
                author1=author1,
                author2=author2,
            )
        color = card_settings.custom_primary_color or get_default_color(character, self._card_data)

        embed = Embed(
            locale=self.locale,
            title=LocaleStr(key="card_settings.modifying_for", name=character.name),
            description=description,
            color=int(color.lstrip("#"), 16) if color is not None else 6649080,
        )

        default_str = LocaleStr(key="card_settings.color_default").translate(self.locale)
        if color is not None:
            value = self._get_color_markdown(color)
            if card_settings.custom_primary_color is None:
                value += f" ({default_str})"
            embed.set_thumbnail(url=self._get_color_image(color))
        else:
            value = LocaleStr(key="card_settings.no_color")

        embed.add_field(name=LocaleStr(key="card_settings.card_color"), value=value, inline=False)
        embed.add_field(name=LocaleStr(key="template_preview_header"))
        embed.set_image(url=TEMPLATE_PREVIEWS.get(self.template, ""))
        embed.set_footer(text=LocaleStr(key="card_settings.footer"))
        return embed

    async def start(self, i: Interaction) -> None:
        self._add_items()
        embed = self.get_settings_embed()
        await i.followup.send(embed=embed, view=self, ephemeral=True)
        self.message = await i.original_response()


class CharacterSelect(SettingsCharacterSelect[CardSettingsView]):
    async def callback(self, i: Interaction) -> Any:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        await i.response.defer()
        character_id = self.values[0]

        self.update_options_defaults()
        self.view.selected_character_id = character_id
        self.view.card_settings = await get_card_settings(
            self.view._user_id, character_id, game=self.view.game
        )

        # Update other item styles
        template_select: CardTemplateSelect = self.view.get_item("profile_card_template_select")
        template_select.update_options_defaults(values=[self.view.card_settings.template])

        if self.view.game is Game.ZZZ:
            hl_substat_select: HighlightSubstatSelector = self.view.get_item(
                "card_settings_hl_substat_select"
            )
            hl_substat_select.options = hl_substat_select.get_options(
                self.view.card_settings.highlight_substats
            )
            hl_substat_select.translate(self.view.locale)

        dark_mode_button: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_button.current_toggle = self.view.card_settings.dark_mode
        dark_mode_button.update_style()

        embed = self.view.get_settings_embed()
        await i.edit_original_response(embed=embed, view=self.view)
        return None


class DarkModeButton(ToggleButton[CardSettingsView]):
    def __init__(self, *, current_toggle: bool, disabled: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="dark_mode_button_label"),
            custom_id="profile_dark_mode",
            disabled=disabled,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        self.view.card_settings.dark_mode = self.current_toggle
        await self.view.card_settings.save(update_fields=("dark_mode",))


class PrimaryColorModal(Modal):
    color = TextInput(
        label=LocaleStr(key="profile.primary_color_modal.color.label"),
        placeholder="#000000",
        style=TextStyle.short,
        min_length=7,
        max_length=7,
        required=False,
    )

    def __init__(self, current_color: str | None) -> None:
        super().__init__(title=LocaleStr(key="profile.primary_color_modal.title"))
        self.color.default = current_color


class PrimaryColorButton(Button[CardSettingsView]):
    def __init__(self, current_color: str | None, *, disabled: bool, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.primary_color.button.label"),
            style=ButtonStyle.blurple,
            custom_id="profile_primary_color",
            disabled=disabled,
            row=row,
            emoji=PALETTE,
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

        embed = self.view.get_settings_embed()
        await i.edit_original_response(embed=embed, view=self.view)


class CardTemplateSelect(Select[CardSettingsView]):
    def __init__(self, current_template: str, *, hb_only: bool, game: Game, row: int) -> None:
        options: list[SelectOption] = []

        templates = TEMPLATES[game]
        for template in templates:
            template_id = template.rstrip("1234567890")
            if hb_only and template_id != "hb":
                continue

            template_name = TEMPLATE_NAMES[template_id]
            label = LocaleStr(key=template_name, num=int(template[-1]))
            description = LocaleStr(
                key="is_not_support_custom_image_desc"
                if DISABLE_IMAGE.get((game, template), True)
                else "is_support_custom_image_desc"
            )

            select_option = SelectOption(
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
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        # Save the setting to db
        self.view.card_settings.template = self.values[0]
        await self.view.card_settings.save(update_fields=("template",))

        self.update_options_defaults()

        with contextlib.suppress(ValueError):
            hl_substat_select: HighlightSubstatSelector = self.view.get_item(
                "card_settings_hl_substat_select"
            )
            hl_substat_select.options = hl_substat_select.get_options(
                self.view.card_settings.highlight_substats
            )
            hl_substat_select.translate(self.view.locale)

        change_color_btn: PrimaryColorButton = self.view.get_item("profile_primary_color")
        change_color_btn.disabled = self.view.disable_color

        dark_mode_btn: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_btn.disabled = self.view.disable_dark_mode

        show_rank_btn: ShowRankButton = self.view.get_item("profile_show_rank")
        show_rank_btn.disabled = self.view.disable_show_rank_button

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


class SetCurTempAsDefaultButton(Button[CardSettingsView]):
    """Set current template as default template button."""

    def __init__(self, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile_view.set_cur_temp_as_default"),
            custom_id="set_cur_temp_as_default",
            style=ButtonStyle.primary,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        game_column_map = {
            Game.GENSHIN: "gi_card_temp",
            Game.STARRAIL: "hsr_card_temp",
            Game.ZZZ: "zzz_card_temp",
        }
        column_name = game_column_map.get(self.view.game)
        if column_name is None:
            msg = f"Game {self.view.game!r} does not have a column for card template"
            raise ValueError(msg)

        await Settings.filter(user_id=i.user.id).update(
            **{column_name: self.view.card_settings.template}
        )

        template = self.view.card_settings.template.rstrip("1234567890")
        template_num = self.view.card_settings.template[len(template) :]

        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="set_cur_temp_as_default.done"),
            description=LocaleStr(
                key="set_cur_temp_as_default.done_desc",
                game=EnumStr(self.view.game),
                template=LocaleStr(key=TEMPLATE_NAMES[template], num=template_num),
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class ShowRankButton(ToggleButton[CardSettingsView]):
    def __init__(self, *, current_toggle: bool, disabled: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="profile_view_show_rank_button_label"),
            custom_id="profile_show_rank",
            disabled=disabled,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        self.view.card_settings.show_rank = self.current_toggle
        await self.view.card_settings.save(update_fields=("show_rank",))


class SubstatRolls(ToggleButton[CardSettingsView]):
    def __init__(self, *, current_toggle: bool, disabled: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="profile_show_substat_rolls"),
            custom_id="profile_show_substat_rolls",
            disabled=disabled,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        self.view.card_settings.show_substat_rolls = self.current_toggle
        await self.view.card_settings.save(update_fields=("show_substat_rolls",))


class HighlightSpecialStats(ToggleButton[CardSettingsView]):
    def __init__(self, *, current_toggle: bool, disabled: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="card_settings_hl_special_stats_button_label"),
            custom_id="card_settings_hl_special_stats_button_label",
            disabled=disabled,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        self.view.card_settings.highlight_special_stats = self.current_toggle
        await self.view.card_settings.save(update_fields=("highlight_special_stats",))


class HighlightSubstatSelector(Select[CardSettingsView]):
    def __init__(self, current: list[int], *, row: int) -> None:
        options = self.get_options(current)
        super().__init__(
            placeholder=LocaleStr(key="card_settings_hl_substat_select_placeholder"),
            row=row,
            options=options,
            max_values=len(options),
            custom_id="card_settings_hl_substat_select",
        )

    @staticmethod
    def get_options(current: list[int]) -> list[SelectOption]:
        options: list[SelectOption] = []
        added: set[int] = set()

        for key, substat_id, append in ZZZ_DISC_SUBSTATS:
            if substat_id in added:
                continue

            added.add(substat_id)
            options.append(
                SelectOption(
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
