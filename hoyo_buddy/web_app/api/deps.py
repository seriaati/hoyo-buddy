from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import asyncpg
from fastapi import Depends, HTTPException, Request

from hoyo_buddy.config import CONFIG


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Provide an asyncpg connection for the duration of a request."""
    conn = await asyncpg.connect(CONFIG.db_url)
    try:
        yield conn
    finally:
        await conn.close()


def get_session(request: Request) -> dict[str, Any]:
    """Return the session dict attached to the request by the session middleware."""
    return request.state.session


def require_auth(session: dict[str, Any] = Depends(get_session)) -> int:
    """Require the user to be authenticated; return the Discord user_id."""
    user_id = session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return int(user_id)
