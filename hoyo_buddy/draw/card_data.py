from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel
from seria.utils import read_yaml

from hoyo_buddy.models.draw import GICardData, HSRCardData, ZZZCardData

ASSET_PATH = Path("hoyo-buddy-assets/assets")
GI_DATA = ASSET_PATH / "gi-build-card/data.yaml"
HSR_DATA = ASSET_PATH / "hsr-build-card/data.yaml"
ZZZ_DATA = ASSET_PATH / "zzz-build-card/agent_data.yaml"
ZZZ_DATA2 = ASSET_PATH / "zzz-build-card/agent_data_temp2.yaml"


class CardDataManager:
    def __init__(self) -> None:
        self._gi: CardDataDict | None = CardDataDict()
        self._hsr: CardDataDict | None = CardDataDict()
        self._zzz: CardDataDict | None = CardDataDict()
        self._zzz2: CardDataDict | None = CardDataDict()

    def _parse_model[T: BaseModel](self, data: dict[str, Any], model: type[T]) -> CardDataDict[T]:
        return CardDataDict({k: model.model_validate(v) for k, v in data.items()})

    async def load(self) -> None:
        self._gi = self._parse_model(await read_yaml(GI_DATA), GICardData)
        self._hsr = self._parse_model(await read_yaml(HSR_DATA), HSRCardData)
        self._zzz = self._parse_model(await read_yaml(ZZZ_DATA), ZZZCardData)
        self._zzz2 = self._parse_model(await read_yaml(ZZZ_DATA2), ZZZCardData)

    @property
    def zzz(self) -> CardDataDict[ZZZCardData]:
        if self._zzz is None:
            msg = "ZZZ card data is not loaded"
            raise ValueError(msg)
        return self._zzz.copy()

    @property
    def zzz2(self) -> CardDataDict[ZZZCardData]:
        if self._zzz2 is None:
            msg = "ZZZ temp2 card data is not loaded"
            raise ValueError(msg)
        return self._zzz2.copy()

    @property
    def gi(self) -> CardDataDict[GICardData]:
        if self._gi is None:
            msg = "GI card data is not loaded"
            raise ValueError(msg)
        return self._gi.copy()

    @property
    def hsr(self) -> CardDataDict[HSRCardData]:
        if self._hsr is None:
            msg = "HSR card data is not loaded"
            raise ValueError(msg)
        return self._hsr.copy()


class CardDataDict[M](dict[str, M]):
    def get[T](self, key: str, _model: type[T], default: Any = None) -> T | None:
        return super().get(key, default)  # pyright: ignore[reportReturnType]

    def copy(self) -> CardDataDict[M]:
        return CardDataDict(super().copy())


CARD_DATA = CardDataManager()
