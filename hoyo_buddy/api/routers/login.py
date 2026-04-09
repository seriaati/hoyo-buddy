from __future__ import annotations

import base64
import io
import uuid
from typing import Annotated, Any

import genshin
import orjson
import qrcode
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from hoyo_buddy.api.utils import decrypt_string, encrypt_string
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import locale_to_gpy_lang
from hoyo_buddy.enums import Locale, Platform
from hoyo_buddy.hoyo.clients.gpy import ProxyGenshinClient
from hoyo_buddy.utils import dict_cookie_to_str
from hoyo_buddy.utils.misc import get_project_version

from ..deps import get_or_create_device_id, get_session, require_auth
from ..schemas import (
    DeviceInfoRequest,
    DevToolsCookiesRequest,
    EmailPasswordRequest,
    EmailVerifyRequest,
    LoginFlowResponse,
    MobileRequest,
    ModAppRequest,
    OTPVerifyRequest,
    QRCodeResponse,
    QRCodeStatusResponse,
    RawCookiesRequest,
)

router = APIRouter()


def _get_login_flow(session: dict[str, Any]) -> dict[str, Any]:
    """Return (and lazily create) the login_flow sub-dict in the session.

    Always re-assigns ``session["login_flow"]`` so that the session middleware
    detects the mutation and persists the updated cookie, even when the key
    already existed and only nested values were changed.
    """
    login_flow: dict[str, Any] = session.get("login_flow") or {}
    session["login_flow"] = login_flow  # always triggers _SessionDict.__setitem__ → modified=True
    return login_flow


# ── Email / Password ──────────────────────────────────────────────────────────


@router.post("/email-password", response_model=LoginFlowResponse)
async def email_password_login(
    body: EmailPasswordRequest,
    platform: Annotated[str, Query()],
    session: Annotated[dict[str, Any], Depends(get_session)],
    user_id: Annotated[int, Depends(require_auth)],
    device_id: Annotated[str, Depends(get_or_create_device_id)],
) -> LoginFlowResponse:
    """Attempt email/password login for the given platform."""
    try:
        platform_enum = Platform(platform)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid platform: {platform}") from exc

    locale_str: str = session.get("locale", "en-US")
    try:
        locale = Locale(locale_str)
    except ValueError:
        locale = Locale.american_english

    login_flow = _get_login_flow(session)
    login_flow["platform"] = platform_enum.value
    login_flow["device_id"] = device_id
    logger.debug(f"[{user_id}] Using device_id for login: {device_id}")

    region = (
        genshin.Region.CHINESE if platform_enum is Platform.MIYOUSHE else genshin.Region.OVERSEAS
    )
    client = ProxyGenshinClient(region=region, lang=locale_to_gpy_lang(locale), proxy_url=CONFIG.residential_proxy)

    try:
        logger.debug(f"[{user_id}] Attempting email/password login for platform {platform_enum}")
        if platform_enum is Platform.HOYOLAB:
            result = await client._app_login(
                body.email,
                body.password,
                device_id=device_id,
                device_name="Hoyo Buddy",
                device_model=get_project_version(),
            )
        else:
            result = await client._cn_web_login(body.email, body.password)
    except genshin.GenshinException as exc:
        logger.debug(f"[{user_id}] Email/password login failed: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(f"[{user_id}] Email/password login error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if isinstance(result, genshin.models.SessionMMT):
        logger.debug(f"[{user_id}] Login requires geetest v3")
        login_flow["gt_type"] = "on_login"
        login_flow["gt_version"] = 3
        login_flow["encrypted_email"] = encrypt_string(body.email)
        login_flow["encrypted_password"] = encrypt_string(body.password)
        return LoginFlowResponse(next_step="geetest", gt_version=3, mmt=result.model_dump())

    if isinstance(result, genshin.models.SessionMMTv4):
        logger.debug(f"[{user_id}] Login requires geetest v4")
        login_flow["gt_type"] = "on_login"
        login_flow["gt_version"] = 4
        login_flow["encrypted_email"] = encrypt_string(body.email)
        login_flow["encrypted_password"] = encrypt_string(body.password)
        return LoginFlowResponse(
            next_step="geetest",
            gt_version=4,
            api_server="gcaptcha4.captchami.com",
            mmt=result.model_dump(),
        )

    if isinstance(result, genshin.models.ActionTicket):
        logger.debug(f"[{user_id}] Login requires email verification")
        login_flow["encrypted_email"] = encrypt_string(body.email)
        login_flow["encrypted_password"] = encrypt_string(body.password)
        try:
            email_result = await client._send_verification_email(result)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if isinstance(email_result, genshin.models.SessionMMT):
            logger.debug(f"[{user_id}] Geetest v3 required before sending verification email")
            login_flow["gt_type"] = "on_email_send"
            login_flow["gt_version"] = 3
            login_flow["action_ticket"] = orjson.dumps(result.model_dump()).decode()
            return LoginFlowResponse(
                next_step="geetest", gt_version=3, mmt=email_result.model_dump()
            )

        logger.debug(f"[{user_id}] Verification email sent successfully")
        login_flow["action_ticket"] = orjson.dumps(result.model_dump()).decode()
        return LoginFlowResponse(next_step="email_verify")

    # Successful login — store encrypted cookies
    logger.debug(f"[{user_id}] Login successful, storing cookies in session")
    cookies = result.to_str()
    login_flow["encrypted_cookies"] = encrypt_string(cookies)
    return LoginFlowResponse(next_step="finish")


# ── Geetest callback ──────────────────────────────────────────────────────────


@router.post("/geetest-callback", response_model=LoginFlowResponse)
async def geetest_callback(
    mmt_result: dict,
    session: Annotated[dict[str, Any], Depends(get_session)],
    user_id: Annotated[int, Depends(require_auth)],
    device_id: Annotated[str, Depends(get_or_create_device_id)],
) -> LoginFlowResponse:
    """Called after the user completes the geetest captcha. Retries the blocked operation."""
    logger.debug(f"[{user_id}] Geetest callback received")

    login_flow = _get_login_flow(session)
    gt_type: str | None = login_flow.get("gt_type")
    if gt_type is None:
        raise HTTPException(status_code=400, detail="No geetest type in session")
    logger.debug(f"[{user_id}] Geetest type from session: {gt_type}")

    gt_version: int = login_flow.get("gt_version", 3)
    parsed_mmt_result: genshin.models.SessionMMTResult | genshin.models.SessionMMTv4Result
    if gt_version == 4:
        parsed_mmt_result = genshin.models.SessionMMTv4Result(**mmt_result)
    else:
        parsed_mmt_result = genshin.models.SessionMMTResult(**mmt_result)

    locale_str: str = session.get("locale", "en-US")
    try:
        locale = Locale(locale_str)
    except ValueError:
        locale = Locale.american_english

    if gt_type == "on_login":
        encrypted_email = login_flow.get("encrypted_email")
        encrypted_password = login_flow.get("encrypted_password")
        if not encrypted_email or not encrypted_password:
            raise HTTPException(status_code=400, detail="Missing email/password in session")

        email = decrypt_string(encrypted_email)
        password = decrypt_string(encrypted_password)
        login_flow["device_id"] = device_id

        client = ProxyGenshinClient(lang=locale_to_gpy_lang(locale), proxy_url=CONFIG.residential_proxy)
        try:
            logger.debug(f"[{user_id}] Retrying login after geetest with device_id: {device_id}")
            result = await client._app_login(
                email,
                password,
                mmt_result=parsed_mmt_result,
                device_id=device_id,
                device_name="Hoyo Buddy",
                device_model=get_project_version(),
            )
        except Exception as exc:
            logger.debug(f"[{user_id}] Login retry after geetest failed: {exc}")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if isinstance(result, genshin.models.ActionTicket):
            login_flow["action_ticket"] = orjson.dumps(result.model_dump()).decode()
            try:
                logger.debug(f"[{user_id}] Sending verification email after geetest")
                email_result = await client._send_verification_email(result)
            except Exception as exc:
                logger.debug(f"[{user_id}] Failed to send verification email: {exc}")
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            if isinstance(email_result, genshin.models.SessionMMT):
                login_flow["gt_type"] = "on_email_send"
                login_flow["gt_version"] = 3
                return LoginFlowResponse(
                    next_step="geetest", gt_version=3, mmt=email_result.model_dump()
                )

            return LoginFlowResponse(next_step="email_verify")

        cookies = result.to_str()
        login_flow["encrypted_cookies"] = encrypt_string(cookies)
        return LoginFlowResponse(next_step="finish")

    if gt_type == "on_email_send":
        return LoginFlowResponse(next_step="email_verify")

    if gt_type == "on_otp_send":
        encrypted_mobile = login_flow.get("encrypted_mobile")
        if not encrypted_mobile:
            raise HTTPException(status_code=400, detail="Missing mobile in session")

        mobile = decrypt_string(encrypted_mobile)
        client = ProxyGenshinClient(region=genshin.Region.CHINESE)
        try:
            await client._send_mobile_otp(
                mobile, mmt_result=genshin.models.SessionMMTResult(**mmt_result)
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return LoginFlowResponse(next_step="verify_otp")

    raise HTTPException(status_code=400, detail=f"Unknown geetest type: {gt_type}")


# ── Email verification ────────────────────────────────────────────────────────


@router.post("/email-verify", response_model=LoginFlowResponse)
async def email_verify(
    body: EmailVerifyRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
    device_id: Annotated[str, Depends(get_or_create_device_id)],
) -> LoginFlowResponse:
    """Verify the email verification code and complete the login."""
    login_flow = _get_login_flow(session)

    str_action_ticket = login_flow.get("action_ticket")
    encrypted_email = login_flow.get("encrypted_email")
    encrypted_password = login_flow.get("encrypted_password")

    if not str_action_ticket or not encrypted_email or not encrypted_password:
        raise HTTPException(status_code=400, detail="Missing login data in session")

    action_ticket = genshin.models.ActionTicket(**orjson.loads(str_action_ticket.encode()))
    email = decrypt_string(encrypted_email)
    password = decrypt_string(encrypted_password)
    login_flow["device_id"] = device_id

    client = ProxyGenshinClient(proxy_url=CONFIG.residential_proxy)
    try:
        await client._verify_email(body.code, action_ticket)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        result = await client._app_login(
            email,
            password,
            ticket=action_ticket,
            device_id=device_id,
            device_name="Hoyo Buddy",
            device_model=get_project_version(),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cookies = result.to_str()
    login_flow["encrypted_cookies"] = encrypt_string(cookies)
    return LoginFlowResponse(next_step="finish")


# ── Mobile OTP ────────────────────────────────────────────────────────────────


@router.post("/mobile-send-otp", response_model=LoginFlowResponse)
async def mobile_send_otp(
    body: MobileRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> LoginFlowResponse:
    """Send an OTP to the given mobile number."""
    login_flow = _get_login_flow(session)
    client = ProxyGenshinClient(region=genshin.Region.CHINESE)

    try:
        result = await client._send_mobile_otp(body.mobile)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if isinstance(result, genshin.models.SessionMMTv4):
        login_flow["gt_type"] = "on_otp_send"
        login_flow["encrypted_mobile"] = encrypt_string(body.mobile)
        return LoginFlowResponse(next_step="geetest", gt_version=4, mmt=result.model_dump())

    login_flow["encrypted_mobile"] = encrypt_string(body.mobile)
    return LoginFlowResponse(next_step="verify_otp")


@router.post("/mobile-verify", response_model=LoginFlowResponse)
async def mobile_verify(
    body: OTPVerifyRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> LoginFlowResponse:
    """Verify the mobile OTP and complete the login."""
    login_flow = _get_login_flow(session)
    encrypted_mobile = login_flow.get("encrypted_mobile")
    if not encrypted_mobile:
        raise HTTPException(status_code=400, detail="Missing mobile in session")

    mobile = decrypt_string(encrypted_mobile)
    client = ProxyGenshinClient(region=genshin.Region.CHINESE)

    try:
        result = await client._login_with_mobile_otp(mobile, body.code)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    cookies = result.to_str()
    login_flow["encrypted_cookies"] = encrypt_string(cookies)
    return LoginFlowResponse(next_step="finish")


# ── Dev Tools (cookie fields) ─────────────────────────────────────────────────


@router.post("/dev-tools", response_model=LoginFlowResponse)
async def dev_tools_login(
    body: DevToolsCookiesRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> LoginFlowResponse:
    """Accept individual cookie fields and store them encrypted in the session."""
    cookies = (
        f"ltuid_v2={body.ltuid_v2}; "
        f"account_id_v2={body.account_id_v2}; "
        f"ltoken_v2={body.ltoken_v2}; "
        f"ltmid_v2={body.ltmid_v2}; "
        f"account_mid_v2={body.account_mid_v2}"
    )
    login_flow = _get_login_flow(session)
    login_flow["encrypted_cookies"] = encrypt_string(cookies)
    return LoginFlowResponse(next_step="finish")


# ── Raw cookies ───────────────────────────────────────────────────────────────


@router.post("/raw-cookies", response_model=LoginFlowResponse)
async def raw_cookies_login(
    body: RawCookiesRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> LoginFlowResponse:
    """Accept a raw cookie string and store it encrypted in the session."""
    login_flow = _get_login_flow(session)
    login_flow["encrypted_cookies"] = encrypt_string(body.cookies)
    return LoginFlowResponse(next_step="finish")


# ── Mod App ───────────────────────────────────────────────────────────────────


@router.post("/mod-app", response_model=LoginFlowResponse)
async def mod_app_login(
    body: ModAppRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> LoginFlowResponse:
    """Parse mod-app login details, extract device info, and store cookies in session."""
    login_flow = _get_login_flow(session)

    dict_cookies = genshin.parse_cookie(body.login_details)
    device_id = dict_cookies.pop("x-rpc-device_id", None)
    device_fp = dict_cookies.pop("x-rpc-device_fp", None)

    if device_id is not None:
        login_flow["device_id"] = device_id
    if device_fp is not None:
        login_flow["device_fp"] = device_fp

    cookies = dict_cookie_to_str(dict_cookies)
    login_flow["encrypted_cookies"] = encrypt_string(cookies)
    return LoginFlowResponse(next_step="finish")


# ── QR Code ───────────────────────────────────────────────────────────────────


@router.post("/qrcode/create", response_model=QRCodeResponse)
async def create_qrcode(
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> QRCodeResponse:
    """Generate a QR code for Miyoushe login."""
    client = ProxyGenshinClient(region=genshin.Region.CHINESE)
    result = await client._create_qrcode()

    # Generate QR code image as base64
    im = qrcode.make(result.url)
    buffer = io.BytesIO()
    im.save(buffer)  # type: ignore[arg-type]
    image_base64 = base64.b64encode(buffer.getvalue()).decode()

    # Store ticket in session
    login_flow = _get_login_flow(session)
    login_flow["qrcode_ticket"] = result.ticket

    return QRCodeResponse(ticket=result.ticket, image_base64=image_base64)


@router.post("/qrcode/check", response_model=QRCodeStatusResponse)
async def check_qrcode(
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> QRCodeStatusResponse:
    """Check the status of the QR code login."""
    login_flow = _get_login_flow(session)
    ticket: str | None = login_flow.get("qrcode_ticket")
    if not ticket:
        raise HTTPException(status_code=400, detail="No QR code ticket in session")

    client = ProxyGenshinClient(region=genshin.Region.CHINESE)
    try:
        status, cookies = await client._check_qrcode(ticket)
    except genshin.GenshinException as exc:
        if exc.retcode == -106:
            raise HTTPException(status_code=410, detail="QR code expired") from exc
        raise HTTPException(status_code=400, detail=exc.msg) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if status is genshin.models.QRCodeStatus.CONFIRMED:
        dict_cookies = {key: morsel.value for key, morsel in cookies.items()}
        encrypted_cookies = encrypt_string(dict_cookie_to_str(dict_cookies))
        login_flow["encrypted_cookies"] = encrypted_cookies
        return QRCodeStatusResponse(status="confirmed", cookies_saved=True)

    if status is genshin.models.QRCodeStatus.SCANNED:
        return QRCodeStatusResponse(status="scanned", cookies_saved=False)

    return QRCodeStatusResponse(status="pending", cookies_saved=False)


# ── Device Info ───────────────────────────────────────────────────────────────


@router.post("/device-info", response_model=LoginFlowResponse)
async def submit_device_info(
    body: DeviceInfoRequest,
    session: Annotated[dict[str, Any], Depends(get_session)],
    _user_id: Annotated[int, Depends(require_auth)],
) -> LoginFlowResponse:
    """Parse device info JSON, generate device_fp if needed, and store in session."""
    try:
        device_info_dict = orjson.loads(body.device_info)
    except orjson.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid JSON in device_info") from exc

    if not isinstance(device_info_dict, dict):
        raise HTTPException(status_code=422, detail="device_info must be a JSON object")

    # Override oaid with aaid if provided
    if body.aaid:
        device_info_dict["oaid"] = body.aaid.strip()

    device_id: str = device_info_dict.get("device_id", str(uuid.uuid4()).lower())

    client = ProxyGenshinClient(region=genshin.Region.CHINESE)
    try:
        device_fp: str = device_info_dict.get(
            "device_fp",
            await client.generate_fp(
                device_id=device_id,
                device_board=device_info_dict["deviceBoard"],
                oaid=device_info_dict["oaid"],
            ),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    login_flow = _get_login_flow(session)
    login_flow["device_id"] = device_id
    login_flow["device_fp"] = device_fp
    return LoginFlowResponse(next_step="finish")
