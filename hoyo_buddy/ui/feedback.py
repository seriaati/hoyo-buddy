from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, TextChannel, TextStyle, User
from loguru import logger

from ..embeds import DefaultEmbed
from ..l10n import LocaleStr
from .components import Button, Modal, TextInput, View

if TYPE_CHECKING:
    from hoyo_buddy.l10n import Translator

    from ..types import Interaction


class FeedbackView(View):
    def __init__(
        self, *, author: User | Member | None, locale: Locale, translator: Translator
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.add_item(FeedbackButton())


class FeedbackModal(Modal):
    feedback = TextInput(
        label=LocaleStr(key="feedback_modal.feedback.label"), style=TextStyle.paragraph
    )


class FeedbackButton(Button[FeedbackView]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr(key="feedback_button.label"), style=ButtonStyle.blurple)

    async def callback(self, i: Interaction) -> None:
        modal = FeedbackModal(title=LocaleStr(key="feedback_button.label"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        incomplete = modal.incomplete
        if incomplete:
            return

        feedback = modal.feedback.value
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title="New Feedback Received",
            description=feedback,
        )
        embed.set_author(name=i.user.name, icon_url=i.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {i.user.id}")

        feedback_channel = await i.client.fetch_channel(1273772399925399633)
        if isinstance(feedback_channel, TextChannel):
            await feedback_channel.send(embed=embed)
        else:
            logger.error("Failed to fetch feedback channel.")

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr(key="feedback_button.feedback_sent.title"),
            description=LocaleStr(key="feedback_button.feedback_sent.description"),
        )
        await i.edit_original_response(embed=embed, view=None)
