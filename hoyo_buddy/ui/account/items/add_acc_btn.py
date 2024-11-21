from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle

from hoyo_buddy.constants import WEB_APP_URLS
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import ADD
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.web_app.schema import Params

from ...components import Button

if TYPE_CHECKING:
    from hoyo_buddy.types import Interaction

    from ..view import AccountManager
else:
    AccountManager = None


class AddAccountButton(Button[AccountManager]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_account",
            emoji=ADD,
            label=LocaleStr(key="add_account_button_label"),
            style=ButtonStyle.primary,
        )

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            title=LocaleStr(key="account_add_start_title"),
            description=LocaleStr(key="account_add_start_message"),
        )
        self.view.clear_items()
        params = Params(
            locale=self.view.locale.value,
            user_id=i.user.id,
            channel_id=i.channel.id if i.channel is not None else 0,
            guild_id=i.guild.id if i.guild is not None else None,
        )
        self.view.add_item(
            Button(
                label=LocaleStr(key="hbls_button_label"),
                url=WEB_APP_URLS[i.client.env] + f"/platforms?{params.to_query_string()}",
            )
        )
        await i.response.edit_message(embed=embed, view=self.view)
