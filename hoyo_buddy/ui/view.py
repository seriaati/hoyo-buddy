import logging
from typing import Any, Optional, Self, Union

import discord

from ..bot import HoyoBuddy
from ..bot.command_tree import get_error_embed
from ..bot.translator import Translator
from .button import Button
from .embeds import ErrorEmbed
from .select import Select

log = logging.getLogger(__name__)


class View(discord.ui.View):
    def __init__(
        self,
        *,
        author: Union[discord.Member, discord.User],
        locale: discord.Locale,
        translator: Translator,
        timeout: Optional[float] = 180
    ):
        super().__init__(timeout=timeout)
        self.author = author
        self.locale = locale
        self.translator = translator
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
    ) -> None:  # skipcq: PYL-W0221
        log.exception(error)
        embed = await get_error_embed(i, error)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def interaction_check(
        self, i: discord.Interaction[HoyoBuddy]
    ) -> bool:  # skipcq: PYL-W0221
        if i.user.id != self.author.id:
            embed = ErrorEmbed(
                self.locale,
                self.translator,
                title="Interaction failed",
                description="This view is not initiated by you, therefore you cannot use it.",
            )
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

    def add_item(
        self, item: Union[Button, Select], *, translate: bool = True, **kwargs
    ) -> Self:
        if translate:
            item.translate(self.locale, self.translator, **kwargs)
        return super().add_item(item)

    @staticmethod
    async def absolute_send(i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)

    @staticmethod
    async def absolute_edit(i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await i.edit_original_response(**kwargs)

    @staticmethod
    def get_embed(i: discord.Interaction) -> Optional[discord.Embed]:
        if i.message and i.message.embeds:
            return i.message.embeds[0]
        return None
