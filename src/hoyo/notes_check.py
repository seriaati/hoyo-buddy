import asyncio
import datetime
import logging
from typing import TYPE_CHECKING, ClassVar

from discord import Locale
from genshin.models import Notes, StarRailNote

from ..bot.error_handler import get_error_embed
from ..bot.translator import LocaleStr
from ..db.models import NotesNotify
from ..draw.main_funcs import draw_gi_notes_card, draw_hsr_notes_card
from ..embeds import DefaultEmbed, ErrorEmbed
from ..enums import Game, NotesNotifyType
from ..icons import RESIN_ICON, RTBP_ICON, TBP_ICON
from ..models import DrawInput
from ..ui.hoyo.notes.view import NotesView
from ..utils import get_now

if TYPE_CHECKING:
    from ..bot.bot import HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class NotesChecker:
    _bot: ClassVar["HoyoBuddy"]

    @classmethod
    def _calc_est_time(cls, game: Game, threshold: int, current: int) -> datetime.datetime:
        """Calculate the estimated time for resin/trailblaze power to reach the threshold."""
        if game is Game.GENSHIN:
            return get_now() + datetime.timedelta(minutes=(threshold - current) * 8)
        elif game is Game.STARRAIL:
            return get_now() + datetime.timedelta(minutes=(threshold - current) * 6)
        else:
            raise NotImplementedError

    @classmethod
    async def _get_locale(cls, notify: NotesNotify) -> Locale:
        await notify.account.fetch_related("user")
        await notify.account.user.fetch_related("settings")
        return notify.account.user.settings.locale or Locale.american_english

    @classmethod
    def _get_notify_error_embed(cls, err: Exception, locale: Locale) -> ErrorEmbed:
        embed, recognized = get_error_embed(err, locale, cls._bot.translator)
        if not recognized:
            LOGGER_.exception("Unrecognized error", exc_info=err)
        return embed

    @classmethod
    def _get_notify_embed(cls, notify: NotesNotify, locale: "Locale") -> DefaultEmbed:
        translator = cls._bot.translator

        match notify.type:
            case NotesNotifyType.RESIN:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_author(
                    name=LocaleStr("Resin Reminder", key="resin_reminder_button.label"),
                    icon_url=RESIN_ICON,
                )
            case NotesNotifyType.TB_POWER:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_author(
                    name=LocaleStr("Trailblaze Power Reminder", key="tbp_reminder_button.label"),
                    icon_url=TBP_ICON,
                )
            case NotesNotifyType.RESERVED_TB_POWER:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_author(
                    name=LocaleStr(
                        "Reserved Trailblaze Power Reminder",
                        key="rtbp_reminder_button.label",
                    ),
                    icon_url=RTBP_ICON,
                )
            case NotesNotifyType.GI_EXPED | NotesNotifyType.HSR_EXPED:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    description=LocaleStr(
                        "One (or more) expedetions are finished",
                        key="exped.embed.description",
                    ),
                )
                embed.set_author(name=LocaleStr("Expedition Reminder", key="exped_button.label"))
            case NotesNotifyType.PT:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    description=LocaleStr(
                        "Parametric Transformer is ready",
                        key="pt.embed.description",
                    ),
                )
                embed.set_author(
                    name=LocaleStr("Parametric Transformer Reminder", key="pt_button.label")
                )
            case NotesNotifyType.REALM_CURRENCY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_author(
                    name=LocaleStr("Realm Currency Reminder", key="realm_curr_button.label")
                )
            case _:
                raise NotImplementedError

        embed.title = str(notify.account)
        embed.set_footer(
            text=LocaleStr(
                "Disable this notification or change its settings by clicking the button below",
                key="notif.embed.footer",
            )
        )
        embed.set_image(url="attachment://notes.webp")
        return embed

    @classmethod
    async def _notify_user(cls, notify: NotesNotify, notes: StarRailNote | Notes) -> None:
        locale = await cls._get_locale(notify)
        embed = cls._get_notify_embed(notify, locale)
        draw_input = DrawInput(
            dark_mode=notify.account.user.settings.dark_mode,
            locale=locale,
            session=cls._bot.session,
            filename="notes.webp",
        )
        file_ = (
            await draw_gi_notes_card(draw_input, notes, cls._bot.translator)
            if isinstance(notes, Notes)
            else await draw_hsr_notes_card(draw_input, notes, cls._bot.translator)
        )

        view = NotesView(notify.account, author=None, locale=locale, translator=cls._bot.translator)
        message = await cls._bot.dm_user(notify.account.user.id, embed=embed, file=file_, view=view)
        view.message = message

        notify.enabled = message is not None
        notify.last_notif_time = get_now()
        notify.current_notif_count += 1 if message is not None else 0
        await notify.save()

    @classmethod
    async def _process_resin_notify(cls, notify: NotesNotify) -> None:
        """Process resin notification."""
        notes = await notify.account.client.get_genshin_notes()
        current = notes.current_resin
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            est_time = cls._calc_est_time(Game.GENSHIN, threshold, current)
            notify.est_time = est_time
            notify.current_notif_count = 0
            return await notify.save()

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_realm_currency_notify(cls, notify: NotesNotify) -> None:
        """Process realm currency notification."""
        notes = await notify.account.client.get_genshin_notes()
        current = notes.current_realm_currency
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            notify.current_notif_count = 0
            return await notify.save()

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_tbp_notify(cls, notify: NotesNotify) -> None:
        """Process trailblaze power notification."""
        notes = await notify.account.client.get_starrail_notes()
        current = notes.current_stamina
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            est_time = cls._calc_est_time(Game.STARRAIL, threshold, current)
            notify.est_time = est_time
            notify.current_notif_count = 0
            return await notify.save()

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_rtbp_notify(cls, notify: NotesNotify) -> None:
        """Process reserved trailblaze power notification."""
        notes = await notify.account.client.get_starrail_notes()
        current = notes.current_reserve_stamina
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            notify.current_notif_count = 0
            return await notify.save()

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_expedition_notify(cls, notify: NotesNotify) -> None:
        """Process expedition notification."""
        if notify.type is NotesNotifyType.GI_EXPED:
            notes = await notify.account.client.get_genshin_notes()
        elif notify.type is NotesNotifyType.HSR_EXPED:
            notes = await notify.account.client.get_starrail_notes()
        else:
            raise NotImplementedError

        if any(not exped.finished for exped in notes.expeditions):
            notify.current_notif_count = 0
            await notify.save()

        if (
            any(exped.finished for exped in notes.expeditions)
            and notify.current_notif_count < notify.max_notif_count
        ):
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_pt(cls, notify: NotesNotify) -> None:
        notes = await notify.account.client.get_genshin_notes()

        remaining_time = notes.remaining_transformer_recovery_time
        if remaining_time is None:
            return

        if remaining_time.seconds >= 0:
            notify.current_notif_count = 0
            return await notify.save()

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_notify(cls, notify: NotesNotify) -> None:
        """Proces notification."""
        match notify.type:
            case NotesNotifyType.RESIN:
                await cls._process_resin_notify(notify)
            case NotesNotifyType.TB_POWER:
                await cls._process_tbp_notify(notify)
            case NotesNotifyType.RESERVED_TB_POWER:
                await cls._process_rtbp_notify(notify)
            case NotesNotifyType.GI_EXPED | NotesNotifyType.HSR_EXPED:
                await cls._process_expedition_notify(notify)
            case NotesNotifyType.PT:
                await cls._process_pt(notify)
            case NotesNotifyType.REALM_CURRENCY:
                await cls._process_realm_currency_notify(notify)
            case _:
                raise NotImplementedError

    @classmethod
    async def execute(cls, bot: "HoyoBuddy") -> None:
        cls._bot = bot
        notifies = await NotesNotify.all().prefetch_related("account")

        for notify in notifies:
            if not notify.enabled:
                continue

            if notify.est_time is not None and get_now() < notify.est_time:
                continue

            if (
                notify.last_check_time is not None
                and get_now() - notify.last_check_time
                < datetime.timedelta(minutes=notify.check_interval)
            ):
                continue

            if (
                notify.last_notif_time is not None
                and get_now() - notify.last_notif_time
                < datetime.timedelta(minutes=notify.notify_interval)
            ):
                continue

            try:
                await cls._process_notify(notify)
            except Exception as e:
                content = LocaleStr(
                    "An error occurred while processing your reminder",
                    key="process_notify_error.content",
                )
                translated_content = cls._bot.translator.translate(
                    content, await cls._get_locale(notify)
                )
                embed = cls._get_notify_error_embed(e, await cls._get_locale(notify))
                await cls._bot.dm_user(
                    notify.account.user.id, embed=embed, content=translated_content
                )
            finally:
                notify.last_check_time = get_now()
                await notify.save()
                await asyncio.sleep(1.2)
