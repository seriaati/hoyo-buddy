# pyright: reportAssignmentType=false
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from loguru import logger
from tortoise import fields
from tortoise.exceptions import IntegrityError

from hoyo_buddy.constants import AUTO_TASK_TOGGLE_FIELDS, NOTIF_SETTING_FIELDS
from hoyo_buddy.embeds import DefaultEmbed, ErrorEmbed

from .base import BaseModel
from .hoyo_account import HoyoAccount
from .notif_settings import AccountNotifSettings

if TYPE_CHECKING:
    from hoyo_buddy.types import AutoTaskType

    from .user import User


class DiscordEmbed(BaseModel):
    id = fields.IntField(pk=True, generated=True)
    data: fields.Field[dict[str, Any]] = fields.JSONField()
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="embeds"
    )
    account: fields.ForeignKeyRelation[HoyoAccount] = fields.ForeignKeyField(
        "models.HoyoAccount", related_name="embeds"
    )
    task_type: AutoTaskType = fields.CharField(max_length=20)
    type: Literal["default", "error"] = fields.CharField(max_length=7)

    user_id: int
    account_id: int

    @classmethod
    async def create(
        cls,
        embed: DefaultEmbed | ErrorEmbed,
        *,
        user_id: int,
        account_id: int,
        task_type: AutoTaskType,
    ) -> None:
        notif_fields = NOTIF_SETTING_FIELDS.get(task_type, ())
        if len(notif_fields) < 2:
            logger.error(f"No notification fields found for task type: {task_type!r}")
            return

        toggle_field = AUTO_TASK_TOGGLE_FIELDS.get(task_type)
        if toggle_field is None:
            logger.error(f"No toggle field found for task type: {task_type!r}")
            return

        if isinstance(embed, ErrorEmbed):
            await HoyoAccount.filter(id=account_id).update(**{toggle_field: False})

        try:
            notif_settings, _ = await AccountNotifSettings.get_or_create(account_id=account_id)
        except IntegrityError:
            # The account got deleted at the time this embed was created
            return

        if isinstance(embed, DefaultEmbed):
            success_field = notif_fields[0]
            if not getattr(notif_settings, success_field):
                return
        else:
            failure_field = notif_fields[1]
            if not getattr(notif_settings, failure_field):
                return

        await super().create(
            data=embed.to_dict(),
            user_id=user_id,
            account_id=account_id,
            task_type=task_type,
            type="default" if isinstance(embed, DefaultEmbed) else "error",
        )
