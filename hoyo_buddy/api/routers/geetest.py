from __future__ import annotations

from typing import Annotated

import genshin
from fastapi import APIRouter, Depends, HTTPException

from hoyo_buddy.db.models import HoyoAccount
from hoyo_buddy.enums import GeetestType

from ..deps import require_auth
from ..schemas import GeetestCommandRequest

router = APIRouter()


@router.post("/command")
async def handle_geetest_command(
    body: GeetestCommandRequest, user_id: Annotated[int, Depends(require_auth)]
) -> dict[str, str]:
    """Perform the geetest-gated action (daily check-in or MMT verification) for an account."""
    try:
        gt_type = GeetestType(body.gt_type)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid gt_type: {body.gt_type}") from exc

    account = await HoyoAccount.get_or_none(id=body.account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    if account.user_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    client = account.client

    try:
        if gt_type is GeetestType.DAILY_CHECKIN:
            await client.claim_daily_reward(challenge=body.mmt_result)
        else:
            await client.verify_mmt(genshin.models.MMTResult(**body.mmt_result))
    except genshin.errors.AlreadyClaimed:
        raise HTTPException(status_code=400, detail="Daily reward already claimed") from None
    except genshin.errors.NoNeedGeetest:
        raise HTTPException(status_code=400, detail="Geetest not needed") from None
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to perform action: {e}") from e

    return {"status": "ok"}
