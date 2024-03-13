from typing import TYPE_CHECKING, Any

from discord import File
from mihomo.models import Character as HSRCharacter

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.emojis import get_gi_element_emoji, get_hsr_element_emoji
from hoyo_buddy.ui.components import PaginatorSelect, SelectOption

if TYPE_CHECKING:
    from enka.models import Character as GICharacter

    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class CharacterSelect(PaginatorSelect["ProfileView"]):
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
                    "Lv.{level} | E{eidolons}S{superposition} | {data_type}",
                    key="profile.character_select.description",
                    level=character.level,
                    superposition=character.light_cone.superimpose if character.light_cone else 0,
                    eidolons=character.eidolon,
                    data_type=data_type,
                )
                emoji = get_hsr_element_emoji(character.element.id)
            else:
                description = LocaleStr(
                    "Lv.{level} | C{const}R{refine} | {data_type}",
                    key="profile.genshin.character_select.description",
                    level=character.level,
                    const=character.constellations_unlocked,
                    refine=character.weapon.refinement,
                    data_type=data_type,
                )
                emoji = get_gi_element_emoji(character.element.name)

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

        # Enable the card settings button
        card_settings_btn = self.view.get_item("profile_card_settings")
        card_settings_btn.disabled = False

        # Enable the remove from cache button if the character is in the cache
        remove_from_cache_btn = self.view.get_item("profile_remove_from_cache")
        remove_from_cache_btn.disabled = self.view.character_id in self.view.live_data_character_ids

        self.update_options_defaults()
        await self.set_loading_state(i)

        # Redraw the card
        bytes_obj = await self.view.draw_card(i)
        bytes_obj.seek(0)
        await self.unset_loading_state(
            i, attachments=[File(bytes_obj, filename="card.webp")], embed=None
        )
