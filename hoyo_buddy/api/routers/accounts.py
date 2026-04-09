from __future__ import annotations

from typing import Annotated, Any

import genshin
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from hoyo_buddy.api.utils import decrypt_string
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME, locale_to_gpy_lang
from hoyo_buddy.db.models import AccountNotifSettings, HoyoAccount, Settings, User
from hoyo_buddy.enums import Locale, Platform
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.utils import dict_cookie_to_str

from ..deps import get_session, require_auth
from ..schemas import AccountInfo, AccountSubmitRequest, FinishAccountsResponse, LoginFlowResponse

router = APIRouter()


def _get_login_flow(session: dict[str, Any]) -> dict[str, Any]:
    """Return the login_flow sub-dict from the session."""
    return session.get("login_flow", {})


@router.get("/available", response_model=FinishAccountsResponse)
async def get_available_accounts(
    session: Annotated[dict[str, Any], Depends(get_session)],
    user_id: Annotated[int, Depends(require_auth)],
) -> FinishAccountsResponse:
    """Fetch the list of game accounts available for the current login cookies."""
    login_flow = _get_login_flow(session)

    encrypted_cookies: str | None = login_flow.get("encrypted_cookies")
    if not encrypted_cookies:
        raise HTTPException(status_code=400, detail="No cookies in session. Complete login first.")

    device_id: str | None = login_flow.get("device_id")
    device_fp: str | None = login_flow.get("device_fp")

    # Determine platform from session params
    platform_str: str | None = login_flow.get("platform") or session.get("platform")
    try:
        platform = Platform(platform_str) if platform_str else Platform.HOYOLAB
    except ValueError:
        platform = Platform.HOYOLAB

    # Miyoushe requires device info
    if platform is Platform.MIYOUSHE and (not device_id or not device_fp):
        return FinishAccountsResponse(accounts=[], status="device_info_required")

    cookies = decrypt_string(encrypted_cookies)

    # Optionally fetch cookie with stoken for HoYoLAB
    fetch_cookie = platform is Platform.HOYOLAB and "stoken" in cookies and "ltmid_v2" in cookies
    logger.debug(f"[{user_id}] Fetch cookie with stoken: {fetch_cookie}")

    if fetch_cookie:
        try:
            new_dict_cookie = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
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
    session: Annotated[dict[str, Any], Depends(get_session)],
    user_id: Annotated[int, Depends(require_auth)],
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

    platform_str: str | None = login_flow.get("platform") or session.get("platform")
    try:
        platform = Platform(platform_str) if platform_str else Platform.HOYOLAB
    except ValueError:
        platform = Platform.HOYOLAB

    region = genshin.Region.CHINESE if platform is Platform.MIYOUSHE else genshin.Region.OVERSEAS

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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

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

    fetch_cookie = platform is Platform.HOYOLAB and "stoken" in cookies and "ltmid_v2" in cookies
    if fetch_cookie:
        # Get ltoken_v2 and cookie_token_v2
        try:
            new_dict_cookie = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
        except Exception as e:
            logger.exception(f"[{user_id}] Fetch cookie with stoken error: {e}")
            raise HTTPException(status_code=500, detail=str(e)) from e

        dict_cookie = genshin.parse_cookie(cookies)
        dict_cookie.update(new_dict_cookie)
        cookies = dict_cookie_to_str(dict_cookie)

    # Ensure the User and Settings rows exist
    await User.get_or_create(id=user_id, defaults={"temp_data": {}})
    await Settings.get_or_create(user_id=user_id)

    last_account: HoyoAccount | None = None
    for account in accounts_to_save:
        hb_game = GPY_GAME_TO_HB_GAME[account.game]
        hoyo_account, _ = await HoyoAccount.update_or_create(
            uid=account.uid,
            game=hb_game,
            user_id=user_id,
            defaults={
                "username": account.nickname,
                "cookies": cookies,
                "server": account.server_name,
                "device_id": device_id,
                "device_fp": device_fp,
                "region": region,
            },
        )
        await AccountNotifSettings.get_or_create(account_id=hoyo_account.id)
        last_account = hoyo_account

    # Set the last saved account as current
    if last_account is not None:
        await HoyoAccount.filter(user_id=user_id).update(current=False)
        await HoyoAccount.filter(id=last_account.id).update(current=True)

    # Clear login flow from session
    session.pop("login_flow", None)
    return LoginFlowResponse(next_step="done")
