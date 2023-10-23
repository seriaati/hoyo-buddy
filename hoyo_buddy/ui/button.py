from typing import Optional, Union

import discord
from discord.emoji import Emoji
from discord.enums import ButtonStyle
from discord.partial_emoji import PartialEmoji

from ..bot import HoyoBuddy, emojis
from ..bot.translator import Translator
from ..db.models import User
from .view import View


class Button(discord.ui.Button):
    def __init__(
        self,
        *,
        style: ButtonStyle = ButtonStyle.secondary,
        label: Optional[str] = None,
        disabled: bool = False,
        custom_id: Optional[str] = None,
        url: Optional[str] = None,
        emoji: Optional[Union[Emoji, PartialEmoji, str]] = None,
        row: Optional[int] = None
    ):
        super().__init__(
            style=style,
            label=label,
            disabled=disabled,
            custom_id=custom_id,
            url=url,
            emoji=emoji,
            row=row,
        )

    async def translate(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        translate_label: bool = True,
        **kwargs
    ):
        if self.label and translate_label:
            self.label = await translator.translate(self.label, locale, **kwargs)

    async def set_loading_state(self, i: discord.Interaction[HoyoBuddy]) -> None:
        self.disabled = True
        self.emoji = emojis.LOADING
        self.label = "Loading..."
        user = await User.get(id=i.user.id).prefetch_related("settings")
        await self.translate(user.settings.locale or i.locale, i.client.translator)
        self.view: View
        await self.view.absolute_edit(i, view=self.view)
