from typing import TYPE_CHECKING

from src.bot.emojis import INFO
from src.bot.translator import LocaleStr
from src.embeds import DefaultEmbed
from src.ui.components import Button

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION

    from ..view import ProfileView  # noqa: F401


class CardInfoButton(Button["ProfileView"]):
    def __init__(self) -> None:
        super().__init__(emoji=INFO, row=0)

    async def callback(self, i: "INTERACTION") -> None:
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
        await i.response.send_message(embed=embed, ephemeral=True)
