from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import genshin
from tortoise.exceptions import IntegrityError

from hoyo_buddy.bot.translator import LevelStr, LocaleStr
from hoyo_buddy.constants import GPY_GAME_TO_HB_GAME
from hoyo_buddy.db.models import AccountNotifSettings, HoyoAccount
from hoyo_buddy.emojis import get_game_emoji
from hoyo_buddy.enums import Platform

from ...components import Select, SelectOption

if TYPE_CHECKING:
    from collections.abc import Sequence

    from genshin.models import GenshinAccount

    from hoyo_buddy.bot.translator import Translator
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager  # noqa: F401


class AddAccountSelect(Select["AccountManager"]):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        accounts: Sequence[GenshinAccount],
        cookies: str,
        platform: Platform,
        device_id: str | None,
        device_fp: str | None,
    ) -> None:
        self.accounts = accounts
        self.cookies = cookies
        self.translator = translator
        self.locale = locale

        self._region = (
            genshin.Region.CHINESE if platform is Platform.MIYOUSHE else genshin.Region.OVERSEAS
        )
        self._device_id = device_id
        self._device_fp = device_fp

        options = self.get_account_options()
        super().__init__(
            custom_id="select_accounts_to_add",
            options=options,
            max_values=len(options),
            placeholder=LocaleStr(
                key="select_accounts_to_add_placeholder",
            ),
        )

    def get_account_options(self) -> list[SelectOption]:
        result: list[SelectOption] = []
        added_vals: set[str] = set()
        for account in self.accounts:
            # Sometimes other Hoyo games might appear here, so we add this check
            if isinstance(account.game, genshin.Game):  # pyright: ignore [reportUnnecessaryIsInstance]
                level_str = self.translator.translate(LevelStr(account.level), self.locale)
                option_val = f"{account.uid}_{account.game.value}"
                if option_val in added_vals:
                    continue
                result.append(
                    SelectOption(
                        label=f"{account.nickname} ({account.uid})",
                        description=f"{level_str}",
                        value=option_val,
                        emoji=get_game_emoji(account.game),
                    )
                )
                added_vals.add(option_val)
        return result

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
                    device_id=self._device_id,
                    device_fp=self._device_fp,
                    region=self._region,
                )
            except IntegrityError:
                hoyo_account = await HoyoAccount.get(
                    uid=account.uid,
                    game=GPY_GAME_TO_HB_GAME[account.game],
                    user=self.view.user,
                )
                hoyo_account.cookies = self.cookies
                hoyo_account.username = account.nickname
                hoyo_account.device_id = self._device_id
                hoyo_account.device_fp = self._device_fp
                hoyo_account.region = self._region
                await hoyo_account.save(
                    update_fields=("cookies", "username", "device_id", "device_fp", "region")
                )
            else:
                await AccountNotifSettings.create(account=hoyo_account)

            await self.view.user.set_acc_as_current(hoyo_account)

        self.view.user.temp_data.clear()
        await self.view.user.save(update_fields=("temp_data",))
        await self.view.refresh(i, soft=False)
