from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from genshin import Game as GenshinGame
from tortoise.exceptions import IntegrityError

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME
from hoyo_buddy.db.models import AccountNotifSettings, HoyoAccount
from hoyo_buddy.emojis import get_game_emoji

from ...components import Select, SelectOption

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from genshin.models import GenshinAccount

    from hoyo_buddy.bot.bot import Interaction
    from hoyo_buddy.bot.translator import Translator

    from ..view import AccountManager  # noqa: F401


class AddAccountSelect(Select["AccountManager"]):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        accounts: Sequence[GenshinAccount],
        cookies: str,
    ) -> None:
        self.accounts = accounts
        self.cookies = cookies
        self.translator = translator
        self.locale = locale
        options = list(self.get_account_options())

        super().__init__(
            custom_id="select_accounts_to_add",
            options=options,
            max_values=len(options),
            placeholder=LocaleStr(
                "Select the accounts you want to add...",
                key="select_accounts_to_add_placeholder",
            ),
        )

    def get_account_options(self) -> Generator[SelectOption, None, None]:
        for account in self.accounts:
            if isinstance(account.game, GenshinGame):
                level_str = self.translator.translate(
                    LocaleStr(
                        "Lv.{level}",
                        key="level_str",
                        level=account.level,
                    ),
                    self.locale,
                )

                yield SelectOption(
                    label=f"[{account.uid}] {account.nickname}",
                    description=f"{level_str} | {account.server_name}",
                    value=f"{account.uid}_{account.game.value}",
                    emoji=get_game_emoji(account.game),
                )

    async def callback(self, i: Interaction) -> None:
        for value in self.values:
            uid, game = value.split("_")
            account = discord.utils.get(self.accounts, uid=int(uid), game__value=game)
            if account is None:
                msg = "Invalid account selected"
                raise ValueError(msg)

            try:
                hoyo_account = await HoyoAccount.create(
                    uid=account.uid,
                    username=account.nickname,
                    game=GPY_GAME_TO_HB_GAME[account.game],
                    cookies=self.cookies,
                    user=self.view.user,
                    server=account.server_name,
                )
            except IntegrityError:
                hoyo_account = await HoyoAccount.get(
                    uid=account.uid,
                    game=GPY_GAME_TO_HB_GAME[account.game],
                    user=self.view.user,
                )
                hoyo_account.cookies = self.cookies
                hoyo_account.username = account.nickname
                await hoyo_account.save()
            else:
                await AccountNotifSettings.create(account=hoyo_account)

            await self.view.user.set_acc_as_current(hoyo_account)

        self.view.user.temp_data.clear()
        await self.view.user.save(update_fields=("temp_data",))
        await self.view.refresh(i, soft=False)
