from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.app_commands import locale_str
from discord.ext import commands, tasks
from loguru import logger

from hoyo_buddy.commands.configs import COMMANDS
from hoyo_buddy.config import CONFIG
from hoyo_buddy.constants import IMAGE_EXTENSIONS, INSTALL_URL, get_docs_url
from hoyo_buddy.db import Settings as UserSettings
from hoyo_buddy.db import get_dyk
from hoyo_buddy.db.utils import get_locale
from hoyo_buddy.exceptions import NotAnImageError

from ..embeds import DefaultEmbed
from ..emojis import DISCORD_WHITE_ICON, GITHUB_WHITE_ICON
from ..l10n import LocaleStr
from ..types import Interaction
from ..ui import Button, View
from ..ui.settings import SettingsUI
from ..utils import ephemeral, get_discord_user_md_link, upload_image

if TYPE_CHECKING:
    from ..bot import HoyoBuddy


class Others(commands.Cog):
    def __init__(self, bot: HoyoBuddy) -> None:
        self.bot = bot
        self.repo_url = "https://github.com/seriaati/hoyo-buddy"

    async def cog_load(self) -> None:
        if CONFIG.is_dev:
            return
        self.update_stat_vcs.start()

    def cog_unload(self) -> None:
        if CONFIG.is_dev:
            return
        self.update_stat_vcs.cancel()

    @tasks.loop(hours=2)
    async def update_stat_vcs(self) -> None:
        guild = await self.bot.get_or_fetch_guild()
        if guild is None:
            logger.warning("Skipping update_stat_vcs: guild not found")
            return

        category_id = 1309451146556997683
        category = discord.utils.get(guild.categories, id=category_id)
        if category is None:
            return

        vc_ids = [vc.id for vc in category.voice_channels]
        vc_rotator = itertools.cycle(vc_ids)

        # Server installs
        server_count = len(self.bot.guilds)
        vc = guild.get_channel(next(vc_rotator))
        if vc is not None:
            await vc.edit(name=f"{server_count} Servers")

        # User installs
        app_info = await self.bot.application_info()
        user_count = app_info.approximate_user_install_count
        vc = guild.get_channel(next(vc_rotator))
        if vc is not None:
            await vc.edit(name=f"{user_count} User Installs")

    @update_stat_vcs.before_loop
    async def before_update_stat_vcs(self) -> None:
        await self.bot.wait_until_ready()

    @app_commands.command(name=locale_str("about"), description=COMMANDS["about"].description)
    async def about_command(self, i: Interaction) -> None:
        await i.response.defer(ephemeral=ephemeral(i))

        guild = await self.bot.get_or_fetch_guild()
        if guild is None:
            msg = "This command can only be used in a server."
            raise ValueError(msg)

        if not guild.chunked:
            await guild.chunk()

        settings = await UserSettings.get(user_id=i.user.id)
        locale = await get_locale(i)
        embed = DefaultEmbed(
            locale=locale,
            title=f"{self.bot.user.name if self.bot.user is not None else 'Hoyo Buddy'} {self.bot.version}",
            description=LocaleStr(key="about_embed.description"),
        )

        # developer
        seria_id = 410036441129943050
        owner = i.client.get_user(seria_id) or await i.client.fetch_user(seria_id)
        embed.add_field(
            name=LocaleStr(key="about_command.developer"),
            value=get_discord_user_md_link(owner),
            inline=False,
        )

        # designer
        designer_role = guild.get_role(1266651937411960882)
        if designer_role is not None:
            designers = [get_discord_user_md_link(designer) for designer in designer_role.members]
            embed.add_field(
                name=LocaleStr(key="about_command.designers"),
                value=" ".join(designers),
                inline=False,
            )

        # translators
        translator_role = guild.get_role(1010181916642787503)
        if translator_role is not None:
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
            name=LocaleStr(key="about_command.guild_count"), value=str(len(i.client.guilds))
        )

        # ram usage
        embed.add_field(
            name=LocaleStr(key="about_command.ram_usage"), value=f"{self.bot.ram_usage:.2f} MB"
        )

        # uptime
        uptime = discord.utils.format_dt(i.client.uptime, "R")
        embed.add_field(name=LocaleStr(key="about_command.uptime"), value=uptime)

        # url buttons
        view = View(locale=locale, author=None)
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
            Button(label=LocaleStr(key="about_command.website"), url="https://hb.seria.moe", row=1)
        )
        view.add_item(
            Button(
                label=LocaleStr(key="about_command.support"),
                url="https://link.seria.moe/donate",
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
        view.add_item(
            Button(
                label=LocaleStr(key="changelog_embed_title"),
                url=get_docs_url("changelog", locale=locale),
                row=1,
            )
        )
        view.add_item(
            Button(
                label=LocaleStr(key="status_page_btn_label"),
                url="https://status.seria.moe/?category=Hoyo%20Buddy",
                row=2,
            )
        )
        view.add_item(
            Button(
                label=LocaleStr(key="docs_page_btn_label"),
                url=get_docs_url("intro", locale=locale),
                row=2,
            )
        )
        view.add_item(Button(label=LocaleStr(key="invite_page_btn_label"), url=INSTALL_URL, row=2))

        # brand image
        image_ = discord.File(
            SettingsUI.get_brand_img_filename("DARK" if settings.dark_mode else "LIGHT", locale),
            filename="brand.webp",
        )
        embed.set_image(url="attachment://brand.webp")

        view.message = await i.edit_original_response(
            embed=embed, attachments=[image_], view=view, content=await get_dyk(i)
        )

    @app_commands.command(
        name=app_commands.locale_str("upload"), description=COMMANDS["upload"].description
    )
    @app_commands.rename(image=app_commands.locale_str("image", key="upload_cmd_image_param_name"))
    @app_commands.describe(
        image=app_commands.locale_str("Image to upload", key="upload_cmd_image_param_desc")
    )
    async def upload_command(self, i: Interaction, image: discord.Attachment) -> None:
        if not any(image.filename.endswith(ext) for ext in IMAGE_EXTENSIONS):
            raise NotAnImageError

        await i.response.defer(ephemeral=ephemeral(i))
        url = await upload_image(i.client.session, image_url=image.url)
        await i.followup.send(f"<{url}>", ephemeral=True)


async def setup(bot: HoyoBuddy) -> None:
    await bot.add_cog(Others(bot))
