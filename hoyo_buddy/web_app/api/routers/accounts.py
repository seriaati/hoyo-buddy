from __future__ import annotations

from typing import Any

import asyncpg
import genshin
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import FRONTEND_URLS, GPY_GAME_TO_HB_GAME, locale_to_gpy_lang
from hoyo_buddy.enums import Locale, Platform
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.utils import dict_cookie_to_str, get_discord_protocol_url
from hoyo_buddy.web_app.utils import decrypt_string

from ..deps import get_db, get_session, require_auth
from ..schemas import AccountInfo, AccountSubmitRequest, FinishAccountsResponse, LoginFlowResponse

router = APIRouter()


def _get_login_flow(session: dict[str, Any]) -> dict[str, Any]:
    """Return the login_flow sub-dict from the session."""
    return session.get("login_flow", {})


@router.get("/available", response_model=FinishAccountsResponse)
async def get_available_accounts(
    session: dict[str, Any] = Depends(get_session),
    user_id: int = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db),
) -> FinishAccountsResponse:
    """Fetch the list of game accounts available for the current login cookies."""
    login_flow = _get_login_flow(session)

    encrypted_cookies: str | None = login_flow.get("encrypted_cookies")
    if not encrypted_cookies:
        raise HTTPException(status_code=400, detail="No cookies in session. Complete login first.")

    device_id: str | None = login_flow.get("device_id")
    device_fp: str | None = login_flow.get("device_fp")

    # Determine platform from session params
    platform_str: str | None = session.get("platform")
    try:
        platform = Platform(platform_str) if platform_str else Platform.HOYOLAB
    except ValueError:
        platform = Platform.HOYOLAB

    # Miyoushe requires device info
    if platform is Platform.MIYOUSHE and (not device_id or not device_fp):
        return FinishAccountsResponse(accounts=[], status="device_info_required")

    cookies = decrypt_string(encrypted_cookies)

    # Optionally fetch cookie with stoken for HoYoLAB
    fetch_cookie = (
        platform is Platform.HOYOLAB and "stoken" in cookies and "ltmid_v2" in cookies
    )
    logger.debug(f"[{user_id}] Fetch cookie with stoken: {fetch_cookie}")

    if fetch_cookie:
        try:
            new_dict_cookie = await genshin.fetch_cookie_with_stoken_v2(
                cookies, token_types=[2, 4]
            )
        except Exception as exc:
            logger.exception(f"[{user_id}] Fetch cookie with stoken error: {exc}")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        dict_cookie = genshin.parse_cookie(cookies)
        dict_cookie.update(new_dict_cookie)
        cookies = dict_cookie_to_str(dict_cookie)

    locale_str: str = session.get("locale", "en-US")
    try:
        locale = Locale(locale_str)
    except ValueError:
        locale = Locale.american_english

    try:
        client = ProxyGenshinClient(
            cookies,
            lang=locale_to_gpy_lang(locale),
            region=genshin.Region.OVERSEAS
            if platform is Platform.HOYOLAB
            else genshin.Region.CHINESE,
            device_id=device_id,
            device_fp=device_fp,
        )
        accounts = await client.get_game_accounts()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not accounts:
        raise HTTPException(status_code=404, detail="No game accounts found")

    account_infos = [
        AccountInfo(
            uid=acc.uid,
            nickname=acc.nickname,
            game=acc.game.value if isinstance(acc.game, genshin.Game) else str(acc.game),  # pyright: ignore[reportUnnecessaryIsInstance]
            server_name=acc.server_name,
            level=acc.level,
        )
        for acc in accounts
        if isinstance(acc.game, genshin.Game)  # pyright: ignore[reportUnnecessaryIsInstance]
    ]

    return FinishAccountsResponse(accounts=account_infos, status="ok")


@router.post("/submit", response_model=LoginFlowResponse)
async def submit_accounts(
    body: AccountSubmitRequest,
    session: dict[str, Any] = Depends(get_session),
    user_id: int = Depends(require_auth),
    conn: asyncpg.Connection = Depends(get_db),
) -> LoginFlowResponse:
    """Save the selected accounts to the database and return a Discord redirect URL."""
    if not body.selected_accounts:
        raise HTTPException(status_code=400, detail="No accounts selected")

    login_flow = _get_login_flow(session)

    encrypted_cookies: str | None = login_flow.get("encrypted_cookies")
    if not encrypted_cookies:
        raise HTTPException(status_code=400, detail="No cookies in session")

    cookies = decrypt_string(encrypted_cookies)
    device_id: str | None = login_flow.get("device_id")
    device_fp: str | None = login_flow.get("device_fp")

    platform_str: str | None = session.get("platform")
    try:
        platform = Platform(platform_str) if platform_str else Platform.HOYOLAB
    except ValueError:
        platform = Platform.HOYOLAB

    region = (
        genshin.Region.CHINESE
        if platform is Platform.MIYOUSHE
        else genshin.Region.OVERSEAS
    )

    locale_str: str = session.get("locale", "en-US")
    try:
        locale = Locale(locale_str)
    except ValueError:
        locale = Locale.american_english

    # Fetch all game accounts to match selected ones
    try:
        client = ProxyGenshinClient(
            cookies,
            lang=locale_to_gpy_lang(locale),
            region=region,
            device_id=device_id,
            device_fp=device_fp,
        )
        all_accounts = await client.get_game_accounts()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Filter to only selected accounts
    selected_set = set(body.selected_accounts)
    accounts_to_save = [
        acc
        for acc in all_accounts
        if isinstance(acc.game, genshin.Game)  # pyright: ignore[reportUnnecessaryIsInstance]
        and f"{acc.game.value}_{acc.uid}" in selected_set
    ]

    if not accounts_to_save:
        raise HTTPException(status_code=400, detail="None of the selected accounts were found")

    # Insert/update DB rows
    await conn.execute(
        'INSERT INTO "user" (id, temp_data) VALUES ($1, $2) ON CONFLICT (id) DO NOTHING',
        user_id,
        "{}",
    )
    await conn.execute(
        'INSERT INTO "settings" (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING',
        user_id,
    )

    account_id: int | None = None
    for account in accounts_to_save:
        await conn.execute(
            "INSERT INTO hoyoaccount (uid, username, game, cookies, user_id, server, device_id, device_fp, region, redeemed_codes) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) "
            "ON CONFLICT (uid, game, user_id) DO UPDATE SET cookies = $4, username = $2, device_id = $7, device_fp = $8, region = $9",
            account.uid,
            account.nickname,
            GPY_GAME_TO_HB_GAME[account.game],
            cookies,
            user_id,
            account.server_name,
            device_id,
            device_fp,
            region,
            "[]",
        )
        account_id = await conn.fetchval(
            "SELECT id FROM hoyoaccount WHERE uid = $1 AND game = $2 AND user_id = $3",
            account.uid,
            GPY_GAME_TO_HB_GAME[account.game],
            user_id,
        )
        await conn.execute(
            "INSERT INTO accountnotifsettings (account_id) VALUES ($1) ON CONFLICT DO NOTHING",
            account_id,
        )

    # Set the last saved account as current
    if account_id is not None:
        await conn.execute(
            'UPDATE "hoyoaccount" SET current = false WHERE user_id = $1', user_id
        )
        await conn.execute(
            'UPDATE "hoyoaccount" SET current = true WHERE id = $1', account_id
        )

    # Clear login flow from session
    session.pop("login_flow", None)

    # Build redirect URL back to Discord
    channel_id: int | None = session.get("channel_id")
    guild_id: int | None = session.get("guild_id")

    if channel_id is None:
        redirect_url = FRONTEND_URLS[CONFIG.env]
    else:
        redirect_url = get_discord_protocol_url(channel_id=channel_id, guild_id=guild_id)

    return LoginFlowResponse(
        status="success",
        next_step="redirect",
        message=redirect_url,
    )
