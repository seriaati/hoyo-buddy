from __future__ import annotations

from typing import Annotated, Any

import genshin
from fastapi import Depends, HTTPException, Request, Response  # noqa: TC002
from loguru import logger

DEVICE_ID_COOKIE = "hb_device_id"
DEVICE_ID_MAX_AGE = 365 * 86400


def get_session(request: Request) -> dict[str, Any]:
    """Return the session dict attached to the request by the session middleware."""
    return request.state.session


def require_auth(session: Annotated[dict[str, Any], Depends(get_session)]) -> int:
    """Require the user to be authenticated; return the Discord user_id."""
    user_id = session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return int(user_id)


def get_or_create_device_id(request: Request, response: Response) -> str:
    device_id = request.cookies.get(DEVICE_ID_COOKIE)
    if not device_id:
        device_id = genshin.Client.generate_app_device_id()
        logger.debug(f"Generated new device_id: {device_id}")
    response.set_cookie(
        key=DEVICE_ID_COOKIE,
        value=device_id,
        max_age=DEVICE_ID_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return device_id
