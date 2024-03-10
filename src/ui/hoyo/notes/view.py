from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from src.bot.translator import LocaleStr
from src.db.models import NotesNotify
from src.embeds import DefaultEmbed
from src.emojis import BELL_OUTLINE, TOGGLE_EMOJIS
from src.enums import Game, NotesNotifyType, Weekday

from ...components import Button, GoBackButton, View

if TYPE_CHECKING:
    from src.bot.bot import INTERACTION
    from src.bot.translator import Translator
    from src.db.models import HoyoAccount

    from .modals.type_four import TypeFourModal
    from .modals.type_one import TypeOneModal
    from .modals.type_three import TypeThreeModal
    from .modals.type_two import TypeTwoModal


class NotesView(View):
    def __init__(
        self,
        account: "HoyoAccount",
        *,
        author: User | Member | None,
        locale: Locale,
        translator: "Translator",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self._account = account

        self.add_item(ReminderButton())

    @staticmethod
    def _get_type1_value(notify: "NotesNotify | None") -> LocaleStr:
        if notify is None:
            return LocaleStr("Not set", key="reminder_settings.not_set")
        return LocaleStr(
            (
                "Status: {status}\n"
                "Threshold: {threshold}\n"
                "Notify Interval: {notify_interval} minutes\n"
                "Max Notify Count: {max_notif_count}"
            ),
            key="reminder_settings.reminde.set.type1",
            status=TOGGLE_EMOJIS[notify.enabled],
            threshold=notify.threshold,
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
        )

    @staticmethod
    def _get_type2_value(notify: "NotesNotify | None") -> LocaleStr:
        if notify is None:
            return LocaleStr("Not set", key="reminder_settings.not_set")
        return LocaleStr(
            (
                "Status: {status}\n"
                "Notify Interval: {notify_interval} minutes\n"
                "Max Notify Count: {max_notif_count}"
            ),
            key="reminder_settings.reminde.set.type2",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
        )

    @staticmethod
    def _get_type3_value(notify: "NotesNotify | None") -> LocaleStr:
        if notify is None:
            return LocaleStr("Not set", key="reminder_settings.not_set")
        return LocaleStr(
            (
                "Status: {status}\n"
                "Notify Interval: {notify_interval} minutes\n"
                "Max Notify Count: {max_notif_count}\n"
                "Notify Time: {notify_time} hours before the server resets\n"
            ),
            key="reminder_settings.reminde.set.type2",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
            notify_time=notify.notify_time,
        )

    @staticmethod
    def _get_type4_value(notify: "NotesNotify | None") -> LocaleStr:
        if notify is None:
            return LocaleStr("Not set", key="reminder_settings.not_set")
        return LocaleStr(
            (
                "Status: {status}\n"
                "Notify Interval: {notify_interval} minutes\n"
                "Max Notify Count: {max_notif_count}\n"
                "Notify Time: {notify_time} hours before the server resets\n"
                "Notify Weekday: {notify_weekday}"
            ),
            key="reminder_settings.reminde.set.type2",
            status=TOGGLE_EMOJIS[notify.enabled],
            notify_interval=notify.notify_interval,
            max_notif_count=notify.max_notif_count,
            notify_time=notify.notify_time,
            notify_weekday=LocaleStr(
                Weekday(notify.notify_weekday).name.title(), warn_no_key=False
            ),
        )

    async def _get_reminder_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("Real-Time Notes Reminders", key="reminder_settings_title"),
        )

        if self._account.game is Game.GENSHIN:
            resin_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.RESIN
            )
            embed.add_field(
                name=LocaleStr("Resin Reminder", key="resin_reminder_button.label"),
                value=self._get_type1_value(resin_notify),
                inline=False,
            )

            realm_currency_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.REALM_CURRENCY
            )
            embed.add_field(
                name=LocaleStr("Realm Currency Reminder", key="realm_curr_button.label"),
                value=self._get_type1_value(realm_currency_notify),
                inline=False,
            )

            pt_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.PT
            )
            embed.add_field(
                name=LocaleStr("Parametric Transformer Reminder", key="pt_button.label"),
                value=self._get_type2_value(pt_notify),
                inline=False,
            )

            expedition_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.GI_EXPED
            )
            embed.add_field(
                name=LocaleStr("Expedition Reminder", key="exped_button.label"),
                value=self._get_type2_value(expedition_notify),
                inline=False,
            )

            daily_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.GI_DAILY
            )
            embed.add_field(
                name=LocaleStr("Daily Reminder", key="daily_button.label"),
                value=self._get_type3_value(daily_notify),
                inline=False,
            )

            resin_discount_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.RESIN_DISCOUNT
            )
            embed.add_field(
                name=LocaleStr("Weekly Boss Discount Reminder", key="week_boss_button.label"),
                value=self._get_type4_value(resin_discount_notify),
                inline=False,
            )

        elif self._account.game is Game.STARRAIL:
            tbp_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.TB_POWER
            )
            embed.add_field(
                name=LocaleStr("Trailblaze Power Reminder", key="tbp_reminder_button.label"),
                value=self._get_type1_value(tbp_notify),
                inline=False,
            )

            reserved_tbp_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.RESERVED_TB_POWER
            )
            embed.add_field(
                name=LocaleStr(
                    "Reserved Trailblaze Power Reminder", key="rtbp_reminder_button.label"
                ),
                value=self._get_type1_value(reserved_tbp_notify),
                inline=False,
            )

            expedition_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.HSR_EXPED
            )
            embed.add_field(
                name=LocaleStr("Expedition Reminder", key="exped_button.label"),
                value=self._get_type2_value(expedition_notify),
                inline=False,
            )

            daily_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.HSR_DAILY
            )
            embed.add_field(
                name=LocaleStr("Daily Reminder", key="daily_button.label"),
                value=self._get_type3_value(daily_notify),
                inline=False,
            )

            echo_of_war_notify = await NotesNotify.get_or_none(
                account=self._account, type=NotesNotifyType.ECHO_OF_WAR
            )
            embed.add_field(
                name=LocaleStr("Weekly Boss Discount Reminder", key="week_boss_button.label"),
                value=self._get_type4_value(echo_of_war_notify),
                inline=False,
            )

        else:
            raise NotImplementedError

        return embed

    async def process_type_one_modal(
        self,
        *,
        modal: "TypeOneModal",
        notify: NotesNotify | None,
        notify_type: NotesNotifyType,
        check_interval: int,
    ) -> DefaultEmbed:
        enabled = bool(int(modal.enabled.value))
        threshold = int(modal.threshold.value)
        notify_interval = int(modal.notify_interval.value)
        max_notif_count = int(modal.max_notif_count.value)

        if notify is None:
            await NotesNotify.create(
                type=notify_type,
                account=self._account,
                threshold=threshold,
                check_interval=check_interval,
                max_notif_count=max_notif_count,
                notify_interval=notify_interval,
                enabled=enabled,
            )
        else:
            notify.threshold = threshold
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.enabled = enabled
            await notify.save()

        return await self._get_reminder_embed()

    async def process_type_two_modal(
        self,
        *,
        modal: "TypeTwoModal",
        notify: NotesNotify | None,
        notify_type: NotesNotifyType,
        check_interval: int,
    ) -> DefaultEmbed:
        enabled = bool(int(modal.enabled.value))
        notify_interval = int(modal.notify_interval.value)
        max_notif_count = int(modal.max_notif_count.value)

        if notify is None:
            await NotesNotify.create(
                type=notify_type,
                account=self._account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
            )
        else:
            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            await notify.save()

        return await self._get_reminder_embed()

    async def process_type_three_modal(
        self,
        *,
        modal: "TypeThreeModal",
        notify: NotesNotify | None,
        notify_type: NotesNotifyType,
        check_interval: int,
    ) -> DefaultEmbed:
        enabled = bool(int(modal.enabled.value))
        notify_interval = int(modal.notify_interval.value)
        max_notif_count = int(modal.max_notif_count.value)
        notify_time = int(modal.notify_time.value)

        if notify is None:
            await NotesNotify.create(
                type=notify_type,
                account=self._account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
                notify_time=notify_time,
            )
        else:
            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.notify_time = notify_time
            await notify.save()

        return await self._get_reminder_embed()

    async def process_type_four_modal(
        self,
        *,
        modal: "TypeFourModal",
        notify: NotesNotify | None,
        notify_type: NotesNotifyType,
        check_interval: int,
    ) -> DefaultEmbed:
        enabled = bool(int(modal.enabled.value))
        notify_interval = int(modal.notify_interval.value)
        max_notif_count = int(modal.max_notif_count.value)
        notify_time = int(modal.notify_time.value)
        notify_weekday = int(modal.notify_weekday.value)

        if notify is None:
            await NotesNotify.create(
                type=notify_type,
                account=self._account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
                notify_time=notify_time,
                notify_weekday=notify_weekday,
            )
        else:
            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.notify_time = notify_time
            notify.notify_weekday = notify_weekday
            await notify.save()

        return await self._get_reminder_embed()


class ReminderButton(Button[NotesView]):
    def __init__(self) -> None:
        super().__init__(
            style=ButtonStyle.blurple,
            emoji=BELL_OUTLINE,
            label=LocaleStr("Reminder Settings", key="reminder_button.label"),
        )

    async def callback(self, i: "INTERACTION") -> None:
        go_back_button = GoBackButton(
            self.view.children,
            self.view.get_embeds(i.message),
            self.view.get_attachments(i.message),
        )
        self.view.clear_items()
        self.view.add_item(go_back_button)

        if self.view._account.game is Game.GENSHIN:
            from .buttons import (  # noqa: PLC0415
                DailyReminder,
                ExpeditionReminder,
                PTReminder,
                RealmCurrencyReminder,
                ResinReminder,
                WeekBossReminder,
            )

            self.view.add_item(ResinReminder(row=0))
            self.view.add_item(RealmCurrencyReminder(row=0))
            self.view.add_item(PTReminder(row=1))
            self.view.add_item(ExpeditionReminder(row=1))
            self.view.add_item(DailyReminder(row=2))
            self.view.add_item(WeekBossReminder(row=2))
        elif self.view._account.game is Game.STARRAIL:
            from .buttons import (  # noqa: PLC0415
                DailyReminder,
                ExpeditionReminder,
                ReservedTBPReminder,
                TBPReminder,
                WeekBossReminder,
            )

            self.view.add_item(TBPReminder(row=0))
            self.view.add_item(ReservedTBPReminder(row=0))
            self.view.add_item(ExpeditionReminder(row=1))
            self.view.add_item(DailyReminder(row=1))
            self.view.add_item(WeekBossReminder(row=2))
        else:
            raise NotImplementedError

        embed = await self.view._get_reminder_embed()
        await i.response.edit_message(embed=embed, view=self.view, attachments=[])
