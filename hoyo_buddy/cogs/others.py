from typing import TYPE_CHECKING, Any

from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from ..bot.translator import LocaleStr
from ..db.models import Settings as UserSettings
from ..embeds import DefaultEmbed
from ..ui.feedback import FeedbackView

if TYPE_CHECKING:
    from ..bot.bot import INTERACTION, HoyoBuddy


class Others(commands.Cog):
    def __init__(self, bot: "HoyoBuddy") -> None:
        self.bot = bot

    @app_commands.command(
        name=locale_str("feedback", translate=False),
        description=locale_str(
            "Give feedback to the bot's developer", key="feedback_command_description"
        ),
    )
    async def feedback_command(self, i: "INTERACTION") -> Any:
        await i.response.defer()
        locale = (await UserSettings.get(user_id=i.user.id)).locale or i.locale
        view = FeedbackView(author=i.user, locale=locale, translator=self.bot.translator)
        embed = DefaultEmbed(
            locale,
            self.bot.translator,
            description=LocaleStr(
                (
                    "🤗 Hi! Thanks for taking the time to give me feedback.\n"
                    "Click on the button below to start.\n\n"
                    "Note: I might contact you for more details. So please keep your DMs opened (or join the Hoyo Buddy Discord server)."
                ),
                key="feedback_command.description",
            ),
        )
        owner = await i.client.fetch_user(i.client.owner_id)
        assert owner is not None
        embed.set_author(name=owner.display_name, icon_url=owner.display_avatar.url)
        embed.set_footer(
            text=LocaleStr(
                "",
                key="feedback_command.footer",
            )
        )
        await i.followup.send(embed=embed, view=view)


async def setup(bot: "HoyoBuddy") -> None:
    await bot.add_cog(Others(bot))
