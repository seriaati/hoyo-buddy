from __future__ import annotations

from pydantic import BaseModel


class GIGachaAvatar(BaseModel):
    id: int
    name: str
    icon: str


class GIGachaWeapon(BaseModel):
    id: int
    name: str
    icon: str


class GIGachaConfigData(BaseModel):
    all_avatar: list[GIGachaAvatar]
    all_weapon: list[GIGachaWeapon]


class GIGachaConfigResponse(BaseModel):
    retcode: int
    data: GIGachaConfigData


class HSRGachaCharacterItem(BaseModel):
    item_id: int
    item_name: str
    icon_url: str


class HSRGachaWeaponItem(BaseModel):
    item_id: int
    item_name: str
    item_url: str


class HSRGachaCharacterListData(BaseModel):
    list: list[HSRGachaCharacterItem]  # noqa: A003


class HSRGachaWeaponListData(BaseModel):
    list: list[HSRGachaWeaponItem]  # noqa: A003


class HSRGachaCharacterListResponse(BaseModel):
    retcode: int
    data: HSRGachaCharacterListData


class HSRGachaWeaponListResponse(BaseModel):
    retcode: int
    data: HSRGachaWeaponListData


class ZZZGachaItem(BaseModel):
    id: int
    name: str
    icon: str


class ZZZGachaListData(BaseModel):
    list: list[ZZZGachaItem]  # noqa: A003


class ZZZGachaListResponse(BaseModel):
    retcode: int
    data: ZZZGachaListData
