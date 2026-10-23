from __future__ import annotations

from typing import TYPE_CHECKING

import genshin

from hoyo_buddy.constants import MW_EVENT_BANNER_TYPES
from hoyo_buddy.db import GachaHistory, update_gacha_nums
from hoyo_buddy.enums import Game
from hoyo_buddy.exceptions import UIDMismatchError
from hoyo_buddy.utils.gacha import zzz_rank_type_to_rarity

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    import asyncpg
    from genshin.paginators import Paginator

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.hoyo.clients.gpy import GenshinClient


class UnknownGachaItemError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Cannot find item ID for {name}, is this an invalid item?")


async def _fetch_new_records[RecordT: genshin.models.Unique](
    make_paginator: Callable[[int], Paginator[RecordT]],
    banner_types: Iterable[int],
    cursors: dict[str, int],
) -> list[RecordT]:
    """Fetch records newer than the per-banner cursors, updating `cursors` in place.

    Each banner's paginator yields records newest-first, so iteration stops (and no
    further API requests are made) once a record at or below the cursor is reached.
    """
    records: list[RecordT] = []

    for banner_type in banner_types:
        key = str(banner_type)
        cutoff = cursors.get(key, 0)

        async for record in make_paginator(banner_type):
            if record.id <= cutoff:
                break
            cursors[key] = max(cursors.get(key, 0), record.id)
            records.append(record)

    records.sort(key=lambda x: x.id)
    return records


def _zzz_signal_records(
    signals: list[genshin.models.SignalSearch], account: HoyoAccount
) -> list[GachaHistory]:
    return [
        GachaHistory(
            wish_id=signal.id,
            rarity=zzz_rank_type_to_rarity(signal.rarity),
            time=signal.time,
            banner_type=signal.banner_type,
            item_id=signal.item_id,
            account=account,
            banner_id=None,
            game=Game.ZZZ,
        )
        for signal in signals
    ]


def _check_uid(
    record: genshin.models.Wish
    | genshin.models.Warp
    | genshin.models.SignalSearch
    | genshin.models.MWWish,
    account: HoyoAccount,
) -> None:
    if record.uid != account.uid:
        raise UIDMismatchError(record.uid)


async def fetch_authkey(client: GenshinClient, account: HoyoAccount) -> str:
    """Generate a gacha authkey from the account's cookies, refreshing the cookie token if needed."""
    try:
        return await client.fetch_authkey(account.uid)
    except genshin.InvalidCookies:
        cookies = account.dict_cookies
        if "stoken" not in cookies or "ltmid_v2" not in cookies:
            raise
        await client.update_cookie_token()
        return await client.fetch_authkey(account.uid)


async def fetch_genshin_records(
    client: GenshinClient,
    account: HoyoAccount,
    *,
    authkey: str,
    cursors: dict[str, int],
    item_ids: Mapping[str, int],
) -> list[GachaHistory]:
    records: list[GachaHistory] = []

    wishes = await _fetch_new_records(
        lambda b: client.wish_history(b, authkey=authkey), genshin.models.GenshinBannerType, cursors
    )
    for wish in wishes:
        _check_uid(wish, account)

        item_id = item_ids.get(wish.name)
        if item_id is None:
            raise UnknownGachaItemError(wish.name)

        records.append(
            GachaHistory(
                wish_id=wish.id,
                rarity=wish.rarity,
                time=wish.time,
                banner_type=301 if wish.banner_type == 400 else wish.banner_type,
                item_id=item_id,
                account=account,
                banner_id=None,
                game=Game.GENSHIN,
            )
        )

    mw_wishes = await _fetch_new_records(
        lambda b: client.mw_wish_history(b, authkey=authkey),
        (genshin.models.MWBannerType.STANDARD, genshin.models.MWBannerType.EVENT),
        cursors,
    )
    for wish in mw_wishes:
        _check_uid(wish, account)

        records.append(
            GachaHistory(
                wish_id=wish.id,
                rarity=wish.rarity,
                time=wish.time,
                banner_type=2000 if wish.banner_type in MW_EVENT_BANNER_TYPES else wish.banner_type,
                item_id=wish.item_id,
                account=account,
                banner_id=wish.banner_id,
                game=Game.GENSHIN,
            )
        )

    return records


async def fetch_starrail_records(
    client: GenshinClient, account: HoyoAccount, *, authkey: str, cursors: dict[str, int]
) -> list[GachaHistory]:
    warps = await _fetch_new_records(
        lambda b: client.warp_history(b, authkey=authkey),
        genshin.models.StarRailBannerType,
        cursors,
    )
    records: list[GachaHistory] = []
    for warp in warps:
        _check_uid(warp, account)

        records.append(
            GachaHistory(
                wish_id=warp.id,
                rarity=warp.rarity,
                time=warp.time,
                banner_type=warp.banner_type,
                item_id=warp.item_id,
                account=account,
                banner_id=warp.banner_id,
                game=Game.STARRAIL,
            )
        )
    return records


async def fetch_zzz_records(
    client: GenshinClient, account: HoyoAccount, *, authkey: str, cursors: dict[str, int]
) -> list[GachaHistory]:
    signals = await _fetch_new_records(
        lambda b: client.signal_history(b, authkey=authkey), genshin.models.ZZZBannerType, cursors
    )
    for signal in signals:
        _check_uid(signal, account)
    return _zzz_signal_records(signals, account)


async def fetch_zzz_chronicle_records(
    client: GenshinClient, account: HoyoAccount, *, cursors: dict[str, int]
) -> list[GachaHistory]:
    signals = await _fetch_new_records(
        lambda b: client.chronicle_signal_history(b, uid=account.uid),
        genshin.models.ZZZBannerType,
        cursors,
    )
    return _zzz_signal_records(signals, account)


async def save_records(
    account: HoyoAccount,
    records: list[GachaHistory],
    *,
    cursors: dict[str, int],
    pool: asyncpg.Pool,
) -> int:
    """Save fetched records and cursors, returns the number of newly added records."""
    if not records:
        return 0

    before = await GachaHistory.get_wish_count(account)
    await GachaHistory.bulk_create(records)

    account.gacha_cursors = cursors
    await account.save(update_fields=("gacha_cursors",))

    after = await GachaHistory.get_wish_count(account)
    await update_gacha_nums(pool, account=account)
    return after - before
