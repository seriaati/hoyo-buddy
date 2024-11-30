from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, Any, Final

import enka
from discord import ButtonStyle, TextStyle
from genshin.models import ZZZPartialAgent

from hoyo_buddy.db.models import CardSettings, Settings
from hoyo_buddy.embeds import DefaultEmbed, Embed
from hoyo_buddy.emojis import PALETTE
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import InvalidColorError
from hoyo_buddy.l10n import EnumStr, LocaleStr
from hoyo_buddy.ui import Button, Modal, Select, SelectOption, TextInput, ToggleButton, View
from hoyo_buddy.utils import is_valid_hex_color

from .btn_states import DISABLE_COLOR, DISABLE_DARK_MODE
from .items.settings_chara_select import CharacterSelect as SettingsCharacterSelect

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale, Member, User

    from hoyo_buddy.types import Interaction

    from .view import Character

CARD_TEMPLATES: Final[dict[Game, tuple[str, ...]]] = {
    Game.GENSHIN: ("hb1", "hb2", "hattvr1", "encard1", "enkacard1", "enkacard2"),
    Game.STARRAIL: ("hb1", "src1", "src2", "src3"),
    Game.ZZZ: ("hb1", "hb2", "hb3", "hb4"),
}
CARD_TEMPLATE_AUTHORS: Final[dict[str, tuple[str, str]]] = {
    "hb": ("@ayasaku_", "@seriaati"),
    "src": ("@korzzex", "@korzzex"),
    "hattvr": ("@algoinde", "@hattvr"),
    "encard": ("@korzzex", "@korzzex"),
    "enkacard": ("@korzzex", "@korzzex"),
}
CARD_TEMPLATE_NAMES: Final[dict[str, str]] = {
    "hb": "profile.card_template_select.hb.label",
    "src": "profile.card_template_select.src.label",
    "hattvr": "profile.card_template_select.enka_classic.label",
    "encard": "profile.card_template_select.encard.label",
    "enkacard": "profile.card_template_select.enkacard.label",
}


async def get_card_settings(user_id: int, character_id: str, *, game: Game) -> CardSettings:
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

        card_settings = await CardSettings.create(
            user_id=user_id, character_id=character_id, dark_mode=False, template=template
        )

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
        hb_template_only: bool,
        is_team: bool,
        settings: Settings,
        *,
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

        self._add_items()

    @staticmethod
    def _get_color_markdown(color: str) -> str:
        return f"[{color}](https://www.colorhexa.com/{color[1:]})"

    @staticmethod
    def _get_color_image(color: str) -> str:
        return f"https://singlecolorimage.com/get/{color[1:]}/100x100"

    @property
    def disable_color_features(self) -> bool:
        return self.game is Game.GENSHIN or self.card_settings.template in DISABLE_COLOR

    @property
    def disable_dark_mode_features(self) -> bool:
        return self.game is Game.ZZZ or self.card_settings.template in DISABLE_DARK_MODE

    @property
    def disable_show_rank_button(self) -> bool:
        return self.game is not Game.GENSHIN or "hb" not in self.card_settings.template

    @property
    def disable_substat_roll_button(self) -> bool:
        return self.game is not Game.ZZZ

    def _add_items(self) -> None:
        self.add_item(CharacterSelect(self._characters, self.selected_character_id, row=0))
        self.add_item(
            CardTemplateSelect(
                self.card_settings.template, hb_only=self._hb_template_only, game=self.game, row=1
            )
        )

        self.add_item(
            PrimaryColorButton(
                self.card_settings.custom_primary_color, disabled=self.disable_color_features, row=2
            )
        )
        self.add_item(SetCurTempAsDefaultButton(row=2))

        self.add_item(
            DarkModeButton(
                current_toggle=self.card_settings.dark_mode,
                disabled=self.disable_dark_mode_features,
                row=3,
            )
        )
        self.add_item(
            SubstatRolls(
                current_toggle=self.card_settings.show_substat_rolls,
                disabled=self.disable_substat_roll_button,
                row=3,
            )
        )
        self.add_item(
            ShowRankButton(
                current_toggle=self.card_settings.show_rank,
                disabled=self.disable_show_rank_button,
                row=3,
            )
        )
        self.add_item(
            HighlightSpecialStats(
                current_toggle=self.card_settings.highlight_special_stats,
                disabled=self.disable_substat_roll_button,
                row=3,
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

        color = card_settings.custom_primary_color or get_default_color(character, self._card_data)
        embed = Embed(
            locale=self.locale,
            title=LocaleStr(key="card_settings.modifying_for", name=character.name),
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
        embed.set_footer(text=LocaleStr(key="card_settings.footer"))
        return embed

    async def start(self, i: Interaction) -> None:
        embed = self.get_settings_embed()
        await i.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await i.original_response()


class CharacterSelect(SettingsCharacterSelect[CardSettingsView]):
    async def callback(self, i: Interaction) -> None:
        changed = self.update_page()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        self.view.selected_character_id = self.values[0]
        self.view.card_settings = await get_card_settings(
            self.view._user_id, self.values[0], game=self.view.game
        )

        # Update other item styles
        template_select: CardTemplateSelect = self.view.get_item("profile_card_template_select")
        template_select.update_options_defaults(values=[self.view.card_settings.template])

        dark_mode_button: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_button.current_toggle = self.view.card_settings.dark_mode
        dark_mode_button.update_style()

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)
        return None


class DarkModeButton(ToggleButton[CardSettingsView]):
    def __init__(self, current_toggle: bool, disabled: bool, row: int) -> None:
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
    def __init__(self, current_color: str | None, disabled: bool, row: int) -> None:
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
        await modal.wait()
        if modal.incomplete:
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

        templates = CARD_TEMPLATES[game]
        for template in templates:
            template_id = template.rstrip("1234567890")
            if hb_only and template_id != "hb":
                continue

            author1, author2 = CARD_TEMPLATE_AUTHORS[template_id]
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

            template_name = CARD_TEMPLATE_NAMES[template_id]
            label = LocaleStr(key=template_name, num=int(template[-1]))

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

        change_color_btn: PrimaryColorButton = self.view.get_item("profile_primary_color")
        change_color_btn.disabled = self.view.disable_color_features

        dark_mode_btn: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_btn.disabled = self.view.disable_dark_mode_features

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
                template=LocaleStr(key=CARD_TEMPLATE_NAMES[template], num=template_num),
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class ShowRankButton(ToggleButton[CardSettingsView]):
    def __init__(self, current_toggle: bool, disabled: bool, row: int) -> None:
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
