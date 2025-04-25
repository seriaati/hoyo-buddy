from __future__ import annotations

from typing import TYPE_CHECKING

from discord import app_commands

from hoyo_buddy.db import HoyoAccount
from hoyo_buddy.db.utils import build_account_query

from ..exceptions import AccountNotFoundError

if TYPE_CHECKING:
    from collections.abc import Sequence

    from hoyo_buddy.enums import Game

    from ..types import Interaction, User


class HoyoAccountTransformer(app_commands.Transformer):
    def __init__(self, games: Sequence[Game] | None) -> None:
        self.games = list(games) if games is not None else []

    def _lb_view_games(self, i: Interaction) -> None:
        games = i.client.get_lb_type_games(i)
        self.games.extend(games)

    async def transform(self, i: Interaction, value: str) -> HoyoAccount:
        self._lb_view_games(i)

        try:
            account_id = int(value)
        except ValueError as e:
            raise AccountNotFoundError from e

        user: User = i.namespace.user
        games = self.games or None

        if user is None or i.user.id == user.id:
            query = build_account_query(
                games=games, user_id=user.id if user is not None else i.user.id, id=account_id
            )
        else:
            query = build_account_query(games=games, user_id=user.id, public=True, id=account_id)

        try:
            account = await HoyoAccount.get_or_none(query)
        except Exception as e:
            raise AccountNotFoundError from e

        if account is None:
            raise AccountNotFoundError

        return account
