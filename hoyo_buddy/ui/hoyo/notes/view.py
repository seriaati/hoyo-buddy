from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, TypeAlias

import genshin
from discord import File, Member, User

from hoyo_buddy.constants import AVAILABLE_OPEN_GAMES, get_open_game_url
from hoyo_buddy.db import draw_locale, get_dyk
from hoyo_buddy.draw.main_funcs import draw_gi_notes_card, draw_hsr_notes_card, draw_zzz_notes_card
from hoyo_buddy.embeds import DefaultEmbed
from hoyo_buddy.emojis import (
    BATTERY_CHARGE_EMOJI,
    PT_EMOJI,
    REALM_CURRENCY,
    RESIN,
    TRAILBLAZE_POWER,
    get_game_emoji,
)
from hoyo_buddy.enums import Game, Locale
from hoyo_buddy.exceptions import FeatureNotImplementedError
from hoyo_buddy.l10n import LocaleStr
from hoyo_buddy.models import DrawInput
from hoyo_buddy.ui import Button, Select, SelectOption, View

if TYPE_CHECKING:
    import io

    from hoyo_buddy.db import HoyoAccount
    from hoyo_buddy.types import Interaction

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

    async def get_reminder_embed(self) -> DefaultEmbed:
        embed = DefaultEmbed(self.locale, title=LocaleStr(key="reminder_settings_title"))
        embed.add_acc_info(self.account)
        embed.set_image(url="attachment://notes.png")
        return embed

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

        return embed.set_image(url="attachment://notes.png").add_acc_info(self.account)

    async def start(self, i: Interaction, *, acc_select: AccountSwitcher | None = None) -> None:
        self._add_items()

        notes = await self._get_notes()
        embed = self._get_notes_embed(notes)

        if isinstance(notes, NotesWithCard):
            draw_input = DrawInput(
                dark_mode=self.dark_mode,
                locale=draw_locale(self.locale, self.account),
                session=i.client.session,
                filename="notes.png",
                executor=i.client.executor,
                loop=i.client.loop,
            )
            self.bytes_obj = await self._draw_notes_card(notes, draw_input)
            self.bytes_obj.seek(0)
            file_ = File(self.bytes_obj, filename="notes.png")
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
