from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands

from ..db.models import HoyoAccount
from ..exceptions import AccountNotFoundError

if TYPE_CHECKING:
    from ..bot.bot import Interaction, User


class HoyoAccountTransformer(app_commands.Transformer):
    async def transform(self, i: Interaction, value: str) -> HoyoAccount:
        try:
            account_id = int(value)
        except ValueError as e:
            raise AccountNotFoundError from e

        user: User = i.namespace.user
        account = (
            await HoyoAccount.get_or_none(
                id=account_id, user_id=user.id if user is not None else i.user.id
            )
            if user is None or i.user.id == user.id
            else await HoyoAccount.get_or_none(id=account_id, user_id=user.id, public=True)
        )
        if account is None:
            raise AccountNotFoundError

        return account
