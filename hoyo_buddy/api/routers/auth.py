from __future__ import annotations

import secrets
from typing import Annotated, Any

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import FRONTEND_URLS

from ..deps import get_session
from ..schemas import AuthCallbackRequest, AuthURLResponse, UserResponse

router = APIRouter()

DISCORD_API_BASE = "https://discord.com/api"
DISCORD_OAUTH_SCOPES = "identify"


def _build_discord_oauth_url(state: str) -> str:
    """Build the Discord OAuth2 authorization URL."""
    redirect_uri = f"{FRONTEND_URLS[CONFIG.env]}/oauth/callback"
    params = {
        "client_id": str(CONFIG.discord_client_id),
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": DISCORD_OAUTH_SCOPES,
        "state": state,
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{DISCORD_API_BASE}/oauth2/authorize?{query}"


async def _fetch_discord_user(access_token: str) -> dict[str, Any] | None:
    """Fetch the Discord user data using the given access token."""
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.get(
            f"{DISCORD_API_BASE}/users/@me", headers={"Authorization": f"Bearer {access_token}"}
        ) as resp,
    ):
        if resp.status == 200:
            return await resp.json()
        return None


async def _refresh_access_token(refresh_token: str) -> dict[str, Any] | None:
    """Refresh the Discord access token using the refresh token."""
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.post(
            f"{DISCORD_API_BASE}/oauth2/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": CONFIG.discord_client_id,
                "client_secret": CONFIG.discord_client_secret,
            },
        ) as resp,
    ):
        if resp.status == 200:
            return await resp.json()
        return None


def _user_data_to_response(user_data: dict[str, Any]) -> UserResponse:
    """Convert raw Discord user data to a UserResponse."""
    user_id = user_data.get("id", "")
    username = user_data.get("username", "")
    avatar = user_data.get("avatar")
    if avatar:
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"
    else:
        discriminator = int(user_data.get("discriminator", "0") or "0")
        default_avatar_index = discriminator % 5
        avatar_url = f"https://cdn.discordapp.com/embed/avatars/{default_avatar_index}.png"
    return UserResponse(id=user_id, username=username, avatar_url=avatar_url)


@router.post("/logout")
async def logout(session: Annotated[dict, Depends(get_session)]) -> JSONResponse:
    session.clear()
    response = JSONResponse({"status": "ok"})
    response.delete_cookie("hb_session")
    return response


@router.get("/me", response_model=UserResponse)
async def get_me(session: Annotated[dict, Depends(get_session)]) -> UserResponse:
    """Return the currently authenticated Discord user."""
    access_token: str | None = session.get("oauth_access_token")
    if access_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_data = await _fetch_discord_user(access_token)
    if user_data is not None:
        return _user_data_to_response(user_data)

    # Token may be expired — try to refresh
    refresh_token: str | None = session.get("oauth_refresh_token")
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_data = await _refresh_access_token(refresh_token)
    if token_data is None:
        raise HTTPException(status_code=401, detail="Failed to refresh token")

    new_access_token = token_data.get("access_token")
    if new_access_token is None:
        raise HTTPException(status_code=401, detail="Failed to refresh token")

    session["oauth_access_token"] = new_access_token
    if "refresh_token" in token_data:
        session["oauth_refresh_token"] = token_data["refresh_token"]

    user_data = await _fetch_discord_user(new_access_token)
    if user_data is None:
        raise HTTPException(status_code=401, detail="Failed to fetch user data after refresh")

    return _user_data_to_response(user_data)


@router.get("/discord/url", response_model=AuthURLResponse)
async def get_discord_auth_url(session: Annotated[dict, Depends(get_session)]) -> AuthURLResponse:
    """Generate a Discord OAuth2 authorization URL and store the state in the session."""
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    url = _build_discord_oauth_url(state)
    return AuthURLResponse(url=url)


@router.post("/discord/callback", response_model=UserResponse)
async def discord_callback(
    body: AuthCallbackRequest, session: Annotated[dict, Depends(get_session)]
) -> UserResponse:
    """Exchange the Discord OAuth2 code for tokens and authenticate the user."""
    # Validate state to prevent CSRF
    stored_state: str | None = session.get("oauth_state")
    if stored_state is None or stored_state != body.state:
        raise HTTPException(status_code=403, detail="Invalid state")

    redirect_uri = f"{FRONTEND_URLS[CONFIG.env]}/oauth/callback"

    # Exchange code for tokens
    async with (
        aiohttp.ClientSession() as http_session,
        http_session.post(
            f"{DISCORD_API_BASE}/oauth2/token",
            data={
                "client_id": CONFIG.discord_client_id,
                "client_secret": CONFIG.discord_client_secret,
                "grant_type": "authorization_code",
                "code": body.code,
                "redirect_uri": redirect_uri,
                "scope": DISCORD_OAUTH_SCOPES,
            },
        ) as resp,
    ):
        if resp.status != 200:
            reason = resp.reason or "Failed to get access token"
            raise HTTPException(status_code=resp.status, detail=reason)
        token_data: dict[str, Any] = await resp.json()

    access_token = token_data.get("access_token")
    if access_token is None:
        raise HTTPException(status_code=400, detail="Missing access token in response")

    refresh_token = token_data.get("refresh_token")
    if refresh_token is None:
        raise HTTPException(status_code=400, detail="Missing refresh token in response")

    # Store tokens in session
    session["oauth_access_token"] = access_token
    session["oauth_refresh_token"] = refresh_token
    # Clear the used state
    session.pop("oauth_state", None)

    # Fetch user data and store user_id
    user_data = await _fetch_discord_user(access_token)
    if user_data is None:
        raise HTTPException(status_code=400, detail="Failed to fetch user data")

    user_id = user_data.get("id")
    if user_id is None:
        raise HTTPException(status_code=400, detail="Missing user ID in Discord response")

    session["user_id"] = int(user_id)

    return _user_data_to_response(user_data)
