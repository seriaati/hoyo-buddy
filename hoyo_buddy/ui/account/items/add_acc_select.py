from typing import TYPE_CHECKING

import discord
from genshin import Game as GenshinGame
from tortoise.exceptions import IntegrityError

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.db.models import AccountNotifSettings, HoyoAccount
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.enums import GAME_CONVERTER

from ...components import Select, SelectOption

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

    from genshin.models import GenshinAccount
    from ui.account.view import AccountManager  # noqa: F401

    from hoyo_buddy.bot.bot import INTERACTION
    from hoyo_buddy.bot.translator import Translator


class AddAccountSelect(Select["AccountManager"]):
    def __init__(
        self,
        locale: discord.Locale,
        translator: "Translator",
        *,
        accounts: "Sequence[GenshinAccount]",
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

    def get_account_options(self) -> "Generator[SelectOption, None, None]":
        for account in self.accounts:
            if isinstance(account.game, GenshinGame):
                server_name = self.translator.translate(
                    LocaleStr(account.server_name, warn_no_key=False),
                    self.locale,
                )
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
                    description=f"{level_str} | {server_name}",
                    value=f"{account.uid}_{account.game.value}",
                    emoji=get_game_emoji(account.game),
                )

    async def callback(self, i: "INTERACTION") -> None:
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
                    game=GAME_CONVERTER[account.game],
                    cookies=self.cookies,
                    user=self.view.user,
                    server=account.server_name,
                )
            except IntegrityError:
                await HoyoAccount.filter(
                    uid=account.uid,
                    game=GAME_CONVERTER[account.game],
                    user=self.view.user,
                ).update(cookies=self.cookies, username=account.nickname)
            else:
                await AccountNotifSettings.create(account=hoyo_account)

        self.view.user.temp_data.pop("cookies", None)
        self.view.user.temp_data.pop("email", None)
        self.view.user.temp_data.pop("password", None)
        await self.view.user.save()
        await self.view.refresh(i, soft=False)
