from __future__ import annotations

from typing import Annotated

import hb_data
from fastapi import APIRouter, HTTPException, Query
from pydantic import ValidationError

from hoyo_buddy.constants import locale_to_starrail_data_lang, locale_to_zenless_data_lang
from hoyo_buddy.db.models import GachaHistory, HoyoAccount
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.hoyo.clients.ambr import AmbrAPIClient
from hoyo_buddy.web_app.schema import GachaParams
from hoyo_buddy.web_app.utils import fetch_gacha_icons, fetch_json_file

from ..schemas import GachaIconsResponse, GachaItem, GachaLogResponse, GachaNamesResponse

router = APIRouter()


async def _fetch_gacha_names(*, item_ids: list[int], locale: Locale, game: Game) -> dict[int, str]:
    """Fetch item names for the given item IDs, locale, and game."""
    result: dict[int, str] = {}

    if game is Game.ZZZ:
        zzz_map: dict[str, str] = await fetch_json_file(
            f"zzz_item_names_{locale_to_zenless_data_lang(locale)}.json"
        )
        item_names = {int(k): v for k, v in zzz_map.items()}
    elif game is Game.STARRAIL:
        hsr_map: dict[str, str] = await fetch_json_file(
            f"hsr_item_names_{locale_to_starrail_data_lang(locale)}.json"
        )
        item_names = {int(k): v for k, v in hsr_map.items()}
    elif game is Game.GENSHIN:
        async with AmbrAPIClient(locale) as client:
            item_names = await client.fetch_item_id_to_name_map()
        async with hb_data.GIClient() as client:
            mw_costumes = client.get_mw_costumes()
            mw_items = client.get_mw_items()
            item_names.update({costume.id: costume.name for costume in mw_costumes})
            item_names.update({item.id: item.name for item in mw_items})
    else:
        msg = f"Unsupported game: {game} for fetching gacha names"
        raise ValueError(msg)

    for item_id in item_ids:
        result[item_id] = item_names.get(item_id, "???")

    return result


@router.get("/logs", response_model=GachaLogResponse)
async def get_gacha_logs(
    account_id: Annotated[int, Query()],
    banner_type: Annotated[int, Query()],
    locale: Annotated[str, Query()] = "en-US",
    rarities: Annotated[str, Query()] = "",
    size: Annotated[int, Query(ge=1, le=500)] = 100,
    page: Annotated[int, Query(ge=1)] = 1,
    name_contains: Annotated[str | None, Query()] = None,
) -> GachaLogResponse:
    """Return paginated gacha history for an account. No auth required."""
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
            page=page,
            name_contains=name_contains,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Check account exists and get its game
    account = await HoyoAccount.get_or_none(id=params.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    game = account.game

    # Base queryset filtered by account, banner_type, and rarities
    qs = GachaHistory.filter(
        account_id=params.account_id, banner_type=params.banner_type, rarity__in=params.rarities
    )

    total_row = await qs.count()

    # Fetch gacha logs — fetch all when name filter is active, paginate otherwise
    if params.name_contains:
        gacha_logs = await qs.order_by("-wish_id")
    else:
        gacha_logs = (
            await qs.order_by("-wish_id").offset((params.page - 1) * params.size).limit(params.size)
        )

    # Apply name filter if requested
    if params.name_contains:
        try:
            locale_enum = Locale(params.locale)
        except ValueError:
            locale_enum = Locale.american_english

        item_ids = list({g.item_id for g in gacha_logs})
        gacha_names = await _fetch_gacha_names(item_ids=item_ids, locale=locale_enum, game=game)
        gacha_logs = [
            g
            for g in gacha_logs
            if params.name_contains.lower() in gacha_names.get(g.item_id, "").lower()
        ][(params.page - 1) * params.size : params.page * params.size]
        total_row = len(gacha_logs)

    max_page = max(1, (total_row + params.size - 1) // params.size)

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
        )
        for g in gacha_logs
    ]

    return GachaLogResponse(items=items, total=total_row, page=params.page, max_page=max_page)


@router.get("/icons", response_model=GachaIconsResponse)
async def get_gacha_icons() -> GachaIconsResponse:
    """Fetch Genshin character/weapon icons from ambr API. No auth required."""
    icons = await fetch_gacha_icons()
    return GachaIconsResponse(icons=icons)


@router.get("/names", response_model=GachaNamesResponse)
async def get_gacha_names(
    locale: Annotated[str, Query()],
    game: Annotated[str, Query()],
    item_ids: Annotated[str, Query()] = "",
) -> GachaNamesResponse:
    """Fetch item names for the given locale, game, and item IDs. No auth required."""
    try:
        locale_enum = Locale(locale)
        game_enum = Game(game)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not item_ids:
        return GachaNamesResponse(names={})

    parsed_ids = [int(i) for i in item_ids.split(",") if i.strip()]
    if not parsed_ids:
        return GachaNamesResponse(names={})

    names = await _fetch_gacha_names(item_ids=parsed_ids, locale=locale_enum, game=game_enum)
    return GachaNamesResponse(names={str(k): v for k, v in names.items()})
