import asyncio
import datetime
import logging
from typing import TYPE_CHECKING, ClassVar

from discord import Locale
from genshin.models import Notes, StarRailNote

from ...bot.error_handler import get_error_embed
from ...bot.translator import LocaleStr
from ...db.models import NotesNotify
from ...draw.main_funcs import draw_gi_notes_card, draw_hsr_notes_card
from ...embeds import DefaultEmbed, ErrorEmbed
from ...enums import Game, NotesNotifyType
from ...icons import COMMISSION_ICON, PT_ICON, REALM_CURRENCY_ICON, RESIN_ICON, RTBP_ICON, TBP_ICON
from ...models import DrawInput
from ...ui.hoyo.notes.view import NotesView
from ...utils import get_now

if TYPE_CHECKING:
    from ...bot.bot import HoyoBuddy

LOGGER_ = logging.getLogger(__name__)


class NotesChecker:
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _bot: ClassVar["HoyoBuddy"]
    _notes_cache: ClassVar[dict[Game, dict[int, Notes | StarRailNote]]] = {}

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
        return notify.account.user.settings.locale or Locale.american_english

    @classmethod
    def _get_notify_error_embed(cls, err: Exception, locale: Locale) -> ErrorEmbed:
        embed, recognized = get_error_embed(err, locale, cls._bot.translator)
        if not recognized:
            cls._bot.capture_exception(err)
        return embed

    @classmethod
    def _get_notify_embed(cls, notify: NotesNotify, locale: "Locale") -> DefaultEmbed:
        translator = cls._bot.translator

        match notify.type:
            case NotesNotifyType.RESIN:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Resin Reminder", key="resin_reminder_button.label"),
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_thumbnail(url=RESIN_ICON)
            case NotesNotifyType.TB_POWER:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Trailblaze Power Reminder", key="tbp_reminder_button.label"),
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_thumbnail(url=TBP_ICON)
            case NotesNotifyType.RESERVED_TB_POWER:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(
                        "Reserved Trailblaze Power Reminder",
                        key="rtbp_reminder_button.label",
                    ),
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_thumbnail(url=RTBP_ICON)
            case NotesNotifyType.GI_EXPED | NotesNotifyType.HSR_EXPED:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Expedition Reminder", key="exped_button.label"),
                    description=LocaleStr(
                        "One (or more) expedetions are finished",
                        key="exped.embed.description",
                    ),
                )
            case NotesNotifyType.PT:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Parametric Transformer Reminder", key="pt_button.label"),
                    description=LocaleStr(
                        "Parametric Transformer is ready",
                        key="pt.embed.description",
                    ),
                )
                embed.set_thumbnail(url=PT_ICON)
            case NotesNotifyType.REALM_CURRENCY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Realm Currency Reminder", key="realm_curr_button.label"),
                    description=LocaleStr(
                        "Threshold ({threshold}) is reached",
                        key="threshold.embed.description",
                        threshold=notify.threshold,
                    ),
                )
                embed.set_thumbnail(url=REALM_CURRENCY_ICON)
            case NotesNotifyType.GI_DAILY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Daily Commision Reminder", key="daily_button.label"),
                    description=LocaleStr(
                        "Daily commisions or adventure encounters are not completed yet",
                        key="gi_daily.embed.description",
                    ),
                )
                embed.set_thumbnail(url=COMMISSION_ICON)
            case NotesNotifyType.HSR_DAILY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Daily Training Reminder", key="daily_training_button.label"),
                    description=LocaleStr(
                        "Daily trainings are not completed yet",
                        key="hsr_daily.embed.description",
                    ),
                )
            case NotesNotifyType.RESIN_DISCOUNT | NotesNotifyType.ECHO_OF_WAR:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr("Weekly Boss Discount Reminder", key="week_boss_button.label"),
                    description=LocaleStr(
                        "Weekly boss discounts are not used up yet",
                        key="resin_discount.embed.description",
                    ),
                )
            case _:
                raise NotImplementedError

        embed.add_acc_info(notify.account)
        embed.set_footer(
            text=LocaleStr(
                "Click the button below to change notification settings.\nIf it is expired, use the /notes command.",
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

        view = NotesView(
            notify.account,
            notify.account.user.settings,
            author=None,
            locale=locale,
            translator=cls._bot.translator,
        )
        message = await cls._bot.dm_user(notify.account.user.id, embed=embed, file=file_, view=view)
        view.message = message

        notify.enabled = message is not None
        notify.last_notif_time = get_now()
        notify.current_notif_count += 1 if message is not None else 0
        await notify.save(update_fields=("enabled", "last_notif_time", "current_notif_count"))

    @classmethod
    async def _process_resin_notify(cls, notify: NotesNotify, notes: Notes) -> None:
        """Process resin notification."""
        current = notes.current_resin
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            est_time = cls._calc_est_time(Game.GENSHIN, threshold, current)
            notify.est_time = est_time
            notify.current_notif_count = 0
            return await notify.save(update_fields=("est_time", "current_notif_count"))

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_realm_currency_notify(cls, notify: NotesNotify, notes: Notes) -> None:
        """Process realm currency notification."""
        current = notes.current_realm_currency
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            notify.current_notif_count = 0
            return await notify.save(update_fields=("current_notif_count",))

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_tbp_notify(cls, notify: NotesNotify, notes: StarRailNote) -> None:
        """Process trailblaze power notification."""
        current = notes.current_stamina
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            est_time = cls._calc_est_time(Game.STARRAIL, threshold, current)
            notify.est_time = est_time
            notify.current_notif_count = 0
            return await notify.save(update_fields=("est_time", "current_notif_count"))

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_rtbp_notify(cls, notify: NotesNotify, notes: StarRailNote) -> None:
        """Process reserved trailblaze power notification."""
        current = notes.current_reserve_stamina
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            notify.current_notif_count = 0
            return await notify.save(update_fields=("current_notif_count",))

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_expedition_notify(
        cls, notify: NotesNotify, notes: Notes | StarRailNote
    ) -> None:
        """Process expedition notification."""
        if any(not exped.finished for exped in notes.expeditions):
            notify.current_notif_count = 0
            await notify.save(update_fields=("current_notif_count",))

        if (
            any(exped.finished for exped in notes.expeditions)
            and notify.current_notif_count < notify.max_notif_count
        ):
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_pt_notify(cls, notify: NotesNotify, notes: Notes) -> None:
        remaining_time = notes.remaining_transformer_recovery_time
        if remaining_time is None:
            return

        if remaining_time.seconds >= 0:
            notify.current_notif_count = 0
            return await notify.save(update_fields=("current_notif_count",))

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_daily_notify(cls, notify: NotesNotify, notes: Notes | StarRailNote) -> None:
        if notify.last_check_time is not None and get_now().day != notify.last_check_time.day:
            notify.current_notif_count = 0
            await notify.save(update_fields=("current_notif_count",))

        if (
            isinstance(notes, Notes)
            and notes.completed_commissions + notes.daily_task.completed_tasks >= 4
        ):
            return
        if isinstance(notes, StarRailNote) and notes.current_train_score >= notes.max_train_score:
            return

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_week_boos_discount_notify(
        cls, notify: NotesNotify, notes: Notes | StarRailNote
    ) -> None:
        if notify.last_check_time is not None and get_now().day != notify.last_check_time.day:
            notify.current_notif_count = 0
            await notify.save(update_fields=("current_notif_count",))

        if isinstance(notes, Notes) and notes.remaining_resin_discounts == 0:
            return
        if isinstance(notes, StarRailNote) and notes.remaining_weekly_discounts == 0:
            return

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)

    @classmethod
    async def _process_notify(cls, notify: NotesNotify, notes: Notes | StarRailNote) -> None:
        """Proces notification."""
        match notify.type:
            case NotesNotifyType.RESIN:
                assert isinstance(notes, Notes)
                await cls._process_resin_notify(notify, notes)
            case NotesNotifyType.TB_POWER:
                assert isinstance(notes, StarRailNote)
                await cls._process_tbp_notify(notify, notes)
            case NotesNotifyType.RESERVED_TB_POWER:
                assert isinstance(notes, StarRailNote)
                await cls._process_rtbp_notify(notify, notes)
            case NotesNotifyType.GI_EXPED | NotesNotifyType.HSR_EXPED:
                await cls._process_expedition_notify(notify, notes)
            case NotesNotifyType.PT:
                assert isinstance(notes, Notes)
                await cls._process_pt_notify(notify, notes)
            case NotesNotifyType.REALM_CURRENCY:
                assert isinstance(notes, Notes)
                await cls._process_realm_currency_notify(notify, notes)
            case NotesNotifyType.GI_DAILY | NotesNotifyType.HSR_DAILY:
                await cls._process_daily_notify(notify, notes)
            case NotesNotifyType.RESIN_DISCOUNT | NotesNotifyType.ECHO_OF_WAR:
                await cls._process_week_boos_discount_notify(notify, notes)
            case _:
                raise NotImplementedError

    @classmethod
    async def _handle_notify_error(cls, notify: NotesNotify, e: Exception) -> None:
        content = LocaleStr(
            (
                "An error occurred while processing your reminder.\n"
                "You can disable the reminders by using the </notes> command.\n"
                "If this keeps happening, consider reporting this to the developer with the </feedback> command."
            ),
            key="process_notify_error.content",
        )
        translated_content = cls._bot.translator.translate(content, await cls._get_locale(notify))
        embed = cls._get_notify_error_embed(e, await cls._get_locale(notify))
        await cls._bot.dm_user(notify.account.user.id, embed=embed, content=translated_content)

    @classmethod
    def _determine_skip(cls, notify: NotesNotify) -> bool:  # noqa: PLR0911
        """Determine if the notification should be skipped."""
        if notify.est_time is not None and get_now() < notify.est_time:
            return True

        if notify.notify_weekday is not None and notify.notify_weekday != get_now().weekday() + 1:
            return True

        if (
            notify.last_check_time is not None
            and get_now() - notify.last_check_time
            < datetime.timedelta(minutes=notify.check_interval)
        ):
            return True

        if (
            notify.last_notif_time is not None
            and get_now() - notify.last_notif_time
            < datetime.timedelta(minutes=notify.notify_interval)
        ):
            return True

        return bool(
            notify.notify_time is not None and get_now() < notify.account.server_reset_datetime
        )

    @classmethod
    async def _get_notes(cls, notify: NotesNotify) -> Notes | StarRailNote:
        if notify.account.game is Game.GENSHIN:
            notes = await notify.account.client.get_genshin_notes()
        elif notify.account.game is Game.STARRAIL:
            notes = await notify.account.client.get_starrail_notes()
        else:
            raise NotImplementedError
        return notes

    @classmethod
    async def execute(cls, bot: "HoyoBuddy") -> None:  # noqa: PLR0912
        if cls._lock.locked():
            return

        async with cls._lock:
            cls._bot = bot
            cls._notes_cache = {Game.GENSHIN: {}, Game.STARRAIL: {}}

            notifies = (
                await NotesNotify.filter(enabled=True)
                .all()
                .prefetch_related("account", "account__user", "account__user__settings")
                .order_by("account__uid")
            )

            for notify in notifies:
                if cls._determine_skip(notify):
                    continue

                try:
                    if notify.account.uid not in cls._notes_cache[notify.account.game]:
                        notes = await cls._get_notes(notify)
                        cls._notes_cache[notify.account.game][notify.account.uid] = notes
                    else:
                        notes = cls._notes_cache[notify.account.game][notify.account.uid]

                    await cls._process_notify(notify, notes)
                except Exception as e:
                    await cls._handle_notify_error(notify, e)
                finally:
                    notify.last_check_time = get_now()
                    await notify.save(update_fields=("last_check_time",))
                    await asyncio.sleep(1.2)
