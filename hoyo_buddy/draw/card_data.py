from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from seria.utils import read_yaml

from hoyo_buddy.models.draw import GICardData, HSRCardData, ZZZTemp1CardData, ZZZTemp2CardData

ASSET_PATH = Path("hoyo-buddy-assets/assets")
GI_DATA = ASSET_PATH / "gi-build-card/data.yaml"
HSR_DATA = ASSET_PATH / "hsr-build-card/data.yaml"
ZZZ_DATA = ASSET_PATH / "zzz-build-card/agent_data.yaml"
ZZZ_DATA2 = ASSET_PATH / "zzz-build-card/agent_data_temp2.yaml"


class CardDataManager:
    def __init__(self) -> None:
        self._gi: dict[str, GICardData] | None = None
        self._hsr: dict[str, HSRCardData] | None = None
        self._zzz: dict[str, ZZZTemp1CardData] | None = None
        self._zzz2: dict[str, ZZZTemp2CardData] | None = None

    def _parse_model[T: BaseModel](self, data: dict[str, Any], model: type[T]) -> dict[str, T]:
        return {k: model.model_validate(v) for k, v in data.items()}

    async def load(self) -> None:
        self._gi = self._parse_model(await read_yaml(GI_DATA), GICardData)
        self._hsr = self._parse_model(await read_yaml(HSR_DATA), HSRCardData)
        self._zzz = self._parse_model(await read_yaml(ZZZ_DATA), ZZZTemp1CardData)
        self._zzz2 = self._parse_model(await read_yaml(ZZZ_DATA2), ZZZTemp2CardData)

    @property
    def zzz(self) -> dict[str, ZZZTemp1CardData]:
        if self._zzz is None:
            msg = "ZZZ card data is not loaded"
            raise ValueError(msg)
        return self._zzz.copy()

    @property
    def zzz2(self) -> dict[str, ZZZTemp2CardData]:
        if self._zzz2 is None:
            msg = "ZZZ temp2 card data is not loaded"
            raise ValueError(msg)
        return self._zzz2.copy()

    @property
    def gi(self) -> dict[str, GICardData]:
        if self._gi is None:
            msg = "GI card data is not loaded"
            raise ValueError(msg)
        return self._gi.copy()

    @property
    def hsr(self) -> dict[str, HSRCardData]:
        if self._hsr is None:
            msg = "HSR card data is not loaded"
            raise ValueError(msg)
        return self._hsr.copy()


CARD_DATA = CardDataManager()
