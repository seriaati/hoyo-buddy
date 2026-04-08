from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from hoyo_buddy.db import get_locale

from ..constants import FRONTEND_URLS
from ..embeds import DefaultEmbed
from ..l10n import LocaleStr
from ..models import GeetestCommandPayload
from ..ui import URLButtonView

if TYPE_CHECKING:
    from hoyo_buddy.db import HoyoAccount

    from ..bot import HoyoBuddy
    from ..enums import GeetestType
    from ..types import Interaction


class GeetestCommand:
    def __init__(self, bot: HoyoBuddy, account: HoyoAccount, type_: GeetestType) -> None:
        self._bot = bot
        self._account = account
        self._type = type_

    async def run(self, i: Interaction) -> None:
        locale = await get_locale(i)
        message = await i.original_response()

        client = self._account.client
        client.set_lang(locale)
        mmt = await client.create_mmt()

        payload = GeetestCommandPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild is not None else None,
            channel_id=message.channel.id,
            message_id=message.id,
            gt_version=3,
            api_server="api.geetest.com",
            account_id=self._account.id,
            gt_type=self._type,
            locale=locale.value,
            mmt=mmt.model_dump(),
        )
        url = f"{FRONTEND_URLS[i.client.env]}/geetest_command?{payload.to_query_string()}"
        url = urllib.parse.quote(url, safe=":/?&=")

        view = URLButtonView(locale, url=url, label=LocaleStr(key="complete_geetest_button_label"))

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(key="complete_geetest_button_label"),
            description=LocaleStr(key="complete_geetest_button_description"),
        ).add_acc_info(self._account)

        await i.followup.send(embed=embed, view=view, ephemeral=True)
