from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO
from hoyo_buddy.ui.components import Button

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import Interaction

    from ..view import ProfileView  # noqa: F401


class CardInfoButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=0)

    async def callback(self, i: Interaction) -> None:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("About Character Build Cards", key="profile.card_info.embed.title"),
            description=LocaleStr(
                "- All assets used in the cards belong to Hoyoverse, I do not own them.\n"
                "- All fanarts used in the cards are credited to their respective artists.\n"
                "- The Hoyo Buddy templates' designs are original, you are not allowed to modify them or claim that you made them without my permission.\n"
                "- Game data is provided by {provider}.\n",
                key="profile.card_info.embed.description",
                provider="[Enka.Network](https://api.enka.network/)",
            ),
        )
        await i.response.send_message(embed=embed, ephemeral=True)
