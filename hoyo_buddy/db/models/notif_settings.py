# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING

from tortoise import fields

from .base import BaseModel

if TYPE_CHECKING:
    from .hoyo_account import HoyoAccount


class AccountNotifSettings(BaseModel):
    ALL_FIELDS = (
        "notify_on_checkin_failure",
        "notify_on_checkin_success",
        "mimo_task_success",
        "mimo_task_failure",
        "mimo_buy_success",
        "mimo_buy_failure",
        "mimo_draw_success",
        "mimo_draw_failure",
        "redeem_success",
        "redeem_failure",
    )

    # Future me: Make sure to change NOTIF_SETTING_FIELDS in constants.py if you modify this section
    notify_on_checkin_failure = fields.BooleanField(default=True)
    notify_on_checkin_success = fields.BooleanField(default=True)
    mimo_task_success = fields.BooleanField(default=True)
    mimo_task_failure = fields.BooleanField(default=True)
    mimo_buy_success = fields.BooleanField(default=True)
    mimo_buy_failure = fields.BooleanField(default=True)
    mimo_draw_success = fields.BooleanField(default=True)
    mimo_draw_failure = fields.BooleanField(default=True)
    redeem_success = fields.BooleanField(default=True)
    redeem_failure = fields.BooleanField(default=True)

    web_events = fields.BooleanField(default=False)

    account: fields.OneToOneRelation[HoyoAccount] = fields.OneToOneField(
        "models.HoyoAccount", related_name="notif_settings", pk=True
    )
