from __future__ import annotations

import genshin.models

__all__ = (
    "AnomalyRecord",
    "DeadlyAssault",
    "HardChallenge",
    "ImgTheaterData",
    "ShiyuDefense",
    "SpiralAbyss",
    "StarRailAPCShadow",
    "StarRailChallenge",
    "StarRailPureFiction",
)


class ImgTheaterData(genshin.models.ImgTheaterData):
    lang: str


class StarRailChallenge(genshin.models.StarRailChallenge):
    lang: str


class SpiralAbyss(genshin.models.SpiralAbyss):
    lang: str


class StarRailPureFiction(genshin.models.StarRailPureFiction):
    lang: str


class StarRailAPCShadow(genshin.models.StarRailAPCShadow):
    lang: str


class ShiyuDefense(genshin.models.ShiyuDefense):
    lang: str


class DeadlyAssault(genshin.models.DeadlyAssault):
    lang: str


class HardChallenge(genshin.models.HardChallenge):
    lang: str


class AnomalyRecord(genshin.models.AnomalyRecord):
    lang: str
