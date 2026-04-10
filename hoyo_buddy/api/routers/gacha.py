from __future__ import annotations

from typing import Annotated

import hb_data
from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from hoyo_buddy.constants import locale_to_hoyo_lang
from hoyo_buddy.db.models import GachaHistory, HoyoAccount, JSONFile
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.l10n import BANNER_TYPE_NAMES, translator
from hoyo_buddy.utils.gacha import calculate_gacha_stats, get_gacha_icon

from ..schemas import (
    BannerTypeInfo,
    BannerTypesResponse,
    GachaItem,
    GachaLogResponse,
    GachaParams,
    GachaStatsResponse,
)

router = APIRouter()

GachaData = dict[str, dict[str, str]]


def _get_gacha_data_filename(game: Game, lang: str) -> str:
    if game is Game.GENSHIN:
        return f"gi_gacha_data_{lang}.json"
    if game is Game.STARRAIL:
        return f"hsr_gacha_data_{lang}.json"
    if game is Game.ZZZ:
        return f"zzz_gacha_data_{lang}.json"
    msg = f"Unsupported game: {game}"
    raise ValueError(msg)


async def _load_gacha_data(game: Game, locale: Locale) -> GachaData:
    lang = locale_to_hoyo_lang(locale)
    filename = _get_gacha_data_filename(game, lang)
    data: GachaData = await JSONFile.read(filename, default={})

    if game is Game.GENSHIN:
        async with hb_data.GIClient() as client:
            mw_costumes = client.get_mw_costumes()
            mw_items = client.get_mw_items()
            for costume in mw_costumes:
                data[str(costume.id)] = {"name": costume.name, "icon": ""}
            for item in mw_items:
                data[str(item.id)] = {"name": item.name, "icon": ""}

    return data


@router.get("/logs", response_model=GachaLogResponse)
async def get_gacha_logs(
    account_id: Annotated[int, Query()],
    banner_type: Annotated[int, Query()],
    locale: Annotated[str, Query()] = "en-US",
    rarities: Annotated[str, Query()] = "",
    size: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: Annotated[str | None, Query()] = None,
    name_contains: Annotated[str | None, Query()] = None,
) -> GachaLogResponse:
    parsed_rarities: list[int] = (
        [int(r) for r in rarities.split(",") if r.strip()] if rarities else []
    )

    try:
        params = GachaParams(
            locale=locale,
            account_id=account_id,
            banner_type=banner_type,
            rarities=parsed_rarities,
            size=size,
            cursor=cursor,
            name_contains=name_contains,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    account = await HoyoAccount.get_or_none(id=params.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    game = account.game

    try:
        locale_enum = Locale(params.locale)
    except ValueError:
        locale_enum = Locale.american_english

    gacha_data = await _load_gacha_data(game, locale_enum)

    base_qs = GachaHistory.filter(
        account_id=params.account_id, banner_type=params.banner_type, rarity__in=params.rarities
    )

    if params.name_contains:
        matching_ids = {
            int(item_id)
            for item_id, item in gacha_data.items()
            if params.name_contains.lower() in item.get("name", "").lower()
        }
        if not matching_ids:
            return GachaLogResponse(items=[], total=0, next_cursor=None, game=game.value)
        base_qs = base_qs.filter(item_id__in=matching_ids)

    total = await base_qs.count()

    qs = base_qs.order_by("-wish_id")
    if params.cursor is not None:
        qs = qs.filter(wish_id__lt=params.cursor)

    gacha_logs = await qs.limit(params.size + 1)

    next_cursor: str | None = None
    if len(gacha_logs) > params.size:
        next_cursor = str(gacha_logs[params.size - 1].wish_id)
        gacha_logs = gacha_logs[: params.size]

    items = [
        GachaItem(
            id=g.id,
            item_id=g.item_id,
            rarity=g.rarity,
            num=g.num,
            num_since_last=g.num_since_last,
            wish_id=str(g.wish_id),
            time=str(g.time),
            banner_type=g.banner_type,
            name=gacha_data.get(str(g.item_id), {}).get("name", "???"),
            icon=get_gacha_icon(item_id=g.item_id, gacha_data=gacha_data),
        )
        for g in gacha_logs
    ]

    return GachaLogResponse(items=items, total=total, next_cursor=next_cursor, game=game.value)


@router.get("/banner-types", response_model=BannerTypesResponse)
async def get_banner_types(
    game: Annotated[str, Query()], locale: Annotated[str, Query()] = "en-US"
) -> BannerTypesResponse:
    try:
        game_enum = Game(game)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        locale_enum = Locale(locale)
    except ValueError:
        locale_enum = Locale.american_english

    banner_type_map = BANNER_TYPE_NAMES.get(game_enum, {})
    banner_types = [
        BannerTypeInfo(id=banner_type, name=translator.translate(name, locale_enum))
        for banner_type, name in banner_type_map.items()
    ]

    return BannerTypesResponse(banner_types=banner_types)


@router.get("/stats", response_model=GachaStatsResponse)
async def get_gacha_stats(
    account_id: Annotated[int, Query()], banner_type: Annotated[int, Query()]
) -> GachaStatsResponse:
    account = await HoyoAccount.get_or_none(id=account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await calculate_gacha_stats(
        account_id=account_id, game=account.game, banner_type=banner_type
    )

    return GachaStatsResponse(
        total_pulls=result.total_pulls,
        five_star_pity=result.five_star_pity,
        four_star_pity=result.four_star_pity,
        total_five_stars=result.total_five_stars,
        total_four_stars=result.total_four_stars,
        avg_pulls_per_five_star=result.avg_pulls_per_five_star,
        avg_pulls_per_four_star=result.avg_pulls_per_four_star,
        fifty_fifty_wins=result.fifty_fifty_wins,
        fifty_fifty_total=result.fifty_fifty_total,
        fifty_fifty_win_rate=result.fifty_fifty_win_rate,
    )
