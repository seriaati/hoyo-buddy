from __future__ import annotations

from typing import Annotated, Any

from fastapi import Depends, HTTPException, Request  # noqa: TC002


def get_session(request: Request) -> dict[str, Any]:
    """Return the session dict attached to the request by the session middleware."""
    return request.state.session


def require_auth(session: Annotated[dict[str, Any], Depends(get_session)]) -> int:
    """Require the user to be authenticated; return the Discord user_id."""
    user_id = session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return int(user_id)
