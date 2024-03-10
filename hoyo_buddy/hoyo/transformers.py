from typing import TYPE_CHECKING

from discord import app_commands

from ..db.models import HoyoAccount
from ..exceptions import AccountNotFoundError

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION


class HoyoAccountTransformer(app_commands.Transformer):
    async def transform(self, i: "INTERACTION", value: str) -> HoyoAccount:
        try:
            uid, game = value.split("_")
        except ValueError as e:
            raise AccountNotFoundError from e

        account = await HoyoAccount.get_or_none(uid=uid, game=game, user_id=i.user.id)
        if account is None:
            raise AccountNotFoundError
        return account
