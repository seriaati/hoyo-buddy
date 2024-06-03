from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands

from ..db.models import HoyoAccount
from ..exceptions import AccountNotFoundError

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, USER


class HoyoAccountTransformer(app_commands.Transformer):
    async def transform(self, i: INTERACTION, value: str) -> HoyoAccount:
        try:
            account_id = int(value)
        except ValueError as e:
            raise AccountNotFoundError from e

        user: USER = i.namespace.user
        user = user or i.user
        account = await HoyoAccount.get_or_none(id=account_id)
        if account is None:
            raise AccountNotFoundError
        return account
