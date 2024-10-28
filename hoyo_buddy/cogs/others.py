from __future__ import annotations

from typing import TYPE_CHECKING

import discord
import psutil
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from ..db.models import Settings as UserSettings
from ..db.models import get_dyk
from ..embeds import DefaultEmbed
from ..emojis import DISCORD_WHITE_ICON, GITHUB_WHITE_ICON
from ..l10n import LocaleStr
from ..ui import Button, View
from ..ui.settings import SettingsUI
from ..utils import ephemeral, get_discord_user_md_link

if TYPE_CHECKING:
    import git

    from ..bot import HoyoBuddy
    from ..types import Interaction


class Others(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot
        self.process = psutil.Process()
        self.repo_url = "https://github.com/seriaati/hoyo-buddy"

    def format_commit(self, commit: git.Commit) -> str:
        commit_url = f"{self.repo_url}/commit/{commit.hexsha}"
        dt_str = discord.utils.format_dt(commit.authored_datetime, "R")
        return f"[`{commit.hexsha[:7]}`]({commit_url}) {commit.summary} ({dt_str})"

    def get_last_commits(self, count: int = 5) -> str:
        commits = list(self.bot.repo.iter_commits("main", max_count=count))
        return "\n".join(self.format_commit(commit) for commit in commits)

    @app_commands.command(
        name=locale_str("about"), description=locale_str("About the bot", key="about_command_description")
    )
    async def about_command(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        guild = self.bot.get_guild(1000727526194298910) or await i.client.fetch_guild(1000727526194298910)
        if not guild.chunked:
            await guild.chunk()

        settings = await UserSettings.get(user_id=i.user.id)
        locale = settings.locale or i.locale
        embed = DefaultEmbed(
            locale=locale,
            translator=self.bot.translator,
            title=f"{self.bot.user.name if self.bot.user is not None else 'Hoyo Buddy'} {self.bot.version}",
            description=LocaleStr(key="about_embed.description"),
        )

        # latest changes
        embed.add_field(name=LocaleStr(key="about_command.latest_changes"), value=self.get_last_commits(), inline=False)

        # developer
        owner = await i.client.fetch_user(i.client.owner_id)
        if owner is not None:
            embed.add_field(
                name=LocaleStr(key="about_command.developer"), value=get_discord_user_md_link(owner), inline=False
            )

        # designer
        designer_role = guild.get_role(1266651937411960882)
        if designer_role is not None:
            designers = [get_discord_user_md_link(designer) for designer in designer_role.members]
            embed.add_field(name=LocaleStr(key="about_command.designers"), value=" ".join(designers), inline=False)

        # translators
        translator_role = guild.get_role(1010181916642787503)
        if translator_role is not None:
            translators = [get_discord_user_md_link(translator) for translator in translator_role.members]
            embed.add_field(name=LocaleStr(key="about_command.translators"), value=" ".join(translators), inline=False)

        # guild count
        embed.add_field(name=LocaleStr(key="about_command.guild_count"), value=str(len(i.client.guilds)))

        # ram usage
        memory_usage = self.process.memory_info().rss / 1024**2
        embed.add_field(name=LocaleStr(key="about_command.ram_usage"), value=f"{memory_usage:.2f} MB")

        # uptime
        uptime = discord.utils.format_dt(i.client.uptime, "R")
        embed.add_field(name=LocaleStr(key="about_command.uptime"), value=uptime)

        # url buttons
        view = View(locale=locale, translator=self.bot.translator, author=None)
        view.add_item(Button(label="GitHub", url=self.repo_url, emoji=GITHUB_WHITE_ICON, row=0))
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.discord_server"),
                url="https://link.seria.moe/hb-dc",
                emoji=DISCORD_WHITE_ICON,
                row=0,
            )
        )
        view.add_item(
            Button(label=LocaleStr(key="about_command.website"), url="https://seria.is-a.dev/hoyo-buddy", row=1)
        )
        view.add_item(Button(label=LocaleStr(key="about_command.support"), url="https://link.seria.moe/donate", row=1))
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.contribute"),
                url="https://github.com/seriaati/hoyo-buddy/blob/main/CONTRIBUTING.md",
                row=1,
            )
        )

        # brand image
        image_ = discord.File(
            SettingsUI.get_brand_img_filename("DARK" if settings.dark_mode else "LIGHT", locale), filename="brand.png"
        )
        embed.set_image(url="attachment://brand.png")

        view.message = await i.edit_original_response(
            embed=embed, attachments=[image_], view=view, content=await get_dyk(i)
        )


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Others(bot))
