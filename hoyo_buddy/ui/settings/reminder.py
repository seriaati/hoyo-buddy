from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import discord
from loguru import logger

from hoyo_buddy import emojis, ui
from hoyo_buddy.db import NotesNotify
from hoyo_buddy.emojis import TOGGLE_EMOJIS
from hoyo_buddy.enums import Game, NotesNotifyType
from hoyo_buddy.l10n import LocaleStr, WeekdayStr
from hoyo_buddy.ui.hoyo.notes import modals

if TYPE_CHECKING:
    from collections.abc import Iterable

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Interaction

    from .view import SettingsView  # noqa: F401

type ReminderModal = (
    modals.TypeOneModal
    | modals.TypeTwoModal
    | modals.TypeThreeModal
    | modals.TypeFourModal
    | modals.TypeFiveModal
)


@dataclass
class ReminderItem:
    title: LocaleStr
    notify: NotesNotify | None
    notify_type: NotesNotifyType
    emoji: str | None = None


NOTIFY_TYPE_TO_MODAL_TYPE: dict[NotesNotifyType, type[ReminderModal]] = {
    NotesNotifyType.RESIN: modals.TypeOneModal,
    NotesNotifyType.REALM_CURRENCY: modals.TypeOneModal,
    NotesNotifyType.PT: modals.TypeTwoModal,
    NotesNotifyType.GI_EXPED: modals.TypeTwoModal,
    NotesNotifyType.GI_DAILY: modals.TypeThreeModal,
    NotesNotifyType.RESIN_DISCOUNT: modals.TypeFourModal,
    NotesNotifyType.TB_POWER: modals.TypeOneModal,
    NotesNotifyType.RESERVED_TB_POWER: modals.TypeOneModal,
    NotesNotifyType.HSR_EXPED: modals.TypeTwoModal,
    NotesNotifyType.HSR_DAILY: modals.TypeThreeModal,
    NotesNotifyType.ECHO_OF_WAR: modals.TypeFourModal,
    NotesNotifyType.PLANAR_FISSURE: modals.TypeFiveModal,
    NotesNotifyType.BATTERY: modals.TypeOneModal,
    NotesNotifyType.ZZZ_DAILY: modals.TypeThreeModal,
    NotesNotifyType.SCRATCH_CARD: modals.TypeThreeModal,
    NotesNotifyType.VIDEO_STORE: modals.TypeTwoModal,
    NotesNotifyType.RIDU_POINTS: modals.TypeFourModal,
    NotesNotifyType.ZZZ_BOUNTY: modals.TypeFourModal,
}

NOTIFY_TYPE_MODAL_KWARGS: dict[NotesNotifyType | tuple[NotesNotifyType, ...], dict[str, Any]] = {
    NotesNotifyType.RESIN: {
        "title": LocaleStr(key="resin_reminder_modal.title"),
        "threshold_max_value": 200,
        "min_notify_interval": 10,
    },
    NotesNotifyType.TB_POWER: {
        "title": LocaleStr(
            key="reminder_modal.title",
            notify=LocaleStr(key="hsr_note_stamina", mi18n_game=Game.STARRAIL),
        ),
        "threshold_max_value": 300,
        "min_notify_interval": 10,
    },
    NotesNotifyType.RESERVED_TB_POWER: {
        "title": LocaleStr(
            key="reminder_modal.title",
            notify=LocaleStr(key="hsr_note_reserve_stamina", mi18n_game=Game.STARRAIL),
        ),
        "threshold_max_value": 2400,
        "min_notify_interval": 30,
    },
    NotesNotifyType.BATTERY: {
        "title": LocaleStr(
            key="reminder_modal.title", notify=LocaleStr(key="battery_num", mi18n_game=Game.ZZZ)
        ),
        "threshold_max_value": 240,
        "min_notify_interval": 10,
    },
    NotesNotifyType.STAMINA: {
        "title": LocaleStr(key="reminder_modal.title", notify=LocaleStr(key="notes.stamina_label")),
        "threshold_max_value": 240,
        "min_notify_interval": 10,
    },
    NotesNotifyType.REALM_CURRENCY: {
        "title": LocaleStr(key="realm_curr_modal.title"),
        "threshold_max_value": 2400,
        "min_notify_interval": 30,
    },
    NotesNotifyType.PT: {"title": LocaleStr(key="pt_modal.title"), "min_notify_interval": 30},
    (NotesNotifyType.GI_EXPED, NotesNotifyType.HSR_EXPED): {
        "title": LocaleStr(key="exped_modal.title"),
        "min_notify_interval": 30,
    },
    (NotesNotifyType.GI_DAILY, NotesNotifyType.HSR_DAILY, NotesNotifyType.ZZZ_DAILY): {
        "title": LocaleStr(key="daily_modal.title"),
        "min_notify_interval": 30,
    },
    (NotesNotifyType.RESIN_DISCOUNT, NotesNotifyType.ECHO_OF_WAR): {
        "title": LocaleStr(key="week_boss_modal.title"),
        "min_notify_interval": 30,
    },
    NotesNotifyType.PLANAR_FISSURE: {
        "title": LocaleStr(
            key="reminder_modal.title", notify=LocaleStr(key="planar_fissure_label")
        ),
        "min_notify_interval": 60,
    },
    NotesNotifyType.SCRATCH_CARD: {
        "title": LocaleStr(
            key="reminder_modal.title", notify=LocaleStr(key="card", mi18n_game=Game.ZZZ)
        ),
        "min_notify_interval": 30,
    },
    NotesNotifyType.VIDEO_STORE: {
        "title": LocaleStr(
            key="reminder_modal.title", notify=LocaleStr(key="vhs_sale", mi18n_game=Game.ZZZ)
        ),
        "min_notify_interval": 30,
    },
    NotesNotifyType.RIDU_POINTS: {
        "title": LocaleStr(
            key="reminder_modal.title",
            notify=LocaleStr(key="weekly_task_point", mi18n_game=Game.ZZZ),
        ),
        "min_notify_interval": 60,
    },
    NotesNotifyType.ZZZ_BOUNTY: {
        "title": LocaleStr(
            key="reminder_modal.title",
            notify=LocaleStr(key="bounty_commission", mi18n_game=Game.ZZZ),
        ),
        "min_notify_interval": 60,
    },
}

NOTIFY_TYPE_CHECK_INTERVALS: dict[NotesNotifyType, int] = {
    NotesNotifyType.RESIN: 10,
    NotesNotifyType.REALM_CURRENCY: 30,
    NotesNotifyType.PT: 30,
    NotesNotifyType.GI_EXPED: 30,
    NotesNotifyType.GI_DAILY: 30,
    NotesNotifyType.RESIN_DISCOUNT: 30,
    NotesNotifyType.TB_POWER: 10,
    NotesNotifyType.RESERVED_TB_POWER: 30,
    NotesNotifyType.HSR_EXPED: 30,
    NotesNotifyType.HSR_DAILY: 30,
    NotesNotifyType.ECHO_OF_WAR: 30,
    NotesNotifyType.PLANAR_FISSURE: 60,
    NotesNotifyType.BATTERY: 10,
    NotesNotifyType.ZZZ_DAILY: 30,
    NotesNotifyType.SCRATCH_CARD: 30,
    NotesNotifyType.VIDEO_STORE: 30,
    NotesNotifyType.RIDU_POINTS: 60,
    NotesNotifyType.ZZZ_BOUNTY: 60,
}


class ConfigureButton(ui.Button["SettingsView"]):
    def __init__(self, notify: NotesNotify | None, notify_type: NotesNotifyType) -> None:
        super().__init__(style=discord.ButtonStyle.blurple, emoji=emojis.EDIT)
        self.notify = notify
        self.notify_type = notify_type

    def _get_modal_kwargs(self) -> Any:
        for ntype, kwargs in NOTIFY_TYPE_MODAL_KWARGS.items():
            if isinstance(ntype, tuple):
                if self.notify_type in ntype:
                    return kwargs
            elif self.notify_type is ntype:
                return kwargs

    async def callback(self, i: Interaction) -> None:
        modal_cls = NOTIFY_TYPE_TO_MODAL_TYPE.get(self.notify_type)
        if modal_cls is None:
            msg = f"No modal found for notify type: {self.notify_type}"
            raise ValueError(msg)

        kwargs = self._get_modal_kwargs()
        modal: ReminderModal = modal_cls(self.notify, **kwargs)
        modal.translate(self.view.locale)

        await i.response.send_modal(modal)
        timed_out = await modal.wait()
        if timed_out:
            return

        await NotesReminderMixin.process_modal_value(
            modal=modal, notify=self.notify, notify_type=self.notify_type, account=self.view.account
        )
        await self.view.update(i)


class NotesReminderMixin:
    @staticmethod
    def get_value(*, notify: NotesNotify | None, notify_type: NotesNotifyType) -> LocaleStr:
        modal_cls = NOTIFY_TYPE_TO_MODAL_TYPE.get(notify_type)
        if modal_cls is None:
            msg = f"No modal found for notify type: {notify_type}"
            raise ValueError(msg)

        if modal_cls is modals.TypeOneModal:
            return NotesReminderMixin._get_type1_value(notify)
        if modal_cls is modals.TypeTwoModal:
            return NotesReminderMixin._get_type2_value(notify)
        if modal_cls is modals.TypeThreeModal:
            return NotesReminderMixin._get_type3_value(notify)
        if modal_cls is modals.TypeFourModal:
            return NotesReminderMixin._get_type4_value(notify)
        if modal_cls is modals.TypeFiveModal:
            return NotesReminderMixin._get_type5_value(notify)

        msg = f"Unknown notify type: {notify_type}"
        raise ValueError(msg)

    @staticmethod
    def _get_type1_value(notify: NotesNotify | None) -> LocaleStr:
        if notify is None:
            return LocaleStr(key="reminder_settings.not_set")
        return LocaleStr(
            key="reminder_settings.reminde.set.type1",
            status=TOGGLE_EMOJIS[notify.enabled],
            threshold=notify.threshold,
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
        )

    @staticmethod
    def _get_type2_value(notify: NotesNotify | None) -> LocaleStr:
        if notify is None:
            return LocaleStr(key="reminder_settings.not_set")
        return LocaleStr(
            key="reminder_settings.reminde.set.type2",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
        )

    @staticmethod
    def _get_type3_value(notify: NotesNotify | None) -> LocaleStr:
        if notify is None:
            return LocaleStr(key="reminder_settings.not_set")
        return LocaleStr(
            key="reminder_settings.reminde.set.type3",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
            notify_time=notify.notify_time,
        )

    @staticmethod
    def _get_type4_value(notify: NotesNotify | None) -> LocaleStr:
        if notify is None:
            return LocaleStr(key="reminder_settings.not_set")

        if notify.notify_weekday is None:
            msg = "notify_weekday is None"
            raise ValueError(msg)

        return LocaleStr(
            key="reminder_settings.reminde.set.type4",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
            notify_time=notify.notify_time,
            notify_weekday=WeekdayStr(notify.notify_weekday - 1),
        )

    @staticmethod
    def _get_type5_value(notify: NotesNotify | None) -> LocaleStr:
        if notify is None:
            return LocaleStr(key="reminder_settings.not_set")

        return LocaleStr(
            key="reminder_settings.reminde.set.type5",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
            hours_before=notify.hours_before,
        )

    @staticmethod
    def _reset_notify(notify: NotesNotify) -> None:
        notify.est_time = None
        notify.last_notif_time = None
        notify.last_check_time = None
        notify.current_notif_count = 0

    @staticmethod
    async def process_modal_value(
        *,
        modal: ReminderModal,
        notify: NotesNotify | None,
        notify_type: NotesNotifyType,
        account: HoyoAccount,
    ) -> None:
        # parse modal values
        enabled = bool(modal.enabled.value)
        notify_interval = int(modal.notify_interval.value)
        max_notif_count = int(modal.max_notif_count.value)

        check_interval = NOTIFY_TYPE_CHECK_INTERVALS.get(notify_type)
        if check_interval is None:
            logger.error(f"No check interval found for notify type: {notify_type}")
            check_interval = 10

        threshold_label = getattr(modal, "threshold", None)
        threshold = (
            int(threshold_label.value)
            if threshold_label is not None and threshold_label.value
            else None
        )

        notify_time_label = getattr(modal, "notify_time", None)
        notify_time = (
            int(notify_time_label.value)
            if notify_time_label is not None and notify_time_label.value
            else None
        )

        notify_weekday_label = getattr(modal, "notify_weekday", None)
        notify_weekday = (
            int(notify_weekday_label.value)
            if notify_weekday_label is not None and notify_weekday_label.value
            else None
        )

        hours_before_label = getattr(modal, "hours_before", None)
        hours_before = (
            int(hours_before_label.value)
            if hours_before_label is not None and hours_before_label.value
            else None
        )

        if notify is None:
            notify = NotesNotify(
                account=account,
                type=notify_type,
                enabled=enabled,
                threshold=threshold,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                notify_time=notify_time,
                notify_weekday=notify_weekday,
                hours_before=hours_before,
                check_interval=check_interval,
            )
        else:
            NotesReminderMixin._reset_notify(notify)

            notify.enabled = enabled
            notify.threshold = threshold
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.notify_time = notify_time
            notify.notify_weekday = notify_weekday
            notify.hours_before = hours_before

        await notify.save()


class BaseReminderContainer(ui.DefaultContainer["SettingsView"], NotesReminderMixin):
    def __init__(self, items: Iterable[ReminderItem]) -> None:
        super().__init__(
            ui.TextDisplay(
                LocaleStr(
                    custom_str="# {title}\n{desc}",
                    title=LocaleStr(key="reminder_settings_title"),
                    desc=LocaleStr(key="reminder_settings_desc"),
                )
            ),
            discord.ui.Separator(visible=False, spacing=discord.SeparatorSpacing.large),
        )
        self._add_reminder_items(items)

    def _add_reminder_items(self, items: Iterable[ReminderItem]) -> None:
        for item in items:
            self.add_item(
                ui.Section(
                    ui.TextDisplay(
                        LocaleStr(
                            custom_str="### {emoji}{title}\n{content}",
                            title=item.title,
                            content=self.get_value(
                                notify=item.notify, notify_type=item.notify_type
                            ),
                            emoji=f"{item.emoji} " if item.emoji else "",
                        )
                    ),
                    accessory=ConfigureButton(item.notify, item.notify_type),
                )
            )


class GenshinReminderContainer(BaseReminderContainer):
    def __init__(
        self,
        *,
        resin_notify: NotesNotify | None,
        realm_currency_notify: NotesNotify | None,
        pt_notify: NotesNotify | None,
        expedition_notify: NotesNotify | None,
        daily_notify: NotesNotify | None,
        resin_discount_notify: NotesNotify | None,
    ) -> None:
        items: tuple[ReminderItem, ...] = (
            ReminderItem(
                title=LocaleStr(key="resin_reminder_button.label"),
                notify=resin_notify,
                notify_type=NotesNotifyType.RESIN,
                emoji=emojis.RESIN,
            ),
            ReminderItem(
                title=LocaleStr(key="realm_curr_button.label"),
                notify=realm_currency_notify,
                notify_type=NotesNotifyType.REALM_CURRENCY,
                emoji=emojis.REALM_CURRENCY,
            ),
            ReminderItem(
                title=LocaleStr(key="pt_button.label"),
                notify=pt_notify,
                notify_type=NotesNotifyType.PT,
                emoji=emojis.PT_EMOJI,
            ),
            ReminderItem(
                title=LocaleStr(key="exped_button.label"),
                notify=expedition_notify,
                notify_type=NotesNotifyType.GI_EXPED,
            ),
            ReminderItem(
                title=LocaleStr(key="daily_button.label"),
                notify=daily_notify,
                notify_type=NotesNotifyType.GI_DAILY,
            ),
            ReminderItem(
                title=LocaleStr(key="week_boss_button.label"),
                notify=resin_discount_notify,
                notify_type=NotesNotifyType.RESIN_DISCOUNT,
            ),
        )
        super().__init__(items)


class HSRReminderContainer(BaseReminderContainer):
    def __init__(
        self,
        *,
        tbp_notify: NotesNotify | None,
        reserved_tbp_notify: NotesNotify | None,
        expedition_notify: NotesNotify | None,
        daily_notify: NotesNotify | None,
        echo_of_war_notify: NotesNotify | None,
        planar_fissure_notify: NotesNotify | None,
    ) -> None:
        items: tuple[ReminderItem, ...] = (
            ReminderItem(
                title=LocaleStr(key="hsr_note_stamina", mi18n_game=Game.STARRAIL),
                notify=tbp_notify,
                notify_type=NotesNotifyType.TB_POWER,
                emoji=emojis.TRAILBLAZE_POWER,
            ),
            ReminderItem(
                title=LocaleStr(key="hsr_note_reserve_stamina", mi18n_game=Game.STARRAIL),
                notify=reserved_tbp_notify,
                notify_type=NotesNotifyType.RESERVED_TB_POWER,
                emoji=emojis.RESERVED_TRAILBLAZE_POWER,
            ),
            ReminderItem(
                title=LocaleStr(key="exped_button.label"),
                notify=expedition_notify,
                notify_type=NotesNotifyType.HSR_EXPED,
            ),
            ReminderItem(
                title=LocaleStr(key="daily_button.label"),
                notify=daily_notify,
                notify_type=NotesNotifyType.HSR_DAILY,
            ),
            ReminderItem(
                title=LocaleStr(key="week_boss_button.label"),
                notify=echo_of_war_notify,
                notify_type=NotesNotifyType.ECHO_OF_WAR,
            ),
            ReminderItem(
                title=LocaleStr(key="planar_fissure_label"),
                notify=planar_fissure_notify,
                notify_type=NotesNotifyType.PLANAR_FISSURE,
            ),
        )
        super().__init__(items)


class ZZZReminderContainer(BaseReminderContainer):
    def __init__(
        self,
        *,
        battery_notify: NotesNotify | None,
        daily_notify: NotesNotify | None,
        scratch_card_notify: NotesNotify | None,
        video_store_notify: NotesNotify | None,
        ridu_points_notify: NotesNotify | None,
        bounty_comm_notify: NotesNotify | None,
    ) -> None:
        items: tuple[ReminderItem, ...] = (
            ReminderItem(
                title=LocaleStr(key="battery_num", mi18n_game=Game.ZZZ),
                notify=battery_notify,
                notify_type=NotesNotifyType.BATTERY,
                emoji=emojis.BATTERY_CHARGE_EMOJI,
            ),
            ReminderItem(
                title=LocaleStr(key="daily_button.label"),
                notify=daily_notify,
                notify_type=NotesNotifyType.ZZZ_DAILY,
            ),
            ReminderItem(
                title=LocaleStr(key="card", mi18n_game=Game.ZZZ),
                notify=scratch_card_notify,
                notify_type=NotesNotifyType.SCRATCH_CARD,
                emoji=emojis.SCRATCH_CARD_EMOJI,
            ),
            ReminderItem(
                title=LocaleStr(key="vhs_sale", mi18n_game=Game.ZZZ),
                notify=video_store_notify,
                notify_type=NotesNotifyType.VIDEO_STORE,
            ),
            ReminderItem(
                title=LocaleStr(key="weekly_task_point", mi18n_game=Game.ZZZ),
                notify=ridu_points_notify,
                notify_type=NotesNotifyType.RIDU_POINTS,
            ),
            ReminderItem(
                title=LocaleStr(key="bounty_commission", mi18n_game=Game.ZZZ),
                notify=bounty_comm_notify,
                notify_type=NotesNotifyType.ZZZ_BOUNTY,
            ),
        )
        super().__init__(items)


class HonkaiReminderContainer(BaseReminderContainer):
    def __init__(self, stamina_notify: NotesNotify | None) -> None:
        items: tuple[ReminderItem, ...] = (
            ReminderItem(
                title=LocaleStr(key="notes.stamina_label"),
                notify=stamina_notify,
                notify_type=NotesNotifyType.STAMINA,
            ),
        )
        super().__init__(items)


class ReminderContainer:
    @staticmethod
    async def for_account(account: HoyoAccount) -> BaseReminderContainer:
        game = account.game
        if game == Game.GENSHIN:
            return GenshinReminderContainer(
                resin_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.RESIN
                ),
                realm_currency_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.REALM_CURRENCY
                ),
                pt_notify=await NotesNotify.get_or_none(account=account, type=NotesNotifyType.PT),
                expedition_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.GI_EXPED
                ),
                daily_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.GI_DAILY
                ),
                resin_discount_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.RESIN_DISCOUNT
                ),
            )

        if game == Game.STARRAIL:
            return HSRReminderContainer(
                tbp_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.TB_POWER
                ),
                reserved_tbp_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.RESERVED_TB_POWER
                ),
                expedition_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.HSR_EXPED
                ),
                daily_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.HSR_DAILY
                ),
                echo_of_war_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.ECHO_OF_WAR
                ),
                planar_fissure_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.PLANAR_FISSURE
                ),
            )

        if game == Game.ZZZ:
            return ZZZReminderContainer(
                battery_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.BATTERY
                ),
                daily_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.ZZZ_DAILY
                ),
                scratch_card_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.SCRATCH_CARD
                ),
                video_store_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.VIDEO_STORE
                ),
                ridu_points_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.RIDU_POINTS
                ),
                bounty_comm_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.ZZZ_BOUNTY
                ),
            )

        if game == Game.HONKAI:
            return HonkaiReminderContainer(
                stamina_notify=await NotesNotify.get_or_none(
                    account=account, type=NotesNotifyType.STAMINA
                )
            )

        msg = f"Reminders not supported for game: {game}"
        raise ValueError(msg)
