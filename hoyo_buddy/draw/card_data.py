from pathlib import Path
from typing import Any

import anyio
from pydantic import BaseModel
from seria.utils import read_yaml

from hoyo_buddy.models.draw import (
    GICardData,
    HSRCardData,
    SpineData,
    ZZZTemp1CardData,
    ZZZTemp2CardData,
)

ASSET_PATH = Path("hoyo-buddy-assets/assets")
GI_DATA = ASSET_PATH / "gi-build-card/data.yaml"
GI_SPINE_DATA = ASSET_PATH / "gi-build-card/spine.yaml"
HSR_DATA = ASSET_PATH / "hsr-build-card/data.yaml"
HSR_SPINE_DATA = {
    1: ASSET_PATH / "hsr-build-card/spine.yaml",
    2: ASSET_PATH / "hsr-build-card2/spine.yaml",
}
ZZZ_DATA = ASSET_PATH / "zzz-build-card/agent_data.yaml"
ZZZ_DATA2 = ASSET_PATH / "zzz-build-card/agent_data_temp2.yaml"
ZZZ_SPINE_DATA = ASSET_PATH / "zzz-build-card/spine.yaml"


class CardDataManager:
    def __init__(self) -> None:
        self._gi: dict[str, GICardData] | None = None
        self._gi_spine: dict[str, SpineData] | None = None
        self._hsr: dict[str, HSRCardData] | None = None
        self._hsr_spine: dict[int, dict[str, SpineData]] | None = None
        self._zzz: dict[str, ZZZTemp1CardData] | None = None
        self._zzz2: dict[str, ZZZTemp2CardData] | None = None
        self._zzz_spine: dict[str, SpineData] | None = None

    def _parse_model[T: BaseModel](self, data: dict[str, Any], model: type[T]) -> dict[str, T]:
        return {k: model.model_validate(v) for k, v in data.items()}

    async def _load_spine(self, path: Path) -> dict[str, SpineData]:
        data = await read_yaml(path) if await anyio.Path(path).exists() else {}
        return self._parse_model(data, SpineData)

    async def load(self) -> None:
        self._gi = self._parse_model(await read_yaml(GI_DATA), GICardData)
        self._gi_spine = await self._load_spine(GI_SPINE_DATA)
        self._hsr = self._parse_model(await read_yaml(HSR_DATA), HSRCardData)
        self._zzz = self._parse_model(await read_yaml(ZZZ_DATA), ZZZTemp1CardData)
        self._zzz2 = self._parse_model(await read_yaml(ZZZ_DATA2), ZZZTemp2CardData)
        self._zzz_spine = await self._load_spine(ZZZ_SPINE_DATA)
        self._hsr_spine = {
            template: await self._load_spine(path) for template, path in HSR_SPINE_DATA.items()
        }

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
    def zzz_spine(self) -> dict[str, SpineData]:
        if self._zzz_spine is None:
            msg = "ZZZ spine data is not loaded"
            raise ValueError(msg)
        return self._zzz_spine.copy()

    @property
    def gi(self) -> dict[str, GICardData]:
        if self._gi is None:
            msg = "GI card data is not loaded"
            raise ValueError(msg)
        return self._gi.copy()

    @property
    def gi_spine(self) -> dict[str, SpineData]:
        if self._gi_spine is None:
            msg = "GI spine data is not loaded"
            raise ValueError(msg)
        return self._gi_spine.copy()

    @property
    def hsr(self) -> dict[str, HSRCardData]:
        if self._hsr is None:
            msg = "HSR card data is not loaded"
            raise ValueError(msg)
        return self._hsr.copy()

    def hsr_spine(self, template: int) -> dict[str, SpineData]:
        if self._hsr_spine is None:
            msg = "HSR spine data is not loaded"
            raise ValueError(msg)
        return self._hsr_spine.get(template, {}).copy()


CARD_DATA = CardDataManager()
