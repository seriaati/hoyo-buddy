from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import genshin
from pydantic import BaseModel, Field


class ZZZGachaEventWeapon(genshin.models.ZZZGachaEventWeapon):
    name: str


class ZZZWeaponGachaEvent(genshin.models.ZZZWeaponGachaEvent):
    weapons: Sequence[ZZZGachaEventWeapon]  # pyright: ignore[reportGeneralTypeIssues]


class ZZZEventCalendar(BaseModel):
    events: Sequence[genshin.models.ZZZEvent]
    characters: Sequence[genshin.models.ZZZCharacterGachaEvent]
    weapons: Sequence[ZZZWeaponGachaEvent]

    # Not used, doesn't exist, just for compatibility with other EventCalendars
    challenges: Sequence[Any] = Field(default_factory=list)
