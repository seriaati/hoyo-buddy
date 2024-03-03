import asyncio
import pickle
from io import BytesIO
from typing import TYPE_CHECKING, Any

from discord import ButtonStyle, File, TextStyle
from discord.utils import get as dget
from enka import Language as EnkaLang
from mihomo.models import Character as HSRCharacter

from hoyo_buddy.ui.components import SelectOption

from ...bot.emojis import (
    ADD,
    BOOK_MULTIPLE,
    DELETE,
    GENSHIN_ELEMENT_EMOJIS,
    HSR_ELEMENT_EMOJIS,
    INFO,
    SETTINGS,
)
from ...bot.translator import LocaleStr
from ...constants import ENKA_LANG_TO_CARD_API_LANG, ENKA_LANG_TO_LOCALE, MIHOMO_LANG_TO_LOCALE
from ...db.models import CardSettings, EnkaCache
from ...draw.hoyo.genshin.build_card import draw_genshin_card
from ...draw.hoyo.hsr.build_card import draw_build_card
from ...draw.static import download_and_save_static_images
from ...embeds import DefaultEmbed
from ...enums import Game
from ...exceptions import CardNotReadyError, InvalidColorError, InvalidImageURLError
from ...utils import is_image_url, is_valid_hex_color, test_url_validity, upload_image
from ..components import (
    Button,
    GoBackButton,
    Modal,
    PaginatorSelect,
    Select,
    TextInput,
    ToggleButton,
    View,
)

if TYPE_CHECKING:
    import io

    import aiohttp
    from discord import Locale, Member, User
    from enka.models import Character as GICharacter
    from enka.models import ShowcaseResponse
    from mihomo.models import StarrailInfoParsed

    from hoyo_buddy.bot.translator import Translator

    from ...bot.bot import INTERACTION


class ProfileView(View):
    def __init__(
        self,
        uid: int,
        game: "Game",
        cache_extras: dict[str, dict[str, Any]],
        card_data: dict[str, Any],
        star_rail_data: "StarrailInfoParsed" = None,  # type: ignore
        genshin_data: "ShowcaseResponse" = None,  # type: ignore
        *,
        author: "User | Member",
        locale: "Locale",
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self.star_rail_data = star_rail_data
        self.genshin_data = genshin_data

        if game is Game.STARRAIL:
            self.live_data_character_ids = [
                char.id for char in star_rail_data.characters if cache_extras[char.id]["live"]
            ]
        else:
            self.live_data_character_ids = [
                str(char.id)
                for char in genshin_data.characters
                if cache_extras[str(char.id)]["live"]
            ]

        self.uid = uid
        self.game = game
        self.cache_extras = cache_extras

        self.character_id: str | None = None

        self._card_settings: CardSettings | None = None
        self._card_data = card_data

    @property
    def player_embed(self) -> DefaultEmbed:
        if self.game is Game.STARRAIL:
            player = self.star_rail_data.player
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=player.name,
                description=LocaleStr(
                    "Trailblaze Level: {level}\n"
                    "Equilibrium Level: {world_level}\n"
                    "Friend Count: {friend_count}\n"
                    "Light Cones: {light_cones}\n"
                    "Characters: {characters}\n"
                    "Achievements: {achievements}\n",
                    key="profile.player_info.embed.description",
                    level=player.level,
                    world_level=player.world_level,
                    friend_count=player.friend_count,
                    light_cones=player.light_cones,
                    characters=player.characters,
                    achievements=player.achievements,
                ),
            )
            embed.set_thumbnail(url=player.avatar.icon)
            if player.signature:
                embed.set_footer(text=player.signature)
        else:
            player = self.genshin_data.player
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=player.nickname,
                description=LocaleStr(
                    "Adventure Rank: {adventure_rank}\n"
                    "Characters: {characters}\n"
                    "Spiral Abyss: {spiral_abyss}\n"
                    "Achievements: {achievements}\n",
                    key="profile.player_info.embed.description",
                    adventure_rank=player.level,
                    characters=len(player.showcase_characters),
                    spiral_abyss=f"{player.abyss_level}-{player.abyss_floor}",
                    achievements=player.achievements,
                ),
            )
            embed.set_thumbnail(url=player.profile_picture_icon.circle)
            embed.set_image(url=player.namecard.full)
            if player.signature:
                embed.set_footer(text=player.signature)
        return embed

    def _add_items(self) -> None:
        self.add_item(PlayerButton())
        self.add_item(CardSettingsButton())
        self.add_item(RemoveFromCacheButton())
        self.add_item(CardInfoButton())
        self.add_item(
            CharacterSelect(
                self.star_rail_data.characters
                if self.game is Game.STARRAIL
                else self.genshin_data.characters,
                self.cache_extras,
            )
        )

    async def _draw_src_character_card(
        self,
        uid: int,
        character: "HSRCharacter",
        template: str,
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        template_num = int(template[-1])
        payload = {
            "uid": uid,
            "lang": self.cache_extras[character.id]["lang"],
            "template": template_num,
            "character_name": character.name,
            "character_art": self._card_settings.current_image,
        }
        endpoint = "http://localhost:7652/star-rail-card"

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_enka_card(
        self,
        uid: int,
        character: "GICharacter",
        session: "aiohttp.ClientSession",
        template: str,
    ) -> BytesIO:
        """Draw character card in StarRailCard template."""
        assert self._card_settings is not None

        payload = {
            "uid": uid,
            "lang": ENKA_LANG_TO_CARD_API_LANG[
                EnkaLang(self.cache_extras[str(character.id)]["lang"])
            ],
            "character_id": str(character.id),
            "character_art": self._card_settings.current_image,
        }
        if template == "hattvr1":
            del payload["character_art"]
            endpoint = "http://localhost:7652/hattvr-enka-card"
        elif "enkacard" in template:
            payload["template"] = int(template[-1])
            endpoint = "http://localhost:7652/enka-card"
        elif template == "encard1":
            del payload["character_id"]
            payload["character_name"] = character.name
            endpoint = "http://localhost:7652/en-card"
        else:
            msg = f"Invalid template: {template}"
            raise NotImplementedError(msg)

        async with session.post(endpoint, json=payload) as resp:
            # API returns a WebP image
            resp.raise_for_status()
            return BytesIO(await resp.read())

    async def _draw_hb_hsr_character_card(
        self,
        character: "HSRCharacter",
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw Star Rail character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        character_data = self._card_data.get(character.id)
        if character_data is None:
            raise CardNotReadyError(character.name)

        art = self._card_settings.current_image or character_data["arts"][0]

        urls = await self._retrieve_hsr_image_urls(character, art)
        await download_and_save_static_images(list(urls), "hsr-build-card", session)

        if self._card_settings.custom_primary_color is None:
            primary = character_data["primary"]
            if "primary-dark" in character_data and self._card_settings.dark_mode:
                primary = character_data["primary-dark"]
            self._card_settings.custom_primary_color = primary

        return await asyncio.to_thread(
            draw_build_card,
            character,
            MIHOMO_LANG_TO_LOCALE[self.cache_extras[character.id]["lang"]],
            self._card_settings.dark_mode,
            art,
            self._card_settings.custom_primary_color,
        )

    async def _draw_hb_gi_character_card(
        self,
        character: "GICharacter",
        session: "aiohttp.ClientSession",
    ) -> BytesIO:
        """Draw Genshin Impact character card in Hoyo Buddy template."""
        assert self._card_settings is not None

        character_data = self._card_data.get(str(character.id))
        if character_data is None:
            raise CardNotReadyError(character.name)

        art = self._card_settings.current_image or character_data["arts"][0]

        urls = await self._retrieve_genshin_image_urls(character, art)
        await download_and_save_static_images(list(urls), "gi-build-card", session)

        return await asyncio.to_thread(
            draw_genshin_card,
            ENKA_LANG_TO_LOCALE[EnkaLang(self.cache_extras[str(character.id)]["lang"])],
            self._card_settings.dark_mode,
            character,
            art,
        )

    async def _retrieve_hsr_image_urls(self, character: "HSRCharacter", art: str) -> set[str]:
        """Retrieve all image URLs needed to draw the HSR card."""
        urls: set[str] = set()
        urls.add(art)
        for trace in character.traces:
            urls.add(trace.icon)
        for trace in character.trace_tree:
            urls.add(trace.icon)
        for relic in character.relics:
            urls.add(relic.icon)
            urls.add(relic.main_affix.icon)
            for affix in relic.sub_affixes:
                urls.add(affix.icon)
        for attr in character.attributes:
            urls.add(attr.icon)
        for addition in character.additions:
            urls.add(addition.icon)
        if character.light_cone is not None:
            urls.add(character.light_cone.portrait)
            for attr in character.light_cone.attributes:
                urls.add(attr.icon)
        urls.add(
            "https://raw.githubusercontent.com/Mar-7th/StarRailRes/master/icon/property/IconEnergyRecovery.png"
        )

        return urls

    async def _retrieve_genshin_image_urls(self, character: "GICharacter", art: str) -> set[str]:
        urls: set[str] = set()
        urls.add(art)
        urls.add(character.weapon.icon)
        urls.add(character.icon.gacha)
        for artifact in character.artifacts:
            urls.add(artifact.icon)
        for talent in character.talents:
            urls.add(talent.icon)
        for constellation in character.constellations:
            urls.add(constellation.icon)

        return urls

    async def draw_card(self, i: "INTERACTION") -> "io.BytesIO":
        """Draw the character card and return the bytes object."""
        assert self.character_id is not None

        if self.game is Game.STARRAIL:
            character = dget(self.star_rail_data.characters, id=self.character_id)
        else:
            character = dget(self.genshin_data.characters, id=int(self.character_id))

        if character is None:
            msg = f"Character not found: {self.character_id}"
            raise ValueError(msg)

        # Initialize card settings
        card_settings = await CardSettings.get_or_none(
            user_id=i.user.id, character_id=self.character_id
        )
        if card_settings is None:
            card_settings = await CardSettings.create(
                user_id=i.user.id, character_id=self.character_id, dark_mode=False
            )
        self._card_settings = card_settings

        # Force change the template to hb1 if is cached data
        if (
            not self.cache_extras[self.character_id]["live"]
            and "hb" not in self._card_settings.template
        ):
            self._card_settings.template = "hb1"
            await self._card_settings.save()

        template = self._card_settings.template

        if isinstance(character, HSRCharacter):
            if "hb" in template:
                bytes_obj = await self._draw_hb_hsr_character_card(character, i.client.session)
            else:
                bytes_obj = await self._draw_src_character_card(
                    self.uid, character, template, i.client.session
                )
        elif "hb" in template:
            bytes_obj = await self._draw_hb_gi_character_card(character, i.client.session)
        else:
            bytes_obj = await self._draw_enka_card(self.uid, character, i.client.session, template)

        return bytes_obj

    async def start(self, i: "INTERACTION") -> None:
        self._add_items()
        await i.followup.send(embed=self.player_embed, view=self)
        self.message = await i.original_response()


class PlayerButton(Button[ProfileView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Player Info", key="profile.player_info.button.label"),
            style=ButtonStyle.blurple,
            emoji=BOOK_MULTIPLE,
        )

    async def callback(self, i: "INTERACTION") -> None:
        card_settings_btn = self.view.get_item("profile_card_settings")
        if card_settings_btn is not None:
            card_settings_btn.disabled = True

        await i.response.edit_message(embed=self.view.player_embed, attachments=[], view=self.view)


class CardInfoButton(Button[ProfileView]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=0)

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("About Star Rail Cards", key="profile.card_info.embed.title"),
            description=LocaleStr(
                "- Star Rail cards are a way to show off your character builds.\n"
                "- All assets used in the cards belong to Hoyoverse, I do not own them.\n"
                "- All fanarts used in the cards are credited to their respective artists.\n"
                "- This Hoyo Buddy template's design is original, you are not allowed to use it without permission.\n"
                "- Game data is provided by the [mihomo API](https://api.mihomo.me/).\n"
                "- Suggestions are welcome, you can contribute to the card data (adding fanarts, fixing colors, etc.) by reaching me in the [Discord Server](https://dsc.gg/hoyo-buddy).",
                key="profile.card_info.embed.description",
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class CharacterSelect(PaginatorSelect[ProfileView]):
    def __init__(
        self,
        characters: list["HSRCharacter"] | list["GICharacter"],
        cache_extras: dict[str, dict[str, Any]],
    ) -> None:
        options: list[SelectOption] = []

        for character in characters:
            data_type = (
                LocaleStr("Real-time data", key="profile.character_select.live_data.description")
                if cache_extras[str(character.id)]["live"]
                else LocaleStr(
                    "Cached data", key="profile.character_select.cached_data.description"
                )
            )
            if isinstance(character, HSRCharacter):
                description = LocaleStr(
                    "Lv. {level} | E{eidolons}S{superposition} | {data_type}",
                    key="profile.character_select.description",
                    level=character.level,
                    superposition=character.light_cone.superimpose if character.light_cone else 0,
                    eidolons=character.eidolon,
                    data_type=data_type,
                )
                emoji = HSR_ELEMENT_EMOJIS[character.element.id.lower()]
            else:
                description = LocaleStr(
                    "Lv. {level} | C{const}R{refine} | {data_type}",
                    key="profile.genshin.character_select.description",
                    level=character.level,
                    const=character.constellations_unlocked,
                    refine=character.weapon.refinement,
                    data_type=data_type,
                )
                emoji = GENSHIN_ELEMENT_EMOJIS[character.element.name.lower()]

            options.append(
                SelectOption(
                    label=character.name,
                    description=description,
                    value=str(character.id),
                    emoji=emoji,
                )
            )

        super().__init__(
            options,
            placeholder=LocaleStr("Select a character", key="profile.character_select.placeholder"),
            custom_id="profile_character_select",
        )

    async def callback(self, i: "INTERACTION") -> None:
        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.view.character_id = self.values[0]

        card_settings_btn = self.view.get_item("profile_card_settings")
        card_settings_btn.disabled = False

        remove_from_cache_btn = self.view.get_item("profile_remove_from_cache")
        remove_from_cache_btn.disabled = self.view.character_id in self.view.live_data_character_ids

        self.update_options_defaults()
        await self.set_loading_state(i)

        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)

        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class CardSettingsButton(Button[ProfileView]):
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
                self.view.character_id in self.view.live_data_character_ids,
                self.view.game,
            )
        )
        self.view.add_item(
            PrimaryColorButton(
                self.view._card_settings.custom_primary_color,
                "hb" not in self.view._card_settings.template,
            )
        )
        self.view.add_item(
            DarkModeButton(
                self.view._card_settings.dark_mode, "hb" not in self.view._card_settings.template
            )
        )
        self.view.add_item(CardSettingsInfoButton())
        self.view.add_item(AddImageButton())
        self.view.add_item(
            RemoveImageButton(self.view._card_settings.current_image in default_arts)
        )

        await i.response.edit_message(view=self.view)


class RemoveFromCacheButton(Button[ProfileView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Remove from Cache", key="profile.remove_from_cache.button.label"),
            style=ButtonStyle.red,
            emoji=DELETE,
            row=3,
            disabled=True,
            custom_id="profile_remove_from_cache",
        )

    async def callback(self, i: "INTERACTION") -> None:
        cache = await EnkaCache.get(uid=self.view.uid)

        if self.view.game is Game.STARRAIL and cache.hsr is not None:
            hsr_cache: StarrailInfoParsed = pickle.loads(cache.hsr)
            for character in hsr_cache.characters:
                if character.id == self.view.character_id:
                    hsr_cache.characters.remove(character)
                    break
        elif self.view.game is Game.GENSHIN and cache.genshin is not None:
            gi_cache: ShowcaseResponse = pickle.loads(cache.genshin)
            for character in gi_cache.characters:
                if character.id == self.view.character_id:
                    gi_cache.characters.remove(character)
                    break
        await cache.save()

        character_select: CharacterSelect = self.view.get_item("profile_character_select")
        for option in character_select.options_before_split:
            if option.value == self.view.character_id:
                character_select.options_before_split.remove(option)
                break
        character_select.options = character_select.process_options()
        self.view.character_id = self.view.star_rail_data.characters[0].id
        character_select.update_options_defaults(values=[self.view.character_id])
        character_select.translate(self.view.locale, self.view.translator)

        await self.set_loading_state(i)
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class PrimaryColorButton(Button[ProfileView]):
    def __init__(self, current_color: str | None, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr("Change Color", key="profile.primary_color.button.label"),
            style=ButtonStyle.blurple,
            row=2,
            custom_id="profile_primary_color",
            disabled=disabled,
        )
        self.current_color = current_color

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        modal = PrimaryColorModal(self.current_color)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        color = modal.color.value
        if not color:
            return

        # Test if the color is valid
        passed = is_valid_hex_color(color)
        if not passed:
            raise InvalidColorError

        self.view._card_settings.custom_primary_color = modal.color.value
        await self.view._card_settings.save()

        await self.set_loading_state(i)
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class PrimaryColorModal(Modal):
    color = TextInput(
        label=LocaleStr("Color (hex code)", key="profile.primary_color_modal.color.label"),
        placeholder="#000000",
        style=TextStyle.short,
        min_length=7,
        max_length=7,
    )

    def __init__(self, current_color: str | None) -> None:
        super().__init__(
            title=LocaleStr("Change Card Color", key="profile.primary_color_modal.title")
        )
        self.color.default = current_color


class DarkModeButton(ToggleButton[ProfileView]):
    def __init__(self, current_toggle: bool, disabled: bool) -> None:
        super().__init__(
            current_toggle,
            LocaleStr("Dark Mode", key="profile.dark_mode.button.label"),
            row=2,
            custom_id="profile_dark_mode",
            disabled=disabled,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        await super().callback(i, edit=False)
        self.view._card_settings.dark_mode = self.current_toggle
        await self.view._card_settings.save()

        await self.set_loading_state(i)
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class ImageSelect(PaginatorSelect[ProfileView]):
    def __init__(
        self,
        current_image_url: str | None,
        default_collection: list[str],
        custom_images: list[str],
        disabled: bool,
    ) -> None:
        self.current_image_url = current_image_url
        self.default_collection = default_collection
        self.custom_images = custom_images

        super().__init__(
            self.generate_options(),
            placeholder=LocaleStr("Select an image", key="profile.image_select.placeholder"),
            custom_id="profile_image_select",
            row=0,
            disabled=disabled,
        )

    def generate_options(self) -> list[SelectOption]:
        options: list[SelectOption] = [
            SelectOption(
                label=LocaleStr("Official Art", key="profile.image_select.none.label"),
                description=LocaleStr(
                    "Doesn't work with Hoyo Buddy's template",
                    key="profile.image_select.none.description",
                ),
                value="none",
                default=self.current_image_url is None,
            )
        ]
        added_values: set[str] = set()

        for collection in [self.default_collection, self.custom_images]:
            for index, url in enumerate(collection, start=1):
                if url not in added_values:
                    options.append(self.get_image_url_option(url, index))
                    added_values.add(url)

        return options

    def get_image_url_option(self, image_url: str, num: int) -> SelectOption:
        option = SelectOption(
            label=LocaleStr(
                "Hoyo Buddy Collection ({num})",
                key="profile.image_select.default_collection.label",
                num=num,
            )
            if image_url in self.default_collection
            else LocaleStr(
                "Custom Image ({num})",
                key="profile.image_select.custom_image.label",
                num=num,
            ),
            value=image_url,
            description=image_url[:100],
            default=image_url == self.current_image_url,
        )
        return option

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        changed = await super().callback()
        if changed:
            return await i.response.edit_message(view=self.view)

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Update the current image URL in db.
        self.view._card_settings.current_image = (
            None if self.values[0] == "none" else self.values[0]
        )
        await self.view._card_settings.save()

        # Enable the remove image button if the image is custom
        remove_image_button: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_image_button.disabled = self.values[0] in self.default_collection

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class AddImageButton(Button[ProfileView]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Add Custom Image", key="profile.add_image.button.label"),
            style=ButtonStyle.green,
            emoji=ADD,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view._card_settings is not None

        modal = AddImageModal()
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        await self.set_loading_state(i)

        image_url = modal.image_url.value
        if not image_url:
            return

        # Check if the image URL is valid.
        passed = is_image_url(image_url)
        if not passed:
            raise InvalidImageURLError
        passed = await test_url_validity(image_url, i.client.session)
        if not passed:
            raise InvalidImageURLError

        try:
            url = await upload_image(image_url, i.client.session)
        except Exception as e:
            raise InvalidImageURLError from e

        # Add the image URL to db.
        self.view._card_settings.custom_images.append(url)
        self.view._card_settings.current_image = url
        await self.view._card_settings.save()

        # Update the image select options.
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        image_select.update_options_defaults(values=[url])
        image_select.translate(self.view.locale, self.view.translator)

        # Enable the remove image button
        remove_img_btn: RemoveImageButton = self.view.get_item("profile_remove_image")
        remove_img_btn.disabled = False

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class AddImageModal(Modal):
    image_url = TextInput(
        label=LocaleStr("Image URL", key="profile.add_image_modal.image_url.label"),
        placeholder="https://example.com/image.png",
        style=TextStyle.short,
        max_length=100,
    )

    def __init__(self) -> None:
        super().__init__(title=LocaleStr("Add Custom Image", key="profile.add_image_modal.title"))


class RemoveImageButton(Button[ProfileView]):
    def __init__(self, disabled: bool) -> None:
        super().__init__(
            label=LocaleStr("Remove Custom Image", key="profile.remove_image.button.label"),
            style=ButtonStyle.red,
            disabled=disabled,
            custom_id="profile_remove_image",
            emoji=DELETE,
            row=3,
        )

    async def callback(self, i: "INTERACTION") -> None:
        assert self.view.character_id is not None
        assert self.view._card_settings is not None
        assert self.view._card_settings.current_image is not None

        await self.set_loading_state(i)

        new_image_url = self.view._card_data[self.view.character_id]["arts"][0]

        # Remove the current image URL from db.
        self.view._card_settings.custom_images.remove(self.view._card_settings.current_image)
        self.view._card_settings.current_image = new_image_url
        await self.view._card_settings.save()

        # Update the image select options.
        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.options_before_split = image_select.generate_options()
        image_select.options = image_select.process_options()
        image_select.update_options_defaults(values=[new_image_url])
        image_select.translate(self.view.locale, self.view.translator)

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class CardTemplateSelect(Select[ProfileView]):
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
                        "Designed and programmed by @seria_ati",
                        key="profile.card_template_select.hb.description",
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
                                "Designed and programmed by @korzzex",
                                key="profile.card_template_select.src.description",
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
                                "Designed and programmed by @hattvr",
                                key="profile.card_template_select.enka_classic.description",
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
                                "Designed and programmed by @korzzex",
                                key="profile.card_template_select.encard.description",
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
                                "Designed and programmed by @korzzex",
                                key="profile.card_template_select.enkacard.description",
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
        self.view._card_settings.template = self.values[0]
        await self.view._card_settings.save()

        self.update_options_defaults()
        await self.set_loading_state(i)

        change_color_btn: PrimaryColorButton = self.view.get_item("profile_primary_color")
        change_color_btn.disabled = (
            "hb" not in self.values[0] and self.view.game is not Game.STARRAIL
        )

        dark_mode_btn: DarkModeButton = self.view.get_item("profile_dark_mode")
        dark_mode_btn.disabled = "hb" not in self.values[0]

        image_select: ImageSelect = self.view.get_item("profile_image_select")
        image_select.disabled = self.values[0] == "hattvr1"

        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )


class CardSettingsInfoButton(Button[ProfileView]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=2)

    async def callback(self, i: "INTERACTION") -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("About Card Settings", key="profile.info.embed.title"),
        )
        embed.add_field(
            name=LocaleStr("Primary Color", key="profile.info.embed.primary_color.name"),
            value=LocaleStr(
                "- Only hex color codes are supported.",
                key="profile.info.embed.primary_color.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Dark Mode", key="profile.info.embed.dark_mode.name"),
            value=LocaleStr(
                "- This setting is independent from the one in </settings>, defaults to light mode.\n"
                "- Light mode cards tend to look better because the colors are not optimized for dark mode.\n"
                "- Suggestions for dark mode colors are welcome!",
                key="profile.info.embed.dark_mode.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Custom Images", key="profile.info.embed.custom_images.name"),
            value=LocaleStr(
                "- Hoyo Buddy comes with some preset arts that I liked, but you can add your own images too.\n"
                "- Only direct image URLs are supported, and they must be publicly accessible; GIFs are not supported.\n"
                "- For Hoyo Buddy's template, vertical images are recommended, the exact size is 640x1138 pixels, crop your image if the position is not right.\n"
                "- For server owners, I am not responsible for any NSFW images that you or your members add.\n"
                "- The red button removes the current custom image and reverts to the default one.",
                key="profile.info.embed.custom_images.value",
            ),
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Templates", key="profile.info.embed.templates.name"),
            value=LocaleStr(
                "- Hoyo Buddy has its own template made by me, but I also added templates made by other developers.\n"
                "- Code of 3rd party templates are not maintained by me, so I cannot guarantee their quality; I am also not responsible for any issues with them.\n"
                "- 3rd party templates may have feature limitations compared to Hoyo Buddy's.\n"
                "- Cached data characters can only use Hoyo Buddy's template.",
                key="profile.info.embed.templates.value",
            ),
            inline=False,
        )
        await i.response.send_message(embed=embed, ephemeral=True)
