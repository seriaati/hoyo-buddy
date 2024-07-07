from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..enums import Game
    from ..types import Interaction


class LeaderboardCommand:
    def __init__(self, interaction: Interaction, uid: int, game: Game) -> None:
        self._interaction = interaction
        self._uid = uid
        self._game = game
