from typing import Any, Optional

import discord
from discord.utils import MISSING

from ..bot import HoyoBuddy
from ..bot.command_tree import get_error_embed
from ..bot.translator import Translator


class Modal(discord.ui.Modal):
    def __init__(
        self, *, title: str, timeout: Optional[float] = None, custom_id: str = MISSING
    ) -> None:
        super().__init__(title=title, timeout=timeout, custom_id=custom_id)

    async def on_error(
        self,
        i: discord.Interaction[HoyoBuddy],
        error: Exception,
        _: discord.ui.Item[Any],
    ) -> None:
        embed = await get_error_embed(i, error)
        await self.absolute_send(i, embed=embed, ephemeral=True)

    async def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        translate_title: bool = True,
        translate_input_labels: bool = True,
        translate_input_placeholders: bool = True,
        **kwargs
    ) -> None:
        if translate_title:
            self.title = translator.translate(self.title, locale, **kwargs)
        for item in self.children:
            if isinstance(item, discord.ui.TextInput):
                if translate_input_labels:
                    item.label = translator.translate(item.label, locale, **kwargs)
                if item.placeholder and translate_input_placeholders:
                    item.placeholder = translator.translate(
                        item.placeholder, locale, **kwargs
                    )

    async def absolute_send(self, i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)
