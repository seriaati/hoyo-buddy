from typing import Any, Optional, Union

import discord

from ..bot import HoyoBuddy
from ..bot.command_tree import get_error_embed
from ..db.models import User
from ..exceptions import HoyoBuddyError
from .embeds import ErrorEmbed


class View(discord.ui.View):
    def __init__(
        self,
        author: Union[discord.Member, discord.User],
        *,
        timeout: Optional[float] = 180
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.message: Optional[discord.Message] = None

    async def on_timeout(self) -> None:
        if self.message:
            self.disable_items()
            await self.message.edit(view=self)

    async def on_error(
        self,
        i: discord.Interaction[HoyoBuddy],
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        embed = await get_error_embed(i, error)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(self, i: discord.Interaction[HoyoBuddy]) -> bool:
        if i.user.id != self.author.id:
            embed = ErrorEmbed(
                title="Interaction failed",
                description="This view is not initiated by you, therefore you cannot use it.",
            )
            user = await User.get(id=i.user.id).prefetch_related("settings")
            await embed.translate(user.settings.locale or i.locale, i.client.translator)
            await i.response.send_message(embed, ephemeral=True)
            return False
        return True

    def disable_items(self) -> None:
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = True

    def enable_items(self) -> None:
        for child in self.children:
            if isinstance(child, (discord.ui.Button, discord.ui.Select)):
                child.disabled = False

    async def absolute_send(self, i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)
