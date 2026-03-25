from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import FRONTEND_URLS

from .routers import accounts, auth, gacha, i18n, login
from .session import SignedCookieSessionMiddleware

app = FastAPI(title="Hoyo Buddy Web API")

# Session middleware — must be added BEFORE CORS so it wraps the entire request
app.add_middleware(
    SignedCookieSessionMiddleware,
    secret_key=CONFIG.fernet_key,
    https_only=CONFIG.env == "prod",
)

# CORS — allow the React frontend origin
allowed_origins = [
    FRONTEND_URLS["prod"],
    FRONTEND_URLS["dev"],
]
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
