from __future__ import annotations

from pathlib import Path
from typing import Any

from seria.utils import read_yaml

ASSET_PATH = Path("hoyo-buddy-assets/assets")
GI_DATA = ASSET_PATH / "gi-build-card/data.yaml"
HSR_DATA = ASSET_PATH / "hsr-build-card/data.yaml"
ZZZ_DATA = ASSET_PATH / "zzz-build-card/agent_data.yaml"
ZZZ_DATA2 = ASSET_PATH / "zzz-build-card/agent_data_temp2.yaml"


class CardData:
    def __init__(self) -> None:
        self._gi: dict[str, Any] | None = {}
        self._hsr: dict[str, Any] | None = {}
        self._zzz: dict[str, Any] | None = {}
        self._zzz2: dict[str, Any] | None = {}

    async def load(self) -> None:
        self._gi = await read_yaml(GI_DATA)
        self._hsr = await read_yaml(HSR_DATA)
        self._zzz = await read_yaml(ZZZ_DATA)
        self._zzz2 = await read_yaml(ZZZ_DATA2)

    @property
    def zzz(self) -> dict[str, Any]:
        if self._zzz is None:
            msg = "ZZZ card data is not loaded"
            raise ValueError(msg)
        return self._zzz

    @property
    def zzz2(self) -> dict[str, Any]:
        if self._zzz2 is None:
            msg = "ZZZ temp2 card data is not loaded"
            raise ValueError(msg)
        return self._zzz2

    @property
    def gi(self) -> dict[str, Any]:
        if self._gi is None:
            msg = "GI card data is not loaded"
            raise ValueError(msg)
        return self._gi

    @property
    def hsr(self) -> dict[str, Any]:
        if self._hsr is None:
            msg = "HSR card data is not loaded"
            raise ValueError(msg)
        return self._hsr


CARD_DATA = CardData()
