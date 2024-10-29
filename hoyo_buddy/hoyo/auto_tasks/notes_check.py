from __future__ import annotations

import asyncio
import datetime
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar, TypeAlias

import discord
from discord import Locale
from genshin.models import Announcement, HonkaiNotes, StarRailNote, VideoStoreState, ZZZNotes
from genshin.models import Notes as GenshinNotes

from hoyo_buddy.constants import UID_TZ_OFFSET

from ...bot.error_handler import get_error_embed
from ...db.models import NotesNotify, draw_locale
from ...draw.main_funcs import draw_gi_notes_card, draw_hsr_notes_card, draw_zzz_notes_card
from ...embeds import DefaultEmbed, ErrorEmbed
from ...enums import Game, NotesNotifyType
from ...icons import (
    BATTERY_CHARGE_ICON,
    COMMISSION_ICON,
    PT_ICON,
    REALM_CURRENCY_ICON,
    RESIN_ICON,
    RTBP_ICON,
    SCRATCH_CARD_ICON,
    TBP_ICON,
)
from ...l10n import LocaleStr
from ...models import DrawInput
from ...ui.hoyo.notes.view import NotesView
from ...utils import get_now

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ...bot import HoyoBuddy

Notes: TypeAlias = GenshinNotes | HonkaiNotes | StarRailNote | ZZZNotes


class NotesChecker:
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()
    _bot: ClassVar[HoyoBuddy]

    @classmethod
    def _calc_est_time(cls, game: Game, threshold: int, current: int) -> datetime.datetime:
        """Calculate the estimated time for resin/trailblaze power to reach the threshold."""
        if game is Game.GENSHIN:
            return get_now() + datetime.timedelta(minutes=(threshold - current) * 8)
        if game in {Game.STARRAIL, Game.ZZZ, Game.HONKAI}:
            return get_now() + datetime.timedelta(minutes=(threshold - current) * 6)
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
    def _get_notify_embed(cls, notify: NotesNotify, notes: Notes | None, locale: Locale) -> DefaultEmbed:
        translator = cls._bot.translator

        match notify.type:
            case NotesNotifyType.RESIN:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="resin_reminder_button.label"),
                    description=LocaleStr(key="threshold.embed.description", threshold=notify.threshold),
                )
                embed.set_thumbnail(url=RESIN_ICON)
            case NotesNotifyType.TB_POWER:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="tbp_reminder_button.label"),
                    description=LocaleStr(key="threshold.embed.description", threshold=notify.threshold),
                )
                embed.set_thumbnail(url=TBP_ICON)
            case NotesNotifyType.RESERVED_TB_POWER:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="rtbp_reminder_button.label"),
                    description=LocaleStr(key="threshold.embed.description", threshold=notify.threshold),
                )
                embed.set_thumbnail(url=RTBP_ICON)
            case NotesNotifyType.GI_EXPED | NotesNotifyType.HSR_EXPED:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="exped_button.label"),
                    description=LocaleStr(key="exped.embed.description"),
                )
            case NotesNotifyType.PT:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="pt_button.label"),
                    description=LocaleStr(key="pt.embed.description"),
                )
                embed.set_thumbnail(url=PT_ICON)
            case NotesNotifyType.REALM_CURRENCY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="realm_curr_button.label"),
                    description=LocaleStr(key="threshold.embed.description", threshold=notify.threshold),
                )
                embed.set_thumbnail(url=REALM_CURRENCY_ICON)
            case NotesNotifyType.GI_DAILY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="daily_button.label"),
                    description=LocaleStr(key="gi_daily.embed.description"),
                )
                embed.set_thumbnail(url=COMMISSION_ICON)
            case NotesNotifyType.HSR_DAILY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="daily_training_button.label"),
                    description=LocaleStr(key="hsr_daily.embed.description"),
                )
            case NotesNotifyType.RESIN_DISCOUNT | NotesNotifyType.ECHO_OF_WAR:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="week_boss_button.label"),
                    description=LocaleStr(key="resin_discount.embed.description"),
                )
            case NotesNotifyType.BATTERY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="battery_charge_button.label"),
                    description=LocaleStr(key="threshold.embed.description", threshold=notify.threshold),
                )
                embed.set_thumbnail(url=BATTERY_CHARGE_ICON)
            case NotesNotifyType.SCRATCH_CARD:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="scratch_card_button.label"),
                    description=LocaleStr(key="scratch_card.embed.description"),
                )
                embed.set_thumbnail(url=SCRATCH_CARD_ICON)
            case NotesNotifyType.ZZZ_DAILY:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="zzz_engagement_button.label"),
                    description=LocaleStr(key="zzz_engagement.embed.description"),
                )
            case NotesNotifyType.VIDEO_STORE:
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="video_store_button.label"),
                    description=LocaleStr(key="video_store.embed.description"),
                )
            case NotesNotifyType.PLANAR_FISSURE:
                assert notify.hours_before is not None
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="planar_fissure_label"),
                    description=LocaleStr(key="planar_fissure_desc", hour=notify.hours_before),
                )
            case NotesNotifyType.HONKAI_DAILY:
                assert isinstance(notes, HonkaiNotes)
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="honkai_daily_embed_title"),
                    description=LocaleStr(key="honkai_daily_embed_description", cur=notes.current_train_score, max=600),
                )
            case NotesNotifyType.STAMINA:
                assert isinstance(notes, HonkaiNotes)
                embed = DefaultEmbed(
                    locale,
                    translator,
                    title=LocaleStr(key="notes.stamina_label"),
                    description=LocaleStr(key="threshold.embed.description", threshold=notify.threshold),
                )
                embed.add_description(
                    LocaleStr(
                        key="notes.stamina",
                        time=datetime.timedelta(seconds=notes.stamina_recover_time),
                        cur=notes.current_stamina,
                        max=notes.max_stamina,
                    )
                )

        embed.add_acc_info(notify.account, blur=False)
        embed.set_footer(text=LocaleStr(key="notif.embed.footer"))
        embed.set_image(url="attachment://notes.png")
        return embed

    @classmethod
    async def _reset_notif_count(cls, notify: NotesNotify, *, est_time: datetime.datetime | None = None) -> None:
        notify.current_notif_count = 0
        if est_time is not None:
            notify.est_time = est_time
        await notify.save(update_fields=("current_notif_count", "est_time"))

    @classmethod
    async def _notify_user(cls, notify: NotesNotify, notes: Notes | None) -> None:
        locale = await cls._get_locale(notify)
        embed = cls._get_notify_embed(notify, notes, locale)
        draw_input = DrawInput(
            dark_mode=notify.account.user.settings.dark_mode,
            locale=draw_locale(locale, notify.account),
            session=cls._bot.session,
            filename="notes.png",
            executor=cls._bot.executor,
            loop=cls._bot.loop,
        )

        if isinstance(notes, ZZZNotes):
            buffer = await draw_zzz_notes_card(draw_input, notes, cls._bot.translator)
        elif isinstance(notes, StarRailNote):
            buffer = await draw_hsr_notes_card(draw_input, notes, cls._bot.translator)
        elif isinstance(notes, GenshinNotes):
            buffer = await draw_gi_notes_card(draw_input, notes, cls._bot.translator)
        else:
            buffer = None

        if buffer is None:
            file_ = None
        else:
            buffer.seek(0)
            file_ = discord.File(buffer, filename="notes.png")

        view = NotesView(
            notify.account,
            notify.account.user.settings.dark_mode,
            author=None,
            locale=locale,
            translator=cls._bot.translator,
        )
        view.bytes_obj = buffer
        message = await cls._bot.dm_user(notify.account.user.id, embed=embed, file=file_, view=view)
        view.message = message

        notify.enabled = message is not None
        notify.last_notif_time = get_now()
        notify.current_notif_count += 1 if message is not None else 0
        await notify.save(update_fields=("enabled", "last_notif_time", "current_notif_count"))

    @classmethod
    async def _process_realm_currency_notify(cls, notify: NotesNotify, notes: GenshinNotes) -> None:
        """Process realm currency notification."""
        current = notes.current_realm_currency
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            est_time = get_now() + notes.remaining_realm_currency_recovery_time
            return await cls._reset_notif_count(notify, est_time=est_time)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_rtbp_notify(cls, notify: NotesNotify, notes: StarRailNote) -> None:
        """Process reserved trailblaze power notification."""
        current = notes.current_reserve_stamina
        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            return await cls._reset_notif_count(notify)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_expedition_notify(cls, notify: NotesNotify, notes: GenshinNotes | StarRailNote) -> None:
        """Process expedition notification."""
        if any(not exped.finished for exped in notes.expeditions):
            min_remain_time = min(exped.remaining_time for exped in notes.expeditions if not exped.finished)
            est_time = get_now() + min_remain_time
            return await cls._reset_notif_count(notify, est_time=est_time)

        if any(exped.finished for exped in notes.expeditions) and notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_pt_notify(cls, notify: NotesNotify, notes: GenshinNotes) -> None:
        remaining_time = notes.remaining_transformer_recovery_time
        if remaining_time is None:
            return None

        if remaining_time.seconds >= 0:
            est_time = get_now() + remaining_time
            return await cls._reset_notif_count(notify, est_time=est_time)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_daily_notify(cls, notify: NotesNotify, notes: Notes) -> None:
        if notify.last_check_time is not None and get_now().day != notify.last_check_time.day:
            return await cls._reset_notif_count(notify)

        gi = isinstance(notes, GenshinNotes) and notes.completed_commissions + notes.daily_task.completed_tasks >= 4
        hsr = isinstance(notes, StarRailNote) and notes.current_train_score >= notes.max_train_score
        zzz = isinstance(notes, ZZZNotes) and notes.engagement.current >= notes.engagement.max
        honkai = isinstance(notes, HonkaiNotes) and notes.current_train_score >= 600

        if gi or hsr or zzz or honkai:
            return await cls._reset_notif_count(notify, est_time=notify.account.server_reset_datetime)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_week_boss_discount_notify(cls, notify: NotesNotify, notes: Notes | StarRailNote) -> None:
        if notify.last_check_time is not None and get_now().day != notify.last_check_time.day:
            return await cls._reset_notif_count(notify)

        if isinstance(notes, GenshinNotes) and notes.remaining_resin_discounts == 0:
            return None
        if isinstance(notes, StarRailNote) and notes.remaining_weekly_discounts == 0:
            return None

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_scratch_card_notify(cls, notify: NotesNotify, notes: ZZZNotes) -> None:
        if notes.scratch_card_completed:
            return await cls._reset_notif_count(notify, est_time=notify.account.server_reset_datetime)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_video_store_notify(cls, notify: NotesNotify, notes: ZZZNotes) -> None:
        if notes.video_store_state in {VideoStoreState.CURRENTLY_OPEN, VideoStoreState.WAITING_TO_OPEN}:
            return await cls._reset_notif_count(notify)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_planar_fissure_notify(cls, notify: NotesNotify, anns: Sequence[Announcement]) -> None:
        assert notify.hours_before is not None

        for ann in anns:
            if "Planar Fissure Event" in ann.title:
                planar_ann = ann
                break
        else:
            return None

        # Get now in the timezone of the accounts's server
        now = get_now() + datetime.timedelta(hours=UID_TZ_OFFSET.get(str(notify.account.uid)[0], 0))
        now = now.replace(tzinfo=None)

        if planar_ann.start_time <= now <= planar_ann.end_time:
            return await cls._reset_notif_count(notify)

        if notify.current_notif_count < notify.max_notif_count and planar_ann.start_time - now <= datetime.timedelta(
            hours=notify.hours_before
        ):
            await cls._notify_user(notify, notes=None)

        return None

    @classmethod
    async def _process_stamina_notify(cls, notify: NotesNotify, notes: Notes) -> None:
        """Process stamina notification."""
        if isinstance(notes, HonkaiNotes):
            current = notes.current_stamina
            game = Game.HONKAI
        elif isinstance(notes, GenshinNotes):
            current = notes.current_resin
            game = Game.GENSHIN
        elif isinstance(notes, StarRailNote):
            current = notes.current_stamina
            game = Game.STARRAIL
        else:
            current = notes.battery_charge.current
            game = Game.ZZZ

        threshold = notify.threshold
        assert threshold is not None

        if current < threshold:
            est_time = cls._calc_est_time(game, threshold, current)
            return await cls._reset_notif_count(notify, est_time=est_time)

        if notify.current_notif_count < notify.max_notif_count:
            await cls._notify_user(notify, notes)
        return None

    @classmethod
    async def _process_notify(
        cls, notify: NotesNotify, notes: Notes | StarRailNote | ZZZNotes | None, anns: Sequence[Announcement] | None
    ) -> None:
        """Proces notification."""
        match notify.type:
            case NotesNotifyType.RESERVED_TB_POWER:
                assert isinstance(notes, StarRailNote)
                await cls._process_rtbp_notify(notify, notes)
            case NotesNotifyType.GI_EXPED | NotesNotifyType.HSR_EXPED:
                assert isinstance(notes, GenshinNotes | StarRailNote)
                await cls._process_expedition_notify(notify, notes)
            case NotesNotifyType.PT:
                assert isinstance(notes, GenshinNotes)
                await cls._process_pt_notify(notify, notes)
            case NotesNotifyType.REALM_CURRENCY:
                assert isinstance(notes, GenshinNotes)
                await cls._process_realm_currency_notify(notify, notes)
            case (
                NotesNotifyType.GI_DAILY
                | NotesNotifyType.HSR_DAILY
                | NotesNotifyType.ZZZ_DAILY
                | NotesNotifyType.HONKAI_DAILY
            ):
                assert notes is not None
                await cls._process_daily_notify(notify, notes)
            case NotesNotifyType.RESIN_DISCOUNT | NotesNotifyType.ECHO_OF_WAR:
                assert isinstance(notes, Notes | StarRailNote)
                await cls._process_week_boss_discount_notify(notify, notes)
            case NotesNotifyType.BATTERY | NotesNotifyType.STAMINA | NotesNotifyType.RESIN | NotesNotifyType.TB_POWER:
                assert notes is not None
                await cls._process_stamina_notify(notify, notes)
            case NotesNotifyType.SCRATCH_CARD:
                assert isinstance(notes, ZZZNotes)
                await cls._process_scratch_card_notify(notify, notes)
            case NotesNotifyType.VIDEO_STORE:
                assert isinstance(notes, ZZZNotes)
                await cls._process_video_store_notify(notify, notes)
            case NotesNotifyType.PLANAR_FISSURE:
                assert anns is not None
                await cls._process_planar_fissure_notify(notify, anns)

    @classmethod
    async def _handle_notify_error(cls, notify: NotesNotify, e: Exception) -> None:
        content = LocaleStr(key="process_notify_error.content")
        locale = await cls._get_locale(notify)
        embed = cls._get_notify_error_embed(e, locale)
        embed.add_acc_info(notify.account, blur=False)

        await cls._bot.dm_user(
            notify.account.user.id, embed=embed, content=content.translate(cls._bot.translator, locale)
        )

        notify.enabled = False
        await notify.save(update_fields=("enabled",))

    @classmethod
    def _determine_skip(cls, notify: NotesNotify) -> bool:
        """Determine if the notification should be skipped."""
        if notify.est_time is not None and get_now() < notify.est_time:
            return True

        if notify.notify_weekday is not None and notify.notify_weekday != get_now().weekday() + 1:
            return True

        if notify.last_check_time is not None and get_now() - notify.last_check_time < datetime.timedelta(
            minutes=notify.check_interval
        ):
            return True

        if notify.last_notif_time is not None and get_now() - notify.last_notif_time < datetime.timedelta(
            minutes=notify.notify_interval
        ):
            return True

        if (  # noqa: SIM103
            notify.notify_time is not None
            and get_now() < notify.account.server_reset_datetime - datetime.timedelta(hours=notify.notify_time)
        ):
            return True

        return False

    @classmethod
    async def _get_notes(cls, notify: NotesNotify) -> Notes | StarRailNote | ZZZNotes:
        if notify.account.game is Game.GENSHIN:
            notes = await notify.account.client.get_genshin_notes()
        elif notify.account.game is Game.STARRAIL:
            notes = await notify.account.client.get_starrail_notes()
        elif notify.account.game is Game.ZZZ:
            notes = await notify.account.client.get_zzz_notes()
        elif notify.account.game is Game.HONKAI:
            notes = await notify.account.client.get_honkai_notes(notify.account.uid)
        else:
            raise NotImplementedError
        return notes

    @classmethod
    async def _adjust_notify(cls, notify: NotesNotify) -> NotesNotify:
        if notify.type is NotesNotifyType.VIDEO_STORE:
            notify.notify_time = None
            await notify.save(update_fields=("notify_time",))
        return notify

    @classmethod
    async def execute(cls, bot: HoyoBuddy) -> None:
        if cls._lock.locked():
            return

        async with cls._lock:
            cls._bot = bot
            notes_cache: defaultdict[Game, dict[int, Notes | StarRailNote | ZZZNotes]] = defaultdict(dict)

            notifies = await NotesNotify.filter(enabled=True).all().order_by("account__uid")

            for notify_ in notifies:
                notify = await cls._adjust_notify(notify_)
                await notify.fetch_related("account")
                if cls._determine_skip(notify):
                    continue

                await notify.fetch_related("account__user", "account__user__settings")

                try:
                    if notify.type is NotesNotifyType.PLANAR_FISSURE:
                        anns = await notify.account.client.get_starrail_announcements()
                        notes = None
                    else:
                        anns = None
                        if notify.account.uid not in notes_cache[notify.account.game]:
                            notes = await cls._get_notes(notify)
                            notes_cache[notify.account.game][notify.account.uid] = notes
                        else:
                            notes = notes_cache[notify.account.game][notify.account.uid]

                    await cls._process_notify(notify, notes, anns)
                except Exception as e:
                    await cls._handle_notify_error(notify, e)
                finally:
                    notify.last_check_time = get_now()
                    await notify.save(update_fields=("last_check_time",))
                    await asyncio.sleep(1.2)
