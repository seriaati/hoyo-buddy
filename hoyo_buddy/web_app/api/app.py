from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import FRONTEND_URLS
from hoyo_buddy.db.config import DB_CONFIG

from .routers import accounts, auth, gacha, geetest, i18n, login
from .session import SignedCookieSessionMiddleware

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    await Tortoise.init(config=DB_CONFIG)
    try:
        yield
    finally:
        await Tortoise.close_connections()


app = FastAPI(title="Hoyo Buddy Web API", lifespan=lifespan)

# Session middleware — must be added BEFORE CORS so it wraps the entire request
app.add_middleware(
    SignedCookieSessionMiddleware, secret_key=CONFIG.fernet_key, https_only=CONFIG.env == "prod"
)

# CORS — allow the React frontend origin
allowed_origins = [FRONTEND_URLS["prod"], FRONTEND_URLS["dev"]]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,  # Required for session cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(login.router, prefix="/api/login", tags=["login"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(gacha.router, prefix="/api/gacha", tags=["gacha"])
app.include_router(i18n.router, prefix="/api/i18n", tags=["i18n"])
# Geetest router is mounted at root to keep relative URLs in HTML pages working
app.include_router(geetest.router, prefix="", tags=["geetest"])
