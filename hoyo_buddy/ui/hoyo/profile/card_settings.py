from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

import enka
from discord import ButtonStyle, TextStyle
from genshin.models import ZZZPartialAgent
from seria.utils import read_json, read_yaml

from hoyo_buddy.constants import HSR_DEFAULT_ART_URL
from hoyo_buddy.db.models import CardSettings, Settings
from hoyo_buddy.embeds import DefaultEmbed, Embed
from hoyo_buddy.emojis import (
    ADD,
    DELETE,
    PALETTE,
    PHOTO_ADD,
    get_gi_element_emoji,
    get_hsr_element_emoji,
    get_zzz_element_emoji,
)
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import (
    GuildOnlyFeatureError,
    InvalidColorError,
    InvalidImageURLError,
    NSFWPromptError,
)
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.ui import (
    Button,
    Modal,
    PaginatorSelect,
    Select,
    SelectOption,
    TextInput,
    ToggleButton,
    View,
)
from hoyo_buddy.utils import (
    get_pixiv_proxy_img,
    is_image_url,
    is_valid_hex_color,
    test_url_validity,
    upload_image,
)

from .btn_states import DISABLE_COLOR, DISABLE_DARK_MODE, DISABLE_IMAGE

if TYPE_CHECKING:
    from collections.abc import Sequence

    from discord import Locale, Member, User

    from hoyo_buddy.l10n import Translator
    from hoyo_buddy.types import Interaction

    from .view import Character

CARD_TEMPLATES: Final[dict[Game, tuple[str, ...]]] = {
    Game.GENSHIN: ("hb1", "hb2", "hattvr1", "encard1", "enkacard1", "enkacard2"),
    Game.STARRAIL: ("hb1", "src1", "src2", "src3"),
    Game.ZZZ: ("hb1", "hb2"),
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
            user_id=user_id,
            character_id=character_id,
            dark_mode=False,
            template=template,
        )

    return card_settings


async def get_art_url(user_id: int, character_id: str, *, game: Game) -> str | None:
    card_settings = await get_card_settings(user_id, character_id, game=game)
    return card_settings.current_image


def get_default_art(character: Character) -> str:
    if isinstance(character, ZZZPartialAgent):
        return character.banner_icon
    if isinstance(character, enka.gi.Character):
        if character.costume is not None:
            return character.costume.icon.gacha
        return character.icon.gacha
    return HSR_DEFAULT_ART_URL.format(char_id=character.id)


async def get_card_data(game: Game) -> dict[str, Any]:
    asset_path = "hoyo-buddy-assets/assets"
    if game is Game.GENSHIN:
        return await read_yaml(f"{asset_path}/gi-build-card/data.yaml")
    if game is Game.STARRAIL:
        return await read_yaml(f"{asset_path}/hsr-build-card/data.yaml")
    if game is Game.ZZZ:
        return await read_yaml(f"{asset_path}/zzz-build-card/agent_data.yaml")

    msg = f"Game {game!r} does not have card data."
    raise ValueError(msg)


def get_default_color(character: Character, card_data: dict[str, Any]) -> str | None:
    chara_key = str(character.id)
    if isinstance(character, ZZZPartialAgent):
        return card_data[chara_key]["color"]
    if isinstance(character, enka.hsr.Character):
        return card_data[chara_key]["primary"]
    return None


def get_default_collection(
    character_id: str, card_data: dict[str, Any], *, game: Game
) -> list[str]:
    if game is Game.ZZZ:
        return []
    return card_data[character_id]["arts"]


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
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

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

    @property
    def disable_image_features(self) -> bool:
        return (
            self.game is Game.ZZZ and not self._is_team
        ) or self.card_settings.template in DISABLE_IMAGE

    @property
    def disable_ai_features(self) -> bool:
        return self.game is Game.ZZZ or self.card_settings.template in DISABLE_IMAGE

    @property
    def disable_color_features(self) -> bool:
        return self.game is Game.GENSHIN or self.card_settings.template in DISABLE_COLOR

    @property
    def disable_dark_mode_features(self) -> bool:
        return self.game is Game.ZZZ or self.card_settings.template in DISABLE_DARK_MODE

    def _add_items(self) -> None:
        character = self._get_current_character()
        default_collection = get_default_collection(
            str(character.id), self._card_data, game=self.game
        )

        self.add_item(
            CharacterSelect(
                characters=self._characters,
                character_id=self.selected_character_id,
                row=0,
            )
        )
        self.add_item(
            ImageSelect(
                current_image_url=self.card_settings.current_image,
                default_collection=default_collection,
                custom_images=self.card_settings.custom_images,
                template=self.card_settings.template,
                disabled=self.disable_image_features,
                row=1,
            )
        )
        self.add_item(
            CardTemplateSelect(
                self.card_settings.template,
                hb_only=self._hb_template_only,
                game=self.game,
                row=2,
            )
        )

        self.add_item(GenerateAIArtButton(disabled=self.disable_ai_features, row=3))
        self.add_item(AddImageButton(row=3, disabled=self.disable_image_features))
        self.add_item(
            RemoveImageButton(
                disabled=self.card_settings.current_image is None
                or self.card_settings.current_image in default_collection,
                row=3,
            )
        )

        self.add_item(
            PrimaryColorButton(
                self.card_settings.custom_primary_color, disabled=self.disable_color_features, row=4
            )
        )
        self.add_item(
            DarkModeButton(
                current_toggle=self.card_settings.dark_mode,
                disabled=self.disable_dark_mode_features,
                row=4,
            )
        )
        self.add_item(
            TeamCardDarkModeButton(
                self.settings.team_card_dark_mode,
                self.disable_dark_mode_features,
                row=4,
            )
        )
        self.add_item(SetCurTempAsDefaultButton(row=4))

    def _get_current_character(self) -> Character:
        return next(
            chara for chara in self._characters if str(chara.id) == self.selected_character_id
        )

    def get_settings_embed(self) -> Embed:
        card_settings = self.card_settings
        character = self._get_current_character()

        color = card_settings.custom_primary_color or get_default_color(character, self._card_data)
        embed = Embed(
            locale=self.locale,
            translator=self.translator,
            title=LocaleStr(key="card_settings.modifying_for", name=character.name),
            color=int(color.lstrip("#"), 16) if color is not None else 6649080,
        )
        default_str = LocaleStr(key="card_settings.color_default").translate(
            self.translator, self.locale
        )
        if color is not None:
            value = self._get_color_markdown(color)
            if card_settings.custom_primary_color is None:
                value += f" ({default_str})"
        else:
            value = LocaleStr(key="card_settings.no_color")

        embed.add_field(name=LocaleStr(key="card_settings.card_color"), value=value, inline=False)
        image_url = card_settings.current_image or get_default_art(character)
        embed.set_image(url=image_url)
        embed.add_field(
            name=LocaleStr(key="card_settings.current_image"), value=image_url, inline=False
        )

        embed.set_footer(text=LocaleStr(key="card_settings.footer"))
        return embed

    async def start(self, i: Interaction) -> None:
        embed = self.get_settings_embed()
        await i.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await i.original_response()


class CharacterSelect(PaginatorSelect[CardSettingsView]):
    def __init__(self, characters: Sequence[Character], character_id: str, row: int) -> None:
        self._characters = characters
        self._character_id = character_id

        options = self._get_options()
        super().__init__(
            options=options,
            placeholder=LocaleStr(key="profile.character_select.placeholder"),
            row=row,
        )

    @staticmethod
    def _get_chara_emoji(chara: Character) -> str:
        if isinstance(chara, ZZZPartialAgent):
            return get_zzz_element_emoji(chara.element)
        if isinstance(chara, enka.gi.Character):
            return get_gi_element_emoji(chara.element.name)
        return get_hsr_element_emoji(str(chara.element))

    def _get_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=chara.name,
                value=str(chara.id),
                emoji=self._get_chara_emoji(chara),
                default=str(chara.id) == self._character_id,
            )
            for chara in self._characters
        ]

    async def callback(self, i: Interaction) -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        self.view.selected_character_id = self.values[0]
        self.view.card_settings = await get_card_settings(
            self.view._user_id, self.values[0], game=self.view.game
        )
        default_arts = get_default_collection(
            self.values[0], self.view._card_data, game=self.view.game
        )
        custom_arts = self.view.card_settings.custom_images

        # Update other item styles
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(
            current_image=self.view.card_settings.current_image,
            custom_images=custom_arts,
            default_collection=default_arts,
        )

        template_select: CardTemplateSelect = self.view.get_item("profile_card_template_select")
        template_select.update_options_defaults(values=[self.view.card_settings.template])

        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = (
            self.view.card_settings.current_image is None
            or self.view.card_settings.current_image in default_arts
        )

        dark_mode_button: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_button.current_toggle = self.view.card_settings.dark_mode
        dark_mode_button.update_style()

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


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


class TeamCardDarkModeButton(ToggleButton[CardSettingsView]):
    def __init__(self, current_toggle: bool, disabled: bool, row: int) -> None:
        super().__init__(
            current_toggle,
            LocaleStr(key="profile.team_dark_mode.button.label"),
            custom_id="profile_team_dark_mode",
            disabled=disabled,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        await super().callback(i, edit=True)
        self.view.settings.team_card_dark_mode = self.current_toggle
        await Settings.filter(user_id=i.user.id).update(team_card_dark_mode=self.current_toggle)


class RemoveImageButton(Button[CardSettingsView]):
    def __init__(self, disabled: bool, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.remove_image.button.label"),
            style=ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        # Disable self
        self.disabled = True

        # Remove the current image URL
        current_image = self.view.card_settings.current_image
        if current_image is None:
            return

        if current_image in self.view.card_settings.custom_images:
            # For whatever reason, the current image may not be in the custom images list
            self.view.card_settings.custom_images.remove(current_image)

        # Update the current image URL
        self.view.card_settings.current_image = None
        self.view.card_settings.custom_images = list(set(self.view.card_settings.custom_images))
        await self.view.card_settings.save(update_fields=("custom_images", "current_image"))

        # Update image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=None, custom_images=self.view.card_settings.custom_images)

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


class ImageSelect(PaginatorSelect[CardSettingsView]):
    def __init__(
        self,
        current_image_url: str | None,
        default_collection: list[str],
        custom_images: list[str],
        template: str,
        disabled: bool,
        row: int,
    ) -> None:
        self.current_image_url = current_image_url
        self.default_collection = default_collection
        self.custom_images = custom_images
        self.template = template

        super().__init__(
            self.get_options(),
            placeholder=LocaleStr(key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
            disabled=disabled,
            row=row,
        )

    def update(
        self,
        *,
        current_image: str | None,
        custom_images: list[str],
        default_collection: list[str] | None = None,
    ) -> None:
        self.current_image_url = current_image
        self.custom_images = custom_images
        self.default_collection = default_collection or self.default_collection

        self.options_before_split = self.get_options()
        self.options = self.process_options()
        if current_image is not None:
            self.set_page_based_on_value(current_image)
        self.translate(self.view.locale, self.view.translator)

    def get_options(self) -> list[SelectOption]:
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr(key="profile.image_select.none.label"),
                value="none",
                default=self.current_image_url is None,
            )
        ]
        added_values: set[str] = set()

        for collection in [self.default_collection, self.custom_images]:
            for index, url in enumerate(collection, start=1):
                if url not in added_values:
                    options.append(self._get_select_option(url, index))
                    added_values.add(url)

        return options

    def _get_select_option(self, image_url: str, num: int) -> SelectOption:
        label = (
            LocaleStr(key="profile.image_select.default_collection.label", num=num)
            if image_url in self.default_collection
            else LocaleStr(key="profile.image_select.custom_image.label", num=num)
        )
        option = SelectOption(
            label=label,
            value=image_url,
            default=image_url == self.current_image_url,
        )
        return option

    async def callback(self, i: Interaction) -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()

        # Update the current image URL in db
        self.view.card_settings.current_image = None if self.values[0] == "none" else self.values[0]
        await self.view.card_settings.save(update_fields=("current_image",))

        # Enable the remove image button if the image is custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = (
            self.values[0] in self.default_collection or self.values[0] == "none"
        )

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


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
        modal.translate(self.view.locale, self.view.translator)
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


class GenerateAIArtButton(Button[CardSettingsView]):
    def __init__(self, disabled: bool, row: int) -> None:
        super().__init__(
            label=LocaleStr(key="profile.generate_ai_art.button.label"),
            style=ButtonStyle.blurple,
            custom_id="profile_generate_ai_art",
            disabled=disabled,
            row=row,
            emoji=PHOTO_ADD,
        )

    async def callback(self, i: Interaction) -> None:
        if i.guild is None:
            raise GuildOnlyFeatureError

        modal = GenerateAIArtModal(title=LocaleStr(key="profile.generate_ai_art.button.label"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
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
        self.view.card_settings.custom_images.append(url)
        self.view.card_settings.current_image = url
        await self.view.card_settings.save(update_fields=("custom_images", "current_image"))

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(current_image=url, custom_images=self.view.card_settings.custom_images)

        # Enable the remove image button
        remove_img_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_img_btn.disabled = False

        embed = self.view.get_settings_embed()
        await self.unset_loading_state(i, embed=embed)


class CardTemplateSelect(Select[CardSettingsView]):
    def __init__(self, current_template: str, hb_only: bool, game: Game, row: int) -> None:
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

        team_dark_mode_btn: TeamCardDarkModeButton = self.view.get_item("profile_team_dark_mode")
        team_dark_mode_btn.disabled = self.view.disable_dark_mode_features

        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.disabled = self.view.disable_image_features

        gen_ai_art_btn: GenerateAIArtButton = self.view.get_item("profile_generate_ai_art")
        gen_ai_art_btn.disabled = self.view.disable_ai_features

        embed = self.view.get_settings_embed()
        await i.response.edit_message(embed=embed, view=self.view)


class AddImageModal(Modal):
    image_url = TextInput(
        label=LocaleStr(key="profile.add_image_modal.image_url.label"),
        placeholder="https://example.com/image.png",
        style=TextStyle.short,
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr(key="profile.add_image.button.label"))


class AddImageButton(Button[CardSettingsView]):
    def __init__(self, row: int, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr(key="profile.add_image.button.label"),
            style=ButtonStyle.green,
            emoji=ADD,
            row=row,
            disabled=disabled,
        )

    async def callback(self, i: Interaction) -> None:
        # Open the modal
        modal = AddImageModal()
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()
        if modal.incomplete:
            return

        await self.set_loading_state(i)

        image_url = modal.image_url.value
        image_url = image_url.strip()

        # Pixiv image support
        if "i.pximg.net" in image_url:
            image_url = await get_pixiv_proxy_img(i.client.session, image_url)

        # Check if the image URL is valid
        passed = is_image_url(image_url)
        if not passed:
            await self.unset_loading_state(i)
            raise InvalidImageURLError
        passed = await test_url_validity(image_url, i.client.session)
        if not passed:
            await self.unset_loading_state(i)
            raise InvalidImageURLError

        if not image_url.startswith("https://iili.io"):
            # Upload the image to iili
            try:
                image_url = await upload_image(i.client.session, image_url=image_url)
            except Exception as e:
                await self.unset_loading_state(i)
                raise InvalidImageURLError from e

        # Add the image URL to db
        self.view.card_settings.custom_images.append(image_url)
        self.view.card_settings.custom_images = list(set(self.view.card_settings.custom_images))
        self.view.card_settings.current_image = image_url
        await self.view.card_settings.save(update_fields=("custom_images", "current_image"))

        # Add the new image URL to the image select options
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.update(
            current_image=image_url, custom_images=self.view.card_settings.custom_images
        )

        # Enable the remove image button
        self.view._item_states["profile_remove_image"] = False

        embed = self.view.get_settings_embed()
        await self.unset_loading_state(i, embed=embed)


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

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="set_cur_temp_as_default.done"),
            description=LocaleStr(key="set_cur_temp_as_default.done_desc"),
        )
        await i.response.send_message(embed=embed, ephemeral=True)
