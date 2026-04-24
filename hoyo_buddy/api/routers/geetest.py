from __future__ import annotations

import genshin
from fastapi import APIRouter, Depends, HTTPException

from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.enums import GeetestType

from ..auth import require_auth
from ..schemas import GeetestCommandRequest

router = APIRouter()


@router.post("/notify")
async def handle_geetest_notify(
    body: GeetestCommandRequest, auth=Depends(require_auth)
) -> dict[str, str]:
    """Perform the geetest-gated action (daily check-in or MMT verification) for an account."""
    try:
        gt_type = GeetestType(body.gt_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid gt_type: {body.gt_type}") from exc

    user_id = getattr(auth, "id", None)
    if user_id is None:
        user_id = getattr(auth, "user_id", None)
    if user_id is None and isinstance(auth, dict):
        user_id = auth.get("id") or auth.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    account = await HoyoAccount.get_or_none(id=body.account_id, user_id=user_id)
    if account is None:
        raise HTTPException(status_code=403, detail="Forbidden")

    client = account.client

    try:
        if gt_type is GeetestType.DAILY_CHECKIN:
            await client.claim_daily_reward(challenge=body.mmt_result)
        else:
            await client.verify_mmt(genshin.models.MMTResult(**body.mmt_result))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {"status": "ok"}
