from __future__ import annotations

from typing import TYPE_CHECKING

from discord import ButtonStyle, Locale, Member, User

from ...embeds import DefaultEmbed
from ...emojis import GIFT_OUTLINE
from ...l10n import LocaleStr
from ..components import Button, Modal, TextInput, ToggleButton, View

if TYPE_CHECKING:
    from hoyo_buddy.l10n import Translator

    from ...db.models import HoyoAccount
    from ...types import Interaction


class GiftCodeModal(Modal):
    code_1 = TextInput(
        label=LocaleStr(key="gift_code_modal.code_input.label", num=1),
        placeholder="https://hsr.hoyoverse.com/gift?code=...",
    )
    code_2 = TextInput(
        label=LocaleStr(key="gift_code_modal.code_input.label", num=2),
        placeholder="https://zzz.hoyoverse.com/gift?code=...",
        required=False,
    )
    code_3 = TextInput(
        label=LocaleStr(key="gift_code_modal.code_input.label", num=3),
        placeholder="GENSHINGIFT",
        required=False,
    )
    code_4 = TextInput(
        label=LocaleStr(key="gift_code_modal.code_input.label", num=4),
        placeholder="HSR2024",
        required=False,
    )
    code_5 = TextInput(
        label=LocaleStr(key="gift_code_modal.code_input.label", num=5),
        placeholder="HOYOBUDDY",
        required=False,
    )


class RedeemUI(View):
    def __init__(
        self,
        account: HoyoAccount,
        *,
        author: User | Member | None,
        locale: Locale,
        translator: Translator,
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.account = account
        self.account.client.set_lang(locale)

        self._add_items()

    @property
    def start_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="redeem_codes_button.label"),
            description=LocaleStr(key="redeem_command_embed.description"),
        ).add_acc_info(self.account)

    @property
    def cooldown_embed(self) -> DefaultEmbed:
        return DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(key="redeem_cooldown_embed.title"),
            description=LocaleStr(key="redeem_cooldown_embed.description"),
        )

    def _add_items(self) -> None:
        self.add_item(RedeemCodesButton())
        self.add_item(AutoRedeemToggle(self.account.auto_redeem))


class RedeemCodesButton(Button[RedeemUI]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr(key="redeem_codes_button.label"),
            emoji=GIFT_OUTLINE,
            style=ButtonStyle.blurple,
        )

    async def callback(self, i: Interaction) -> None:
        modal = GiftCodeModal(title=LocaleStr(key="gift_code_modal.title"))
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)

        await modal.wait()
        if modal.incomplete:
            return

        await self.set_loading_state(i, embed=self.view.cooldown_embed)
        codes = (
            modal.code_1.value,
            modal.code_2.value,
            modal.code_3.value,
            modal.code_4.value,
            modal.code_5.value,
        )

        # Extract codes from urls
        codes = [code.split("code=")[1] if "code=" in code else code for code in codes]
        embed = await self.view.account.client.redeem_codes(
            codes, locale=self.view.locale, translator=self.view.translator, inline=False
        )
        await self.unset_loading_state(i, embed=embed)


class AutoRedeemToggle(ToggleButton[RedeemUI]):
    def __init__(self, current_toggle: bool) -> None:
        super().__init__(current_toggle, LocaleStr(key="auto_redeem_toggle.label"), row=0)

    async def callback(self, i: Interaction) -> None:
        await super().callback(i)
        self.view.account.auto_redeem = self.current_toggle
        await self.view.account.save(update_fields=("auto_redeem",))
