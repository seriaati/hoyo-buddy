from __future__ import annotations

from fastapi import APIRouter, HTTPException

from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr, translator

from ..schemas import I18nResponse

router = APIRouter()

# Keys used by the React frontend — extend this list as the frontend grows
FRONTEND_KEYS = [
    # General
    "loading_text",
    "submit_button_label",
    "close_button_label",
    "required_field_error_message",
    # Login system
    "add_account_button_label",
    "account_add_start_message",
    "hbls_button_label",
    "email_password_button_label",
    "enter_email_password_instructions_description",
    "email_password_modal_email_input_label",
    "email_password_modal_password_input_label",
    "instructions_title",
    "devtools_instructions_description",
    "show_tutorial_button_label",
    "too_many_requests_error_banner_msg",
    # Email verification
    "email_verification_dialog_title",
    "email_verification_dialog_content",
    "email_verification_field_label",
    "email_verification_dialog_action",
    # Account selection
    "select_account.embed.title",
    "select_account.embed.description",
    "accounts_added_snackbar_message",
    "fetching_accounts",
    "fetching_accounts_stuck",
    "no_game_accounts_error_message",
    # Geetest
    "geetest.embed.title",
    "email-geetest.embed.title",
    "captcha.embed.description",
    "complete_captcha_button_label",
    "captcha_not_showing_up",
    "open_captcha_button_label",
    "captcha_verifying",
    # Gacha log
    "gacha_log_stats_title",
    "gacha_log_view_full",
    "gacha_log_view_banner_type_selector_placeholder",
    "gacha_log_personal_stats_title",
    "gacha_log_global_stats_title",
    "gacha_log_personal_stats_lifetime",
    "gacha_log_personal_stats_banner_total",
    "gacha_log_personal_stats_pity",
    "gacha_log_personal_stats_rarity_total",
    "gacha_log_personal_stats_rarity_average",
    "gacha_log_global_stats_lifetime",
    "gacha_log_global_stats_luck",
    "star5_guaranteed",
    "star5_no_guaranteed",
    "win_rate_stats",
    "win_rate_global_stats",
    "top_percent",
]


@router.get("/{locale}", response_model=I18nResponse)
async def get_translations(locale: str) -> I18nResponse:
    """Return all frontend translation strings for the given locale."""
    try:
        locale_enum = Locale(locale)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid locale: {locale}") from exc

    if not translator.loaded:
        raise HTTPException(status_code=503, detail="Translator not loaded yet")

    translations: dict[str, str] = {}
    for key in FRONTEND_KEYS:
        try:
            translated = translator.translate(LocaleStr(key=key), locale_enum)
            translations[key] = translated
        except Exception:
            # Fall back to the key itself if translation fails
            translations[key] = key

    return I18nResponse(locale=locale, translations=translations)
