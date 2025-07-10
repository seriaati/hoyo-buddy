from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, TypeAlias

import genshin
from discord import ButtonStyle, File, Member, User

from hoyo_buddy.constants import AVAILABLE_OPEN_GAMES, get_open_game_url
from hoyo_buddy.db import NotesNotify, draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import draw_gi_notes_card, draw_hsr_notes_card, draw_zzz_notes_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import (
    BATTERY_CHARGE_EMOJI,
    BELL_OUTLINE,
    PT_EMOJI,
    REALM_CURRENCY,
    RESIN,
    TOGGLE_EMOJIS,
    TRAILBLAZE_POWER,
    get_game_emoji,
)
from hoyo_buddy.enums import Game, Locale, NotesNotifyType
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.l10n import LocaleStr, WeekdayStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.ui import Button, GoBackButton, Select, SelectOption, View

if TYPE_CHECKING:
    import io

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Interaction
    from hoyo_buddy.ui.hoyo.notes.modals.type_five import TypeFiveModal

    from .modals.type_four import TypeFourModal
    from .modals.type_one import TypeOneModal
    from .modals.type_three import TypeThreeModal
    from .modals.type_two import TypeTwoModal

NotesWithCard: TypeAlias = (
    genshin.models.Notes | genshin.models.StarRailNote | genshin.models.ZZZNotes
)


class NotesView(View):
    def __init__(
        self,
        account: HoyoAccount,
        accounts: list[HoyoAccount] | None = None,
        *,
        dark_mode: bool,
        author: User | Member | None,
        locale: Locale,
    ) -> None:
        super().__init__(author=author, locale=locale)
        self.account = account
        self.dark_mode = dark_mode
        self.accounts = accounts
        self.bytes_obj: io.BytesIO | None = None

    def _add_items(self) -> None:
        if self.accounts is not None:
            self.add_item(AccountSwitcher(self.accounts, self.account))
        self.add_items(self.get_open_game_buttons(self.account, row=1))
        self.add_item(ReminderButton(row=4))

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

    async def _get_gi_embed(self, embed: DefaultEmbed) -> DefaultEmbed:
        resin_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.RESIN
        )
        embed.add_field(
            name=LocaleStr(key="resin_reminder_button.label"),
            value=self._get_type1_value(resin_notify),
            inline=False,
        )

        realm_currency_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.REALM_CURRENCY
        )
        embed.add_field(
            name=LocaleStr(key="realm_curr_button.label"),
            value=self._get_type1_value(realm_currency_notify),
            inline=False,
        )

        pt_notify = await NotesNotify.get_or_none(account=self.account, type=NotesNotifyType.PT)
        embed.add_field(
            name=LocaleStr(key="pt_button.label"),
            value=self._get_type2_value(pt_notify),
            inline=False,
        )

        expedition_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.GI_EXPED
        )
        embed.add_field(
            name=LocaleStr(key="exped_button.label"),
            value=self._get_type2_value(expedition_notify),
            inline=False,
        )

        daily_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.GI_DAILY
        )
        embed.add_field(
            name=LocaleStr(key="daily_button.label"),
            value=self._get_type3_value(daily_notify),
            inline=False,
        )

        resin_discount_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.RESIN_DISCOUNT
        )
        embed.add_field(
            name=LocaleStr(key="week_boss_button.label"),
            value=self._get_type4_value(resin_discount_notify),
            inline=False,
        )

        return embed

    async def _get_hsr_embed(self, embed: DefaultEmbed) -> DefaultEmbed:
        tbp_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.TB_POWER
        )
        embed.add_field(
            name=LocaleStr(key="hsr_note_stamina", mi18n_game=Game.STARRAIL),
            value=self._get_type1_value(tbp_notify),
            inline=False,
        )

        reserved_tbp_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.RESERVED_TB_POWER
        )
        embed.add_field(
            name=LocaleStr(key="hsr_note_reserve_stamina", mi18n_game=Game.STARRAIL),
            value=self._get_type1_value(reserved_tbp_notify),
            inline=False,
        )

        expedition_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.HSR_EXPED
        )
        embed.add_field(
            name=LocaleStr(key="exped_button.label"),
            value=self._get_type2_value(expedition_notify),
            inline=False,
        )

        daily_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.HSR_DAILY
        )
        embed.add_field(
            name=LocaleStr(key="daily_button.label"),
            value=self._get_type3_value(daily_notify),
            inline=False,
        )

        echo_of_war_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.ECHO_OF_WAR
        )
        embed.add_field(
            name=LocaleStr(key="week_boss_button.label"),
            value=self._get_type4_value(echo_of_war_notify),
            inline=False,
        )

        planar_fissure_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.PLANAR_FISSURE
        )
        embed.add_field(
            name=LocaleStr(key="planar_fissure_label"),
            value=self._get_type5_value(planar_fissure_notify),
            inline=False,
        )

        return embed

    async def _get_zzz_embed(self, embed: DefaultEmbed) -> DefaultEmbed:
        battery_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.BATTERY
        )
        embed.add_field(
            name=LocaleStr(key="battery_num", mi18n_game=Game.ZZZ),
            value=self._get_type1_value(battery_notify),
            inline=False,
        )

        daily_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.ZZZ_DAILY
        )
        embed.add_field(
            name=LocaleStr(key="daily_button.label"),
            value=self._get_type3_value(daily_notify),
            inline=False,
        )

        scratch_card_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.SCRATCH_CARD
        )
        embed.add_field(
            name=LocaleStr(key="card", mi18n_game=Game.ZZZ),
            value=self._get_type3_value(scratch_card_notify),
            inline=False,
        )

        video_store_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.VIDEO_STORE
        )
        embed.add_field(
            name=LocaleStr(key="vhs_sale", mi18n_game=Game.ZZZ),
            value=self._get_type2_value(video_store_notify),
            inline=False,
        )

        ridu_points_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.RIDU_POINTS
        )
        embed.add_field(
            name=LocaleStr(key="weekly_task_point", mi18n_game=Game.ZZZ),
            value=self._get_type4_value(ridu_points_notify),
            inline=False,
        )

        bounty_comm_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.ZZZ_BOUNTY
        )
        embed.add_field(
            name=LocaleStr(key="bounty_commission", mi18n_game=Game.ZZZ),
            value=self._get_type4_value(bounty_comm_notify),
            inline=False,
        )

        return embed

    async def _get_honkai_embed(self, embed: DefaultEmbed) -> DefaultEmbed:
        stamina_notify = await NotesNotify.get_or_none(
            account=self.account, type=NotesNotifyType.STAMINA
        )
        embed.add_field(
            name=LocaleStr(key="notes.stamina_label"),
            value=self._get_type1_value(stamina_notify),
            inline=False,
        )

        return embed

    async def get_reminder_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, title=LocaleStr(key="reminder_settings_title"))
        embed.add_acc_info(self.account)
        embed.set_image(url="attachment://notes.webp")

        if self.account.game is Game.GENSHIN:
            return await self._get_gi_embed(embed)
        if self.account.game is Game.STARRAIL:
            return await self._get_hsr_embed(embed)
        if self.account.game is Game.ZZZ:
            return await self._get_zzz_embed(embed)
        if self.account.game is Game.HONKAI:
            return await self._get_honkai_embed(embed)

        raise FeatureNotImplementedError(platform=self.account.platform, game=self.account.game)

    async def _reset_notify(self, notify: NotesNotify) -> None:
        notify.est_time = None
        notify.last_notif_time = None
        notify.last_check_time = None
        notify.current_notif_count = 0
        await notify.save(
            update_fields=("est_time", "last_notif_time", "last_check_time", "current_notif_count")
        )

    async def process_type_one_modal(
        self,
        *,
        modal: TypeOneModal,
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
                account=self.account,
                threshold=threshold,
                check_interval=check_interval,
                max_notif_count=max_notif_count,
                notify_interval=notify_interval,
                enabled=enabled,
            )
        else:
            await self._reset_notify(notify)

            notify.threshold = threshold
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.enabled = enabled
            await notify.save(
                update_fields=("threshold", "notify_interval", "max_notif_count", "enabled")
            )

        return await self.get_reminder_embed()

    async def process_type_two_modal(
        self,
        *,
        modal: TypeTwoModal,
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
                account=self.account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
            )
        else:
            await self._reset_notify(notify)

            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            await notify.save(update_fields=("enabled", "notify_interval", "max_notif_count"))

        return await self.get_reminder_embed()

    async def process_type_three_modal(
        self,
        *,
        modal: TypeThreeModal,
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
                account=self.account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
                notify_time=notify_time,
            )
        else:
            await self._reset_notify(notify)

            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.notify_time = notify_time
            await notify.save(
                update_fields=("enabled", "notify_interval", "max_notif_count", "notify_time")
            )

        return await self.get_reminder_embed()

    async def process_type_four_modal(
        self,
        *,
        modal: TypeFourModal,
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
                account=self.account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
                notify_time=notify_time,
                notify_weekday=notify_weekday,
            )
        else:
            await self._reset_notify(notify)

            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.notify_time = notify_time
            notify.notify_weekday = notify_weekday
            await notify.save(
                update_fields=(
                    "enabled",
                    "notify_interval",
                    "max_notif_count",
                    "notify_time",
                    "notify_weekday",
                )
            )

        return await self.get_reminder_embed()

    async def process_type_five_modal(
        self,
        *,
        modal: TypeFiveModal,
        notify: NotesNotify | None,
        notify_type: NotesNotifyType,
        check_interval: int,
    ) -> DefaultEmbed:
        enabled = bool(int(modal.enabled.value))
        notify_interval = int(modal.notify_interval.value)
        max_notif_count = int(modal.max_notif_count.value)
        hours_before = int(modal.hours_before.value)

        if notify is None:
            await NotesNotify.create(
                type=notify_type,
                account=self.account,
                check_interval=check_interval,
                notify_interval=notify_interval,
                max_notif_count=max_notif_count,
                enabled=enabled,
                hours_before=hours_before,
            )
        else:
            await self._reset_notify(notify)

            notify.enabled = enabled
            notify.notify_interval = notify_interval
            notify.max_notif_count = max_notif_count
            notify.hours_before = hours_before
            await notify.save(
                update_fields=("enabled", "notify_interval", "max_notif_count", "hours_before")
            )

        return await self.get_reminder_embed()

    async def _get_notes(
        self,
    ) -> (
        genshin.models.Notes
        | genshin.models.StarRailNote
        | genshin.models.ZZZNotes
        | genshin.models.HonkaiNotes
    ):
        if self.account.game is Game.GENSHIN:
            return await self.account.client.get_genshin_notes()
        if self.account.game is Game.ZZZ:
            return await self.account.client.get_zzz_notes()
        if self.account.game is Game.STARRAIL:
            return await self.account.client.get_starrail_notes()
        if self.account.game is Game.HONKAI:
            return await self.account.client.get_honkai_notes()

        raise FeatureNotImplementedError(platform=self.account.platform, game=self.account.game)

    async def _draw_notes_card(self, notes: NotesWithCard, draw_input: DrawInput) -> io.BytesIO:
        if isinstance(notes, genshin.models.Notes):
            return await draw_gi_notes_card(draw_input, notes)
        if isinstance(notes, genshin.models.ZZZNotes):
            return await draw_zzz_notes_card(draw_input, notes)
        return await draw_hsr_notes_card(draw_input, notes)

    def _get_notes_embed(
        self,
        notes: genshin.models.Notes
        | genshin.models.StarRailNote
        | genshin.models.ZZZNotes
        | genshin.models.HonkaiNotes,
    ) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale)

        if isinstance(notes, genshin.models.Notes):
            if notes.remaining_resin_recovery_time.total_seconds() > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=RESIN,
                        in_time=notes.remaining_resin_recovery_time,
                    )
                )
            if notes.remaining_realm_currency_recovery_time.total_seconds() > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=REALM_CURRENCY,
                        in_time=notes.remaining_realm_currency_recovery_time,
                    )
                )
            if (
                notes.remaining_transformer_recovery_time is not None
                and notes.remaining_transformer_recovery_time.total_seconds() > 0
            ):
                embed.add_description(
                    LocaleStr(
                        key="notes_available",
                        emoji=PT_EMOJI,
                        in_time=notes.remaining_transformer_recovery_time,
                    )
                )
        elif isinstance(notes, genshin.models.ZZZNotes):
            if (recover := notes.battery_charge.seconds_till_full) > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=BATTERY_CHARGE_EMOJI,
                        in_time=datetime.timedelta(seconds=recover),
                    )
                )
        elif isinstance(notes, genshin.models.HonkaiNotes):
            embed.add_description(
                LocaleStr(
                    key="notes.stamina",
                    time=datetime.timedelta(seconds=notes.stamina_recover_time),
                    cur=notes.current_stamina,
                    max=notes.max_stamina,
                )
            )
            embed.add_description(
                LocaleStr(key="notes.train_score", cur=notes.current_train_score, max=600)
            )

            embed.add_field(
                name=LocaleStr(key="notes.superstring_dimension"),
                value=LocaleStr(
                    key="notes.superstring_dimension_value",
                    score=notes.ultra_endless.challenge_score,
                ),
                inline=False,
            )
            if notes.battle_field is not None:
                embed.add_field(
                    name=LocaleStr(key="notes.memorial_arena"),
                    value=LocaleStr(
                        key="notes.memorial_arena_value",
                        rewards_cur=notes.battle_field.current_reward,
                        rewards_max=notes.battle_field.max_reward,
                        sss_cur=notes.battle_field.current_sss_reward,
                        sss_max=notes.battle_field.max_sss_reward,
                    ),
                    inline=False,
                )
            embed.add_field(
                name=LocaleStr(key="notes.elysian_realm"),
                value=LocaleStr(
                    key="notes.elysian_realm_value",
                    cur=notes.god_war.current_reward,
                    max=notes.god_war.max_reward,
                ),
                inline=False,
            )
        else:  # StarRailNotes
            if notes.stamina_recover_time.total_seconds() > 0:
                embed.add_description(
                    LocaleStr(
                        key="notes.item_full_in_time",
                        emoji=TRAILBLAZE_POWER,
                        in_time=notes.stamina_recover_time,
                    )
                )
            if notes.have_bonus_synchronicity_points:
                embed.add_description(
                    LocaleStr(
                        key="notes.bonus_sync_points",
                        cur=notes.current_bonus_synchronicity_points,
                        max=notes.max_bonus_synchronicity_points,
                    )
                )

        return embed.set_image(url="attachment://notes.webp").add_acc_info(self.account)

    async def start(self, i: Interaction, *, acc_select: AccountSwitcher | None = None) -> None:
        self._add_items()

        notes = await self._get_notes()
        embed = self._get_notes_embed(notes)

        if isinstance(notes, NotesWithCard):
            draw_input = DrawInput(
                dark_mode=self.dark_mode,
                locale=draw_locale(self.locale, self.account),
                session=i.client.session,
                filename="notes.webp",
                executor=i.client.executor,
                loop=i.client.loop,
            )
            self.bytes_obj = await self._draw_notes_card(notes, draw_input)
            self.bytes_obj.seek(0)
            file_ = File(self.bytes_obj, filename="notes.webp")
        else:
            file_ = None

        if acc_select is not None:
            await acc_select.unset_loading_state(
                i, embed=embed, attachments=[file_] if file_ is not None else []
            )
        else:
            kwargs = {"embed": embed, "view": self, "content": await get_dyk(i)}
            if file_ is not None:
                kwargs["file"] = file_
            await i.followup.send(**kwargs)

        self.message = await i.original_response()

    @staticmethod
    def get_open_game_buttons(account: HoyoAccount, *, row: int = 0) -> list[Button]:
        result: list[Button] = []

        platform, game = account.platform, account.game
        available_games = AVAILABLE_OPEN_GAMES.get(platform)

        if available_games is not None:
            buttons = available_games.get(game)
            if buttons is not None:
                for label_enum, region, game in buttons:
                    url = get_open_game_url(region=region, game=game)
                    result.append(
                        Button(label=LocaleStr(key=label_enum.value), url=str(url), row=row)
                    )

        return result


class ReminderButton(Button[NotesView]):
    def __init__(self, *, row: int) -> None:
        super().__init__(
            style=ButtonStyle.blurple,
            emoji=BELL_OUTLINE,
            label=LocaleStr(key="reminder_button.label"),
            row=row,
        )

    async def callback(self, i: Interaction) -> None:
        go_back_button = GoBackButton(
            self.view.children, self.view.get_embeds(i.message), self.view.bytes_obj
        )
        self.view.clear_items()
        self.view.add_item(go_back_button)

        if self.view.account.game is Game.GENSHIN:
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
        elif self.view.account.game is Game.STARRAIL:
            from .buttons import (  # noqa: PLC0415
                DailyReminder,
                ExpeditionReminder,
                PlanarFissureReminder,
                ReservedTBPReminder,
                TBPReminder,
                WeekBossReminder,
            )

            self.view.add_item(TBPReminder(row=0))
            self.view.add_item(ReservedTBPReminder(row=0))
            self.view.add_item(ExpeditionReminder(row=1))
            self.view.add_item(DailyReminder(row=1))
            self.view.add_item(WeekBossReminder(row=2))
            self.view.add_item(PlanarFissureReminder(row=2))
        elif self.view.account.game is Game.ZZZ:
            from .buttons import (  # noqa: PLC0415
                BatteryReminder,
                BountyCommissionReminder,
                DailyReminder,
                RiduPointsReminder,
                ScratchCardReminder,
                VideoStoreReminder,
            )

            self.view.add_item(BatteryReminder(row=0))
            self.view.add_item(DailyReminder(row=0))
            self.view.add_item(ScratchCardReminder(row=1))
            self.view.add_item(VideoStoreReminder(row=1))
            self.view.add_item(RiduPointsReminder(row=2))
            self.view.add_item(BountyCommissionReminder(row=2))
        elif self.view.account.game is Game.HONKAI:
            from .buttons import DailyReminder, StaminaReminder  # noqa: PLC0415

            self.view.add_item(StaminaReminder(row=0))
            self.view.add_item(DailyReminder(row=0))
        else:
            raise FeatureNotImplementedError(
                platform=self.view.account.platform, game=self.view.account.game
            )

        embed = await self.view.get_reminder_embed()
        await i.response.edit_message(embed=embed, view=self.view, attachments=[])


class AccountSwitcher(Select[NotesView]):
    def __init__(self, accounts: list[HoyoAccount], account: HoyoAccount) -> None:
        super().__init__(
            placeholder=LocaleStr(key="account_select_placeholder"),
            options=[
                SelectOption(
                    label=acc.blurred_display,
                    value=f"{acc.uid}_{acc.game}",
                    emoji=get_game_emoji(acc.game),
                    default=acc == account,
                )
                for acc in accounts
            ],
        )

    async def callback(self, i: Interaction) -> None:
        assert self.view.accounts is not None

        await self.set_loading_state(i)
        uid, game = self.values[0].split("_")
        account = next(
            (acc for acc in self.view.accounts if acc.uid == int(uid) and acc.game == game), None
        )
        if account is None:
            msg = f"Account not found for {uid} in {game}"
            raise ValueError(msg)

        self.view.account = account
        self.view.clear_items()
        await self.view.start(i, acc_select=self)
