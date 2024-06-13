from __future__ import annotations

from typing import TYPE_CHECKING, Any

import discord
import psutil
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands

from ..bot.translator import LocaleStr
from ..db.models import Settings as UserSettings
from ..embeds import DefaultEmbed
from ..emojis import DISCORD_WHITE_ICON, GITHUB_WHITE_ICON
from ..ui.components import Button, View
from ..ui.feedback import FeedbackView
from ..ui.settings import SettingsUI
from ..utils import get_discord_user_md_link

if TYPE_CHECKING:
    import git

    from ..bot.bot import HoyoBuddy, Interaction


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
        name=locale_str("feedback"),
        description=locale_str(
            "Give feedback to the bot's developer", key="feedback_command_description"
        ),
    )
    async def feedback_command(self, i: Interaction) -> Any:
        await i.response.defer()
        locale = (await UserSettings.get(user_id=i.user.id)).locale or i.locale
        view = FeedbackView(author=i.user, locale=locale, translator=self.bot.translator)
        embed = DefaultEmbed(
            locale,
            self.bot.translator,
            description=LocaleStr(
                key="feedback_command.description",
            ),
        )
        owner = await i.client.fetch_user(i.client.owner_id)
        assert owner is not None
        embed.set_author(name=owner.name, icon_url=owner.display_avatar.url)
        await i.followup.send(embed=embed, view=view)
        view.message = await i.original_response()

    @app_commands.command(
        name=locale_str("about"),
        description=locale_str("About the bot", key="about_command_description"),
    )
    async def about_command(self, i: Interaction) -> None:
        await i.response.defer()

        settings = await UserSettings.get(user_id=i.user.id)
        locale = settings.locale or i.locale
        assert self.bot.user is not None
        embed = DefaultEmbed(
            locale=locale,
            translator=self.bot.translator,
            title=f"{self.bot.user.name} {self.bot.version}",
            description=LocaleStr(key="about_embed.description"),
        )

        # latest changes
        embed.add_field(
            name=LocaleStr(key="about_command.latest_changes"),
            value=self.get_last_commits(),
            inline=False,
        )

        # developer
        owner = await i.client.fetch_user(i.client.owner_id)
        assert owner is not None
        embed.add_field(
            name=LocaleStr(key="about_command.developer"),
            value=get_discord_user_md_link(owner),
            inline=False,
        )

        # translators
        guild = self.bot.get_guild(1000727526194298910) or await i.client.fetch_guild(
            1000727526194298910
        )
        if not guild.chunked:
            await guild.chunk()
        translator_role = guild.get_role(1010181916642787503)
        assert translator_role is not None
        translators = [
            get_discord_user_md_link(translator) for translator in translator_role.members
        ]
        embed.add_field(
            name=LocaleStr(key="about_command.translators"),
            value=" ".join(translators),
            inline=False,
        )

        # guild count
        embed.add_field(
            name=LocaleStr(key="about_command.guild_count"),
            value=str(len(i.client.guilds)),
        )

        # ram usage
        memory_usage = self.process.memory_info().rss / 1024**2
        embed.add_field(
            name=LocaleStr(key="about_command.ram_usage"),
            value=f"{memory_usage:.2f} MB",
        )

        # uptime
        uptime = discord.utils.format_dt(i.client.uptime, "R")
        embed.add_field(
            name=LocaleStr(key="about_command.uptime"),
            value=uptime,
        )

        # url buttons
        view = View(locale=locale, translator=self.bot.translator, author=None)
        view.add_item(Button(label="GitHub", url=self.repo_url, emoji=GITHUB_WHITE_ICON, row=0))
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.discord_server"),
                url="https://dsc.gg/hoyo-buddy",
                emoji=DISCORD_WHITE_ICON,
                row=0,
            )
        )
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.website"),
                url="https://seria.is-a.dev/hoyo-buddy",
                row=1,
            )
        )
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.invite"),
                url="https://dub.sh/hb-invite"
                if self.bot.env == "prod"
                else "https://dub.sh/hb-beta-invite",
                row=1,
            )
        )
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.support"),
                url="https://buymeacoffee.com/seria",
                row=1,
            )
        )
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.contribute"),
                url="https://github.com/seriaati/hoyo-buddy/blob/main/CONTRIBUTING.md",
                row=1,
            )
        )

        # brand image
        image_ = discord.File(
            SettingsUI.get_brand_img_filename("DARK" if settings.dark_mode else "LIGHT", locale),
            filename="brand.png",
        )
        embed.set_image(url="attachment://brand.png")

        view.message = await i.edit_original_response(embed=embed, attachments=[image_], view=view)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Others(bot))
