from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.constants import (
    ASCENDED_LEVEL_TO_ASCENSION,
    ASCENSION_TO_MAX_LEVEL,
    NOT_ASCENDED_LEVEL_TO_ASCENSION,
)

if TYPE_CHECKING:
    from hoyo_buddy.enums import Game


def get_ascension_from_level(level: int, ascended: bool, game: Game) -> int:
    """Get the ascension from the level and ascended status.

    Args:
        level: The level.
        ascended: Whether the entity is ascended.
        game: The game.

    Returns:
        The ascension level.
    """
    if not ascended and level in NOT_ASCENDED_LEVEL_TO_ASCENSION[game]:
        return NOT_ASCENDED_LEVEL_TO_ASCENSION[game][level]

    for (start, end), ascension in ASCENDED_LEVEL_TO_ASCENSION[game].items():
        if start <= level <= end:
            return ascension

    return 0


def get_max_level_from_ascension(ascension: int, game: Game) -> int:
    """Get the max level from the ascension.

    Args:
        ascension: The ascension level.
        game: The game.

    Returns:
        The max level.
    """
    return ASCENSION_TO_MAX_LEVEL[game][ascension]
