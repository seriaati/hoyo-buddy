from typing import TYPE_CHECKING

from discord.utils import get as dget

from src.db.models import HoyoAccount

from ...components import Select, SelectOption

if TYPE_CHECKING:
    from ui.account.view import AccountManager  # noqa: F401

    from src.bot.bot import INTERACTION


class AccountSelect(Select["AccountManager"]):
    def __init__(self, options: list[SelectOption]) -> None:
        super().__init__(custom_id="account_selector", options=options)

    async def callback(self, i: "INTERACTION") -> None:
        uid, game = self.values[0].split("_")
        selected_account = dget(self.view.accounts, uid=int(uid), game__value=game)
        assert selected_account is not None

        await HoyoAccount.filter(user=self.view.user).update(current=False)
        selected_account.current = True
        await selected_account.save(update_fields=["current"])

        self.view.selected_account = selected_account
        await self.view.refresh(i, soft=True)
