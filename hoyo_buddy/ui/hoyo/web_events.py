from __future__ import annotations

from typing import TYPE_CHECKING

from hoyo_buddy import ui
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.l10n import LocaleStr

if TYPE_CHECKING:
    import genshin

    from hoyo_buddy.db.models import HoyoAccount
    from hoyo_buddy.enums import Locale
    from hoyo_buddy.types import Interaction, User


class WebEventsView(ui.View):
    def __init__(self, account: HoyoAccount, *, author: User, locale: Locale) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account

    @staticmethod
    def get_event_embed(event: genshin.models.WebEvent, locale: Locale) -> DefaultEmbed:
        embed = DefaultEmbed(locale, title=event.name, description=event.description, url=event.url)
        embed.set_image(url=event.banner)
        embed.set_author(
            name=f"{event.start_time.strftime('%Y/%m/%d')} - {event.end_time.strftime('%Y/%m/%d')}"
        )
        return embed

    async def fetch_events(self) -> list[genshin.models.WebEvent]:
        client = self.account.client
        client.set_lang(self.locale)
        return await client.get_web_events()

    async def start(self, i: Interaction) -> None:
        await self.account.fetch_related("notif_settings")
        events = await self.fetch_events()
        if not events:
            msg = "No events found."
            raise ValueError(msg)

        self.add_item(EventSelector(events=events))
        self.add_item(NotifyToggle(current_toggle=self.account.notif_settings.web_events))
        await i.response.send_message(embed=self.get_event_embed(events[0], self.locale), view=self)

        self.message = await i.original_response()


class EventSelector(ui.Select[WebEventsView]):
    def __init__(self, events: list[genshin.models.WebEvent]) -> None:
        options = [ui.SelectOption(label=event.name, value=str(event.id)) for event in events]
        super().__init__(options=options)
        self.events = events

    def get_event(self, value: str) -> genshin.models.WebEvent:
        event = next((event for event in self.events if str(event.id) == value), None)
        if event is None:
            msg = f"Cannot get event with id {value}"
            raise ValueError(msg)
        return event

    async def callback(self, i: Interaction) -> None:
        embed = self.view.get_event_embed(self.get_event(self.values[0]), self.view.locale)
        await i.response.edit_message(embed=embed)


class NotifyToggle(ui.ToggleButton[WebEventsView]):
    def __init__(self, *, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="web_events_notify_toggle_label"))

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.notif_settings.web_events = self.current_toggle
        await self.view.account.notif_settings.save(update_fields=("web_events",))
