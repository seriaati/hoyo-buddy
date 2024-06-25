from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import EnumStr, Translator
from hoyo_buddy.constants import GAME_LB_TYPES
from hoyo_buddy.ui import Select, SelectOption, View

if TYPE_CHECKING:
    from discord import Locale, Member, User

    from hoyo_buddy.enums import Game


class LeaderboardView(View):
    def __init__(
        self,
        uid: int,
        game: "Game",
        *,
        author: "User | Member | None",
        locale: "Locale",
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)

        self._uid = uid
        self._game = game


class LBTypeSelector(Select):
    def __init__(self, game: "Game") -> None:
        super().__init__(
            options=[
                SelectOption(
                    label=EnumStr(lb_type),
                    value=lb_type.value,
                )
                for lb_type in GAME_LB_TYPES[game]
            ]
        )
