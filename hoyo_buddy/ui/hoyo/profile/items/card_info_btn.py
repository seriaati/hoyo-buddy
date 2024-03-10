from typing import TYPE_CHECKING

from hoyo_buddy.bot.translator import LocaleStr
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import INFO
from hoyo_buddy.enums import Game
from hoyo_buddy.ui.components import Button

if TYPE_CHECKING:
    from hoyo_buddy.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class CardInfoButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=0)

    async def callback(self, i: "INTERACTION") -> None:
        if self.view.game is Game.STARRAIL:
            embed = DefaultEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("About Star Rail Cards", key="profile.card_info.embed.title"),
                description=LocaleStr(
                    "- Star Rail cards are a way to show off your character builds.\n"
                    "- All assets used in the cards belong to Hoyoverse, I do not own them.\n"
                    "- All fanarts used in the cards are credited to their respective artists.\n"
                    "- This Hoyo Buddy template's design is original, you are not allowed to use it without permission.\n"
                    "- Game data is provided by the [mihomo API](https://api.mihomo.me/).\n"
                    "- Suggestions are welcome, you can contribute to the card data (adding fanarts, fixing colors, etc.) by reaching me in the [Discord Server](https://dsc.gg/hoyo-buddy).",
                    key="profile.card_info.embed.description",
                ),
            )
        else:
            embed = DefaultEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr(
                    "About Genshin Impact Cards", key="profile.card_info.gi.embed.title"
                ),
                description=LocaleStr(
                    "- Genshin Impact cards are a way to show off your character builds.\n"
                    "- All assets used in the cards belong to Hoyoverse, I do not own them.\n"
                    "- All fanarts used in the cards are credited to their respective artists.\n"
                    "- This Hoyo Buddy template's design is original, you are not allowed to use it without permission.\n"
                    "- Game data is provided by the [Enka.Network API](https://api.enka.network/).\n"
                    "- Suggestions are welcome, you can contribute to the card data (adding fanarts, fixing colors, etc.) by reaching me in the [Discord Server](https://dsc.gg/hoyo-buddy).",
                    key="profile.card_info.gi.embed.description",
                ),
            )

        await i.response.send_message(embed=embed, ephemeral=True)
