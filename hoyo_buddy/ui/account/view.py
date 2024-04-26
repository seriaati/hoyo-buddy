from typing import TYPE_CHECKING, Any

import genshin

from ...bot.translator import LocaleStr, Translator
from ...db.models import HoyoAccount, User
from ...embeds import DefaultEmbed
from ...emojis import get_game_emoji
from ...enums import LoginPlatform
from ...exceptions import NoGameAccountsError, TryOtherMethodError
from ...models import LoginNotifPayload
from .. import SelectOption
from ..components import Button, GoBackButton, View
from .add_acc_handler import GEETEST_SERVERS
from .items.acc_select import AccountSelect
from .items.acc_settings import AccountPublicToggle, AutoCheckinToggle, AutoRedeemToggle
from .items.add_acc_btn import AddAccountButton
from .items.add_acc_select import AddAccountSelect
from .items.del_acc_btn import DeleteAccountButton
from .items.edit_nickname_btn import EditNicknameButton
from .items.enter_email_pswd import EnterEmailVerificationCode

if TYPE_CHECKING:
    from collections.abc import Sequence

    import discord

    from ...bot.bot import INTERACTION


class AccountManager(View):
    def __init__(
        self,
        *,
        author: "discord.User | discord.Member | None",
        locale: "discord.Locale",
        translator: Translator,
        user: User,
        accounts: "Sequence[HoyoAccount]",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        self.locale = locale
        self.accounts = accounts
        self.selected_account: HoyoAccount | None = None

    @property
    def _acc_embed(self) -> DefaultEmbed:
        account = self.selected_account

        if account is None:
            embed = DefaultEmbed(
                self.locale,
                self.translator,
                title=LocaleStr("Account Manager", key="account_manager_title"),
                description=LocaleStr(
                    "You don't have any accounts yet.",
                    key="account_manager_no_accounts_description",
                ),
            )
            return embed

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=str(account),
        )
        embed.add_field(
            name=LocaleStr("Game", key="account_game"),
            value=LocaleStr(account.game.value, warn_no_key=False),
        )
        if account.nickname:
            embed.add_field(
                name=LocaleStr("Username", key="account_username"),
                value=account.username,
            )
        embed.set_footer(
            text=LocaleStr(
                "Selected account will be the default one used for all commands",
                key="account_manager_footer",
            )
        )
        return embed

    def _add_items(self) -> None:
        if self.accounts:
            self.selected_account = (
                next((a for a in self.accounts if a.current), None) or self.accounts[0]
            )
            self.add_item(AccountSelect(self._get_account_options()))
            self.add_item(AddAccountButton())
            self.add_item(EditNicknameButton())
            self.add_item(DeleteAccountButton())
            self.add_item(AutoRedeemToggle(self.selected_account.auto_redeem))
            self.add_item(AutoCheckinToggle(self.selected_account.daily_checkin))
            self.add_item(AccountPublicToggle(self.selected_account.public))
        else:
            self.add_item(AddAccountButton())

    def _get_account_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in self.accounts
        ]

    async def start(self, i: "INTERACTION") -> None:
        self._add_items()
        embed = self._acc_embed
        await i.response.defer(ephemeral=True)
        self.message = await i.edit_original_response(embed=embed, view=self)

    async def refresh(self, i: "INTERACTION", *, soft: bool) -> Any:
        if not soft:
            accounts = await HoyoAccount.filter(user=self.user).all()
            view = AccountManager(
                author=self.author,
                locale=self.locale,
                translator=self.translator,
                user=self.user,
                accounts=accounts,
            )
            await view.start(i)
        else:
            assert self.selected_account is not None
            auto_redeem_toggle: AutoRedeemToggle = self.get_item("auto_redeem_toggle")
            auto_redeem_toggle.current_toggle = self.selected_account.auto_redeem
            auto_redeem_toggle.update_style()

            auto_checkin_toggle: AutoCheckinToggle = self.get_item("auto_checkin_toggle")
            auto_checkin_toggle.current_toggle = self.selected_account.daily_checkin
            auto_checkin_toggle.update_style()

            acc_public_toggle: AccountPublicToggle = self.get_item("public_account_toggle")
            acc_public_toggle.current_toggle = self.selected_account.public
            acc_public_toggle.update_style()

            await self.absolute_edit(i, embed=self._acc_embed, view=self)

    async def finish_cookie_setup(
        self, cookies: dict[str, Any], *, platform: LoginPlatform, interaction: "INTERACTION"
    ) -> None:
        if platform is LoginPlatform.HOYOLAB and ("stoken" in cookies or "stoken_v2" in cookies):
            # Get ltoken_v2 and cookie_token_v2
            cookie = await genshin.fetch_cookie_with_stoken_v2(cookies, token_types=[2, 4])
            cookies.update(cookie)

        client = genshin.Client(
            cookies,
            region=genshin.Region.OVERSEAS
            if platform is LoginPlatform.HOYOLAB
            else genshin.Region.CHINESE,
        )

        # Update the view to let user select the accounts to add
        try:
            accounts = await client.get_game_accounts()
        except genshin.errors.InvalidCookies as e:
            raise TryOtherMethodError from e

        if not accounts:
            raise NoGameAccountsError(platform)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr("🎉 Welcome to Hoyo Buddy!", key="select_account.embed.title"),
            description=LocaleStr(
                "Select the accounts you want to add.",
                key="select_account.embed.description",
            ),
        )

        self.clear_items()
        self.add_item(
            AddAccountSelect(
                self.locale,
                self.translator,
                accounts=accounts,
                cookies="; ".join(f"{k}={v}" for k, v in cookies.items()),
            )
        )

        await interaction.edit_original_response(embed=embed, view=self)

    async def prompt_user_to_solve_geetest(self, i: "INTERACTION", *, for_code: bool) -> None:
        """Prompt the user to solve CAPTCHA before sending the verification code or logging in.

        Args:
            i: The interaction object.
            for_code: Whether the CAPTCHA is triggered for sending the verification code.
        """
        assert i.channel and i.message

        # geetest info is trasmitted through user.temp_data
        payload = LoginNotifPayload(
            user_id=i.user.id,
            guild_id=i.guild.id if i.guild else None,
            channel_id=i.channel.id,
            message_id=i.message.id,
            locale=self.locale.value,
        )
        url = f"{GEETEST_SERVERS[i.client.env]}/captcha?{payload.to_query_string()}"

        go_back_button = GoBackButton(self.children, self.get_embeds(i.message))
        self.clear_items()
        self.add_item(
            Button(
                label=LocaleStr("Complete CAPTCHA", key="complete_captcha_button_label"), url=url
            )
        )
        self.add_item(go_back_button)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(
                "😥 Need to Solve CAPTCHA Before Sending the Verification Code",
                key="email-geetest.embed.title",
            )
            if for_code
            else LocaleStr("😅 Need to solve CAPTCHA before logging in", key="geetest.embed.title"),
            description=LocaleStr(
                "Click on the button below to complete CAPTCHA.\n",
                key="captcha.embed.description",
            ),
        )
        await i.edit_original_response(embed=embed, view=self)

    async def prompt_user_to_verify_email(self, i: "INTERACTION") -> None:
        go_back_button = GoBackButton(self.children, self.get_embeds(i.message))
        self.clear_items()
        self.add_item(EnterEmailVerificationCode())
        self.add_item(go_back_button)

        embed = DefaultEmbed(
            self.locale,
            self.translator,
            title=LocaleStr(
                "👍 Almost Done! Just Need to Verify Your E-Mail",
                key="email-verification.embed.title",
            ),
            description=LocaleStr(
                (
                    "1. Go to the inbox of the e-mail your entered and find the verification code sent from Hoyoverse.\n"
                    "2. Click the button below to enter the code received.\n"
                ),
                key="email-verification.embed.description",
            ),
        )

        await i.edit_original_response(embed=embed, view=self)
