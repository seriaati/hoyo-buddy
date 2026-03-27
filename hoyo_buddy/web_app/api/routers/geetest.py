from __future__ import annotations

import random
import string
from pathlib import Path
from typing import Any, Literal

import aiohttp
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from loguru import logger
from tortoise import Tortoise

from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import FRONTEND_URLS, get_docs_url
from hoyo_buddy.db.models import User
from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr, translator
from hoyo_buddy.models import GeetestCommandPayload, GeetestLoginPayload
from hoyo_buddy.utils.misc import get_discord_url

router = APIRouter()

GT_V3_URL = "https://static.geetest.com/static/js/gt.0.5.0.js"
GT_V4_URL = "https://static.geetest.com/v4/gt4.js"

# hoyo_buddy/web_app/api/routers/geetest.py → go up 3 levels to reach hoyo_buddy/web_app/templates
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"
_login_template: str | None = None
_command_template: str | None = None


def _load_templates() -> None:
    global _login_template, _command_template  # noqa: PLW0603
    if _login_template is None:
        _login_template = (_TEMPLATES_DIR / "page_login.html").read_text(encoding="utf-8")
    if _command_template is None:
        _command_template = (_TEMPLATES_DIR / "page_command.html").read_text(encoding="utf-8")


@router.get("/captcha", response_class=HTMLResponse)
async def captcha(
    user_id: int | None = None,
    gt_type: str | None = None,
    gt_version: int | None = None,
    api_server: str | None = None,
    locale: str | None = None,
    guild_id: int | None = None,
    channel_id: int | None = None,
    message_id: int | None = None,
    account_id: int | None = None,
) -> HTMLResponse:
    """Serve the captcha HTML page."""
    _load_templates()

    if _login_template is None or _command_template is None:
        raise HTTPException(status_code=500, detail="Template not loaded")

    # Build a query-like mapping for parse_from_request
    query: dict[str, str] = {}
    if user_id is not None:
        query["user_id"] = str(user_id)
    if gt_type is not None:
        query["gt_type"] = gt_type
    if gt_version is not None:
        query["gt_version"] = str(gt_version)
    if api_server is not None:
        query["api_server"] = api_server
    if locale is not None:
        query["locale"] = locale
    if guild_id is not None:
        query["guild_id"] = str(guild_id)
    if channel_id is not None:
        query["channel_id"] = str(channel_id)
    if message_id is not None:
        query["message_id"] = str(message_id)
    if account_id is not None:
        query["account_id"] = str(account_id)

    try:
        if gt_type is not None:
            payload: GeetestCommandPayload | GeetestLoginPayload = (
                GeetestCommandPayload.parse_from_request(query)
            )
        else:
            payload = GeetestLoginPayload.parse_from_request(query)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Invalid query parameters") from e

    user_exists = await User.filter(id=payload.user_id).exists()
    if not user_exists:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        locale_enum = Locale(payload.locale)
    except ValueError:
        locale_enum = Locale.american_english

    body = (
        _login_template.replace("{ user_id }", str(payload.user_id))  # noqa: RUF027
        .replace("{ gt_version }", str(payload.gt_version))  # noqa: RUF027
        .replace("{ api_server }", payload.api_server)  # noqa: RUF027
        .replace(
            "{ captcha_not_showing_up }",
            translator.translate(LocaleStr(key="captcha_not_showing_up"), locale=locale_enum),
        )
        .replace(
            "{ captcha_not_showing_up_link }",
            get_docs_url("/captcha-blank-page", locale=locale_enum),
        )
        .replace(
            "{ open_captcha_button_label }",
            translator.translate(LocaleStr(key="open_captcha_button_label"), locale=locale_enum),
        )
        .replace(
            "{ loading_text }",
            translator.translate(LocaleStr(key="loading_text"), locale=locale_enum),
        )
        .replace(
            "{ captcha_verifying }",
            translator.translate(LocaleStr(key="captcha_verifying"), locale=locale_enum),
        )
    )

    if isinstance(payload, GeetestCommandPayload):
        body = (
            _command_template.replace("{ user_id }", str(payload.user_id))  # noqa: RUF027
            .replace("{ gt_version }", str(payload.gt_version))  # noqa: RUF027
            .replace("{ api_server }", payload.api_server)  # noqa: RUF027
            .replace(
                "{ captcha_not_showing_up }",
                translator.translate(LocaleStr(key="captcha_not_showing_up"), locale=locale_enum),
            )
            .replace(
                "{ captcha_not_showing_up_link }",
                get_docs_url("/captcha-blank-page", locale=locale_enum),
            )
            .replace(
                "{ open_captcha_button_label }",
                translator.translate(
                    LocaleStr(key="open_captcha_button_label"), locale=locale_enum
                ),
            )
            .replace(
                "{ loading_text }",
                translator.translate(LocaleStr(key="loading_text"), locale=locale_enum),
            )
            .replace(
                "{ captcha_verifying }",
                translator.translate(LocaleStr(key="captcha_verifying"), locale=locale_enum),
            )
            .replace("{ guild_id }", str(payload.guild_id))  # noqa: RUF027
            .replace("{ channel_id }", str(payload.channel_id))  # noqa: RUF027
            .replace("{ message_id }", str(payload.message_id))  # noqa: RUF027
            .replace("{ gt_type }", payload.gt_type.value)  # noqa: RUF027
            .replace("{ account_id }", str(payload.account_id))  # noqa: RUF027
            .replace("{ locale }", payload.locale)  # noqa: RUF027
        )

    return HTMLResponse(content=body)


@router.get("/gt/{version}.js")
async def gt_js(version: str) -> Response:
    """Proxy the Geetest JavaScript file."""
    gt_url = GT_V4_URL if version == "v4" else GT_V3_URL

    async with aiohttp.ClientSession() as session, session.get(gt_url) as r:
        content = await r.read()

    return Response(content=content, media_type="text/javascript")


@router.post("/send-data", status_code=204)
async def send_data_endpoint(data: dict[str, Any]) -> None:
    """Update user's temp_data with the solved geetest mmt and send a NOTIFY to the database."""
    gt_notif_type: Literal["login", "command"] = data.pop("gt_notif_type")
    user_id = data.pop("user_id")

    await User.filter(id=user_id).update(temp_data=data)

    if gt_notif_type == "command":
        message_id = data.pop("message_id")
        account_id = data.pop("account_id")
        gt_type = data.pop("gt_type")
        locale = data.pop("locale")
        channel_id = data.pop("channel_id")

        conn = Tortoise.get_connection("default")
        await conn.execute_query(
            f"NOTIFY geetest_command, '{user_id};{message_id};{gt_type};{account_id};{locale};{channel_id}'"
        )


@router.get("/redirect")
async def redirect_endpoint(
    user_id: int | None = None,
    channel_id: int | None = None,
    guild_id: str | None = None,
    message_id: str | None = None,
) -> RedirectResponse:
    """Redirect the user back to Discord with protocol link."""
    try:
        if user_id is not None:
            # login
            random_token = "".join(random.choices(string.ascii_letters + string.digits, k=16))
            url = FRONTEND_URLS[CONFIG.env] + f"/geetest?user_id={user_id}&token={random_token}"
        elif channel_id is not None:
            # command
            parsed_guild_id: int | None = None
            if guild_id is not None:
                try:
                    parsed_guild_id = int(guild_id)
                except ValueError:
                    parsed_guild_id = None

            parsed_message_id: int | None = None
            if message_id is not None:
                try:
                    parsed_message_id = int(message_id)
                except ValueError:
                    parsed_message_id = None

            url = get_discord_url(
                channel_id=channel_id, guild_id=parsed_guild_id, message_id=parsed_message_id
            )
        else:
            raise HTTPException(
                status_code=400, detail="Missing query parameter: user_id or channel_id"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in redirect endpoint")
        raise HTTPException(status_code=500, detail="Internal Server Error") from e

    return RedirectResponse(url=url, status_code=302)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint to ensure the server is running."""
    return {"status": "ok"}
