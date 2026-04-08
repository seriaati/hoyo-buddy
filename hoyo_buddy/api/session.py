from __future__ import annotations

from collections import UserDict
from typing import TYPE_CHECKING, Any

import itsdangerous
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp


class _SessionDict(UserDict):
    """A UserDict subclass that tracks mutations."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._modified = False

    @property
    def modified(self) -> bool:
        return self._modified

    def mark_modified(self) -> None:
        self._modified = True

    def __setitem__(self, key: Any, value: Any) -> None:
        super().__setitem__(key, value)
        self._modified = True

    def __delitem__(self, key: Any) -> None:
        super().__delitem__(key)
        self._modified = True

    def clear(self) -> None:
        super().clear()
        self._modified = True

    def pop(self, *args: Any) -> Any:
        result = super().pop(*args)
        self._modified = True
        return result

    def update(self, *args: Any, **kwargs: Any) -> None:
        super().update(*args, **kwargs)
        self._modified = True


class SignedCookieSessionMiddleware(BaseHTTPMiddleware):
    """Starlette-compatible session middleware using itsdangerous signed cookies."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        secret_key: str,
        cookie_name: str = "hb_session",
        max_age: int = 86400 * 7,
        same_site: str = "lax",
        https_only: bool = False,
    ) -> None:
        super().__init__(app)
        self._serializer = itsdangerous.URLSafeTimedSerializer(secret_key, salt="hb-session")
        self._cookie_name = cookie_name
        self._max_age = max_age
        self._same_site = same_site
        self._https_only = https_only

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        # Deserialize session from cookie
        session_data: dict[str, Any] = {}
        cookie_value = request.cookies.get(self._cookie_name)
        if cookie_value:
            try:
                session_data = self._serializer.loads(cookie_value, max_age=self._max_age)
            except itsdangerous.SignatureExpired:
                logger.debug("Session cookie expired, starting fresh session")
            except itsdangerous.BadSignature:
                logger.warning("Session cookie has bad signature, starting fresh session")
            except Exception:
                logger.exception("Failed to deserialize session cookie")

        session = _SessionDict(session_data)
        request.state.session = session

        response = await call_next(request)

        # Serialize session back to cookie if modified
        if session.modified:
            signed_value = self._serializer.dumps(dict(session))
            cookie_kwargs: dict[str, Any] = {
                "key": self._cookie_name,
                "value": signed_value,
                "max_age": self._max_age,
                "httponly": True,
                "samesite": self._same_site,
            }
            if self._https_only:
                cookie_kwargs["secure"] = True
            response.set_cookie(**cookie_kwargs)

        return response
