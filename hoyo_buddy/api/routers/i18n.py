from __future__ import annotations

from fastapi import APIRouter, HTTPException

from hoyo_buddy.enums import Locale
from hoyo_buddy.l10n import LocaleStr, translator

from ..schemas import I18nResponse

router = APIRouter()


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
    for key in translator._l10n.get(locale.replace("-", "_"), {}):
        if not key.startswith("web."):
            continue

        try:
            translated = translator.translate(LocaleStr(key=key), locale_enum)
            translations[key] = translated
        except Exception:
            # Fall back to the key itself if translation fails
            translations[key] = key

    return I18nResponse(locale=locale, translations=translations)
