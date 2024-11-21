from __future__ import annotations

import urllib.parse
from typing import TYPE_CHECKING

from ..constants import GEETEST_SERVERS
from ..db.models import HoyoAccount, User, get_locale
from ..embeds import DefaultEmbed
from ..l10n import LocaleStr
from ..models import GeetestCommandPayload
from ..ui import URLButtonView

if TYPE_CHECKING:
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
        client.set_lang(i.locale)
        mmt = await client.create_mmt()

        # Save mmt to db
        await User.filter(id=i.user.id).update(temp_data=mmt.dict())

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
        )
        url = f"{GEETEST_SERVERS[i.client.env]}/captcha?{payload.to_query_string()}"
        url = urllib.parse.quote(url, safe=":/?&=")

        view = URLButtonView(locale, url=url, label=LocaleStr(key="complete_geetest_button_label"))

        embed = DefaultEmbed(
            locale,
            title=LocaleStr(key="complete_geetest_button_label"),
            description=LocaleStr(key="complete_geetest_button_description"),
        ).add_acc_info(self._account)

        await i.followup.send(embed=embed, view=view, ephemeral=True)
