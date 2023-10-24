from typing import Any, Optional, Union

import discord

from ..bot import HoyoBuddy
from ..bot.command_tree import get_error_embed
from ..bot.translator import Translator
from ..db.models import User
from .button import Button
from .embeds import ErrorEmbed
from .select import Select

log = logging.getLogger(__name__)


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

    async def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        translate_label: bool = True,
        translate_placeholder: bool = True,
        translate_option_labels: bool = True,
        translate_option_descriptions: bool = True,
        **kwargs
    ) -> None:
        for child in self.children:
            if isinstance(child, (Button, Select)):
                await child.translate(
                    locale,
                    translator,
                    translate_label=translate_label,
                    translate_placeholder=translate_placeholder,
                    translate_option_labels=translate_option_labels,
                    translate_option_descriptions=translate_option_descriptions,
                    **kwargs
                )

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
        log.exception(error)
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

    def add_item(
        self, item: Union[Button, Select], *, translate: bool = True, **kwargs
    ) -> Self:
        if translate:
            item.translate(self.locale, self.translator, **kwargs)
        return super().add_item(item)

    async def absolute_send(self, i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.send_message(**kwargs)
        except discord.InteractionResponded:
            await i.followup.send(**kwargs)

    async def absolute_edit(self, i: discord.Interaction, **kwargs) -> None:
        try:
            await i.response.edit_message(**kwargs)
        except discord.InteractionResponded:
            await i.edit_original_response(**kwargs)

    def get_embed(self, i: discord.Interaction) -> Optional[discord.Embed]:
        if i.message and i.message.embeds:
            return i.message.embeds[0]
        return None
