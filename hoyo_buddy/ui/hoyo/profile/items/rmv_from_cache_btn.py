import pickle
from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import EnkaCache
from hoyo_buddy.emojis import DELETE
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.components import Button

if TYPE_CHECKING:
    from enka.models import ShowcaseResponse
    from mihomo.models import StarrailInfoParsed

    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401
    from .chara_select import CharacterSelect


class RemoveFromCacheButton(Button["ProfileView"]):
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

        # Remove the character from the cache
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

        # Update options in the character select
        character_select: CharacterSelect = self.view.get_item("profile_character_select")
        for option in character_select.options_before_split:
            # Remove the character from the options
            if option.value == self.view.character_id:
                character_select.options_before_split.remove(option)
                break

        character_select.options = character_select.process_options()
        self.view.character_id = str(self.view.characters[0].id)
        character_select.update_options_defaults(values=[self.view.character_id])
        character_select.translate(self.view.locale, self.view.translator)

        # Redraw the card
        await self.view.update(i, self)
