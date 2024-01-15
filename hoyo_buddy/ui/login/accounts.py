from typing import TYPE_CHECKING, Any

import discord
import genshin
from tortoise.exceptions import IntegrityError

from ...bot import INTERACTION, emojis
from ...bot.translator import LocaleStr, Translator
from ...db.enums import GAME_CONVERTER
from ...db.models import AccountNotifSettings, HoyoAccount, User
from ...embeds import DefaultEmbed, ErrorEmbed
from ...hoyo.client import GenshinClient
from .. import Button, GoBackButton, Modal, Select, SelectOption, TextInput, View

if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

GEETEST_SERVER_URL = {
    "prod": "https://geetest-server.seriaati.xyz",
    "test": "http://geetest-server-test.seriaati.xyz",
    "dev": "http://localhost:5000",
}


class AccountManager(View):
    def __init__(
        self,
        *,
        author: discord.User | discord.Member,
        locale: discord.Locale,
        translator: Translator,
        user: User,
        accounts: "Sequence[HoyoAccount]",
    ) -> None:
        super().__init__(author=author, locale=locale, translator=translator)
        self.user = user
        self.locale = locale
        self.accounts = accounts
        self.selected_account: HoyoAccount | None = None

    async def init(self) -> None:
        if self.accounts:
            self.selected_account = self.accounts[0]
            self.add_item(AccountSelector(self.get_account_options()))
            self.add_item(AddAccount())
            self.add_item(EditNickname())
            self.add_item(DeleteAccount())
        else:
            self.add_item(AddAccount())

    def get_account_embed(self) -> DefaultEmbed:
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
            inline=False,
        )
        embed.add_field(
            name=LocaleStr("Server", key="account_server"),
            value=LocaleStr(account.server, warn_no_key=False),
            inline=False,
        )
        if account.nickname:
            embed.add_field(
                name=LocaleStr("Username", key="account_username"),
                value=account.username,
                inline=False,
            )
        return embed

    def get_account_options(self) -> list[SelectOption]:
        return [
            SelectOption(
                label=str(account),
                value=f"{account.uid}_{account.game.value}",
                emoji=emojis.get_game_emoji(account.game),
                default=account == self.selected_account,
            )
            for account in self.accounts
        ]

    async def refresh(self, i: INTERACTION, *, soft: bool) -> Any:
        if not soft:
            accounts = await HoyoAccount.filter(user=self.user).all()
            view = AccountManager(
                author=self.author,
                locale=self.locale,
                translator=self.translator,
                user=self.user,
                accounts=accounts,
            )
            await view.init()
            await self.absolute_edit(i, embed=view.get_account_embed(), view=view)
            view.message = await i.original_response()
        else:
            account_selector = self.get_item("account_selector")
            if isinstance(account_selector, Select):
                account_selector.options = self.get_account_options()
            await self.absolute_edit(i, embed=self.get_account_embed(), view=self)


class AccountSelector(Select["AccountManager"]):
    def __init__(self, options: list[SelectOption]) -> None:
        super().__init__(custom_id="account_selector", options=options)

    async def callback(self, i: INTERACTION) -> Any:
        uid, game = self.values[0].split("_")
        selected_account = discord.utils.get(self.view.accounts, uid=int(uid), game__value=game)
        if selected_account is None:
            msg = "Invalid account selected"
            raise ValueError(msg)

        self.view.selected_account = selected_account
        await self.view.refresh(i, soft=True)


class DeleteAccountContinue(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="delete_account_continue",
            label=LocaleStr("Continue", key="continue_button_label"),
            emoji=emojis.FORWARD,
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, i: INTERACTION) -> Any:
        await self.view.refresh(i, soft=False)


class DeleteAccount(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="delete_account",
            style=discord.ButtonStyle.danger,
            emoji=emojis.DELETE,
            label=LocaleStr("Delete selected account", key="delete_account_button_label"),
            row=2,
        )

    async def callback(self, i: INTERACTION) -> Any:
        account = self.view.selected_account
        if account is None:
            msg = "No account selected"
            raise ValueError(msg)
        await account.delete()

        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Account deleted", key="account_deleted_title"),
            description=LocaleStr(
                "{account} has been deleted.",
                key="account_deleted_description",
                account=str(account),
            ),
        )
        self.view.clear_items()
        self.view.add_item(DeleteAccountContinue())
        await i.response.edit_message(embed=embed, view=self.view)


class NicknameModal(Modal):
    nickname = TextInput(
        label=LocaleStr("Nickname", key="nickname_modal_label"),
        placeholder=LocaleStr("Main account, Asia account...", key="nickname_modal_placeholder"),
        required=False,
        style=discord.TextStyle.short,
        max_length=32,
    )

    def __init__(self, current_nickname: str | None = None) -> None:
        super().__init__(title=LocaleStr("Edit nickname", key="edit_nickname_modal_title"))
        self.nickname.default = current_nickname


class EditNickname(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="edit_nickname",
            emoji=emojis.EDIT,
            label=LocaleStr("Edit nickname", key="edit_nickname_button_label"),
        )

    async def callback(self, i: INTERACTION) -> Any:
        account = self.view.selected_account
        if account is None:
            msg = "No account selected"
            raise ValueError(msg)

        modal = NicknameModal(account.nickname)
        modal.translate(self.view.locale, self.view.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        account.nickname = modal.nickname.value
        await account.save()
        await self.view.refresh(i, soft=True)


class CookiesModal(Modal):
    cookies = TextInput(
        label="Cookies",
        placeholder=LocaleStr("Paste your cookies here...", key="cookies_modal_placeholder"),
        style=discord.TextStyle.paragraph,
    )


class DevToolCookiesModalV2(Modal):
    ltuid_v2 = TextInput(label="ltuid_v2")
    ltoken_v2 = TextInput(label="ltoken_v2")


class DevToolCookiesModal(Modal):
    ltuid = TextInput(label="ltuid")
    ltoken = TextInput(label="ltoken")


class SelectAccountsToAdd(Select["AccountManager"]):
    def __init__(
        self,
        locale: discord.Locale,
        translator: Translator,
        *,
        accounts: "Sequence[genshin.models.GenshinAccount]",
        cookies: str,
    ) -> None:
        self.accounts = accounts
        self.cookies = cookies
        self.translator = translator
        self.locale = locale
        options = list(self.get_account_options())

        super().__init__(
            custom_id="select_accounts_to_add",
            options=options,
            max_values=len(options),
            placeholder=LocaleStr(
                "Select the accounts you want to add...",
                key="select_accounts_to_add_placeholder",
            ),
        )

    def get_account_options(self) -> "Generator[SelectOption, None, None]":
        for account in self.accounts:
            if isinstance(account.game, genshin.Game):
                server_name = self.translator.translate(
                    LocaleStr(account.server_name, warn_no_key=False),
                    self.locale,
                )

                level_str = LocaleStr(
                    "Lv. {level}",
                    key="level_str",
                    level=account.level,
                )
                yield SelectOption(
                    label=f"[{account.uid}] {account.nickname}",
                    description=f"{level_str} | {server_name}",
                    value=f"{account.uid}_{account.game.value}",
                    emoji=emojis.get_game_emoji(account.game),
                )

    async def callback(self, i: INTERACTION) -> Any:
        for value in self.values:
            uid, game = value.split("_")
            account = discord.utils.get(self.accounts, uid=int(uid), game__value=game)
            if account is None:
                msg = "Invalid account selected"
                raise ValueError(msg)

            try:
                hoyo_account = await HoyoAccount.create(
                    uid=account.uid,
                    username=account.nickname,
                    game=GAME_CONVERTER[account.game],
                    cookies=self.cookies,
                    user=self.view.user,
                    server=account.server_name,
                )
            except IntegrityError:
                await HoyoAccount.filter(
                    uid=account.uid,
                    game=GAME_CONVERTER[account.game],
                    user=self.view.user,
                ).update(cookies=self.cookies, username=account.nickname)
            else:
                await AccountNotifSettings.create(account=hoyo_account)

        self.view.user.temp_data.pop("cookies", None)
        await self.view.user.save()
        await self.view.refresh(i, soft=False)


class EnterCookies(Button["AccountManager"]):
    def __init__(self, *, v2: bool, dev_tools: bool = False) -> None:
        if dev_tools:
            if v2:
                label = LocaleStr(
                    "I have ltuid_v2 and ltoken_v2",
                    key="devtools_v2_cookies_button_label",
                )
            else:
                label = LocaleStr("I have ltuid and ltoken", key="devtools_v1_cookies_button_label")
        else:
            label = LocaleStr("Enter Cookies", key="cookies_button_label")

        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            emoji=emojis.COOKIE,
        )
        self.v2 = v2
        self.dev_tools = dev_tools

    async def callback(self, i: INTERACTION) -> Any:
        modal = self.get_cookies_modal()
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        cookies = self.get_cookies(modal)
        if not cookies:
            return

        await self.set_loading_state(i)
        client = GenshinClient(cookies)
        client.set_lang(self.view.locale)

        try:
            game_accounts = await client.get_game_accounts()
        except genshin.InvalidCookies:
            await self.unset_loading_state(i)
            embed = self.get_invalid_cookies_embed(modal)
            await i.edit_original_response(embed=embed)
        else:
            go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
            self.view.clear_items()
            self.view.add_item(
                SelectAccountsToAdd(
                    self.view.locale,
                    self.view.translator,
                    accounts=game_accounts,
                    cookies=cookies,
                )
            )
            self.view.add_item(go_back_button)
            await i.edit_original_response(embed=None, view=self.view)

    def get_cookies_modal(self) -> DevToolCookiesModal | DevToolCookiesModalV2 | CookiesModal:
        if self.dev_tools:
            if self.v2:
                return DevToolCookiesModalV2(
                    title=LocaleStr("Enter Cookies", key="enter_cookies_modal_title")
                )
            return DevToolCookiesModal(
                title=LocaleStr("Enter Cookies", key="enter_cookies_modal_title")
            )
        return CookiesModal(title=LocaleStr("Enter Cookies", key="enter_cookies_modal_title"))

    @staticmethod
    def get_cookies(
        modal: DevToolCookiesModal | DevToolCookiesModalV2 | CookiesModal,
    ) -> str | None:
        if isinstance(modal, DevToolCookiesModal):
            if not all((modal.ltuid.value, modal.ltoken.value)):
                return None
            return f"ltuid={modal.ltuid.value.strip()}; ltoken={modal.ltoken.value.strip()}"

        if isinstance(modal, DevToolCookiesModalV2):
            if not all((modal.ltuid_v2.value, modal.ltoken_v2.value)):
                return None
            return f"ltuid_v2={modal.ltuid_v2.value.strip()}; ltoken_v2={modal.ltoken_v2.value.strip()}"

        if modal.cookies.value is None:
            return None
        return modal.cookies.value

    def get_invalid_cookies_embed(self, modal: Modal) -> ErrorEmbed:
        if isinstance(modal, CookiesModal):
            return ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Invalid cookies", key="invalid_cookies_title"),
                description=LocaleStr(
                    (
                        "It is likely that your account has the new security feature enabled.\n"
                        "Part of the cookies is encrypted and cannot be obtained by JavaScript.\n"
                        "Please try the other methods to add your accounts."
                    ),
                    key="invalid_cookies_description",
                ),
            )
        else:
            return ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Invalid cookies", key="invalid_cookies_title"),
                description=LocaleStr(
                    "Please check that you copied the values of ltuid and ltoken correctly",
                    key="invalid_ltuid_ltoken_description",
                ),
            )


class WithJavaScript(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(label=LocaleStr("With JavaScript", key="javascript_button_label"))

    async def callback(self, i: INTERACTION) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{emojis.INFO} Note: This method should work for all major browsers on desktop, but on mobile, it only works for **Chrome** and **Edge**.\n\n"
                    "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (for CN players)\n"
                    "2. Copy the code below\n"
                    "3. Click on the address bar and type `java`\n"
                    "4. Paste the code and press enter. Make sure there are **NO SPACES** between `java` and `script`\n"
                    "5. Select all and copy the text that appears\n"
                    "6. Click the button below and paste the text in the box\n"
                ),
                key="javascript_instructions_description",
            ),
        )
        embed.set_image(url="https://i.imgur.com/PxO0Wr6.gif")
        code = "script:document.write(document.cookie)"
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterCookies(v2=False))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)
        await i.followup.send(code, ephemeral=True)


class WithDevTools(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("With DevTools (Desktop Only)", key="devtools_button_label")
        )

    async def callback(self, i: INTERACTION) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    "1. Login to [HoYoLAB](https://www.hoyolab.com/home) or [Miyoushe](https://www.miyoushe.com/ys/) (for CN players)\n"
                    "2. Open the DevTools by pressing F12 or Ctrl+Shift+I\n"
                    "3. Press the >> icon on the top navigation bar\n"
                    "4. Click on the `Application` tab\n"
                    "5. Click on `Cookies` on the left sidebar\n"
                    "6. Click on the website you're on (e.g. https://www.hoyolab.com)\n"
                    "7. Type `ltoken` in the `Filter` box and copy the `Value` of `ltoken` or `ltoken_v2`\n"
                    "8. Type `ltuid` in the `Filter` box and copy the `Value` of `ltuid` or `ltuid_v2`\n"
                    "9. Click the button below and paste the values you copied in the corresponding boxes\n"
                ),
                key="devtools_instructions_description",
            ),
        )
        embed.set_image(url="https://i.imgur.com/oSljaFQ.gif")
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterCookies(v2=True, dev_tools=True))
        self.view.add_item(EnterCookies(v2=False, dev_tools=True))
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)


class EmailPasswordContinueButton(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="email_password_continue",
            label=LocaleStr("Continue", key="continue_button_label"),
            emoji=emojis.FORWARD,
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, i: INTERACTION) -> Any:
        user = self.view.user
        await user.refresh_from_db()
        cookies: dict[str, Any] | None = user.temp_data.get("cookies")
        if cookies is None:
            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Cookies not found", key="cookies_not_found_title"),
                description=LocaleStr(
                    "Please complete the CAPTCHA before continuing.",
                    key="cookies_not_found_description",
                ),
            )
            self.label = self.view.translator.translate(
                LocaleStr("Refresh", key="refresh_button_label"), self.view.locale
            )
            self.emoji = emojis.REFRESH
            return await i.response.edit_message(embed=embed, view=self.view)

        if retcode := cookies.get("retcode"):
            if str(retcode) == "-3208":
                embed = ErrorEmbed(
                    self.view.locale,
                    self.view.translator,
                    title=LocaleStr(
                        "Invalid email or password", key="invalid_email_password_title"
                    ),
                    description=LocaleStr(
                        "Either your email or password is incorrect, please try again by pressing the back button.",
                        key="invalid_email_password_description",
                    ),
                )
                self.view.remove_item(self)
                return await i.response.edit_message(embed=embed, view=self.view)

            embed = ErrorEmbed(
                self.view.locale,
                self.view.translator,
                title=LocaleStr("Unknown error", key="unknown_error_title"),
                description=LocaleStr(
                    "Error code: {retcode}\nMessage: {msg}",
                    key="unknown_error_description",
                    retcode=retcode,
                    msg=cookies.get("message"),
                ),
            )
            return await i.response.edit_message(embed=embed, view=self.view)

        await self.set_loading_state(i)
        str_cookies = "; ".join(f"{key}={value}" for key, value in cookies.items())
        client = GenshinClient(str_cookies)
        client.set_lang(self.view.locale)
        game_accounts = await client.get_game_accounts()
        await self.unset_loading_state(i)

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(
            SelectAccountsToAdd(
                self.view.locale,
                self.view.translator,
                accounts=game_accounts,
                cookies=str_cookies,
            )
        )
        self.view.add_item(go_back_button)
        await i.edit_original_response(embed=None, view=self.view)


class EmailPasswordModal(Modal):
    email = TextInput(
        label=LocaleStr("email or username", key="email_password_modal_email_input_label"),
        placeholder="a@gmail.com",
    )
    password = TextInput(
        label=LocaleStr("password", key="email_password_modal_password_input_label"),
        placeholder="12345678",
    )


class EnterEmailPassword(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("Enter Email and Password", key="enter_email_password_button_label"),
            style=discord.ButtonStyle.primary,
            emoji=emojis.PASSWORD,
        )

    async def callback(self, i: INTERACTION) -> Any:
        modal = EmailPasswordModal(
            title=LocaleStr("Enter Email and Password", key="enter_email_password_modal_title")
        )
        modal.translate(self.view.locale, i.client.translator)
        await i.response.send_modal(modal)
        await modal.wait()

        if modal.email.value is None or modal.password.value is None:
            return
        email = modal.email.value
        password = modal.password.value
        self.view.user.temp_data["email"] = email
        self.view.user.temp_data["password"] = password
        await self.view.user.save()

        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        web_server_url = GEETEST_SERVER_URL[i.client.env]
        self.view.add_item(
            Button(
                label=LocaleStr("Complete CAPTCHA", key="complete_captcha_button_label"),
                url=f"{web_server_url}/?user_id={i.user.id}&locale={self.view.locale.value}",
            )
        )
        self.view.add_item(EmailPasswordContinueButton())
        self.view.add_item(go_back_button)
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{emojis.INFO} Note: This method **DOESN'T WORK** for Miyoushe users, only HoYoLAB users can use this method.\n\n"
                    "1. Click the `Complete CAPTCHA` button below\n"
                    "2. You will be redirected to a website, click the button and complete the CAPTCHA\n"
                    "3. After completing, click on the `Continue` button below\n"
                ),
                key="email_password_instructions_description",
            ),
        )
        embed.set_image(url="https://i.imgur.com/Q9cR2Sf.gif")
        await i.edit_original_response(embed=embed, view=self.view)


class WithEmailPassword(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            label=LocaleStr("With Email and Password", key="email_password_button_label")
        )

    async def callback(self, i: INTERACTION) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Instructions", key="instructions_title"),
            description=LocaleStr(
                (
                    f"{emojis.INFO} Note: This method is not recommended as it requires you to enter your private information, it only serves as a last resort when the other 2 methods don't work. Your email and password are not saved permanently in the database, you can refer to the [source code](https://github.com/seriaati/hoyo-buddy/blob/3bbd8a9fb42d2bb8db4426fda7d7d3ba6d86e75c/hoyo_buddy/ui/login/accounts.py#L386) if you feel unsafe.\n\n"
                    "Click the button below to enter your email and password.\n"
                ),
                key="enter_email_password_instructions_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(EnterEmailPassword())
        self.view.add_item(go_back_button)
        await i.response.edit_message(embed=embed, view=self.view)


class AddAccount(Button["AccountManager"]):
    def __init__(self) -> None:
        super().__init__(
            custom_id="add_account",
            emoji=emojis.ADD,
            label=LocaleStr("Add accounts", key="add_account_button_label"),
            style=discord.ButtonStyle.primary,
        )

    async def callback(self, i: INTERACTION) -> Any:
        embed = DefaultEmbed(
            self.view.locale,
            self.view.translator,
            title=LocaleStr("Adding accounts", key="adding_accounts_title"),
            description=LocaleStr(
                "Below are 3 ways you can add accounts; however, it is recommended to try the first one, then work your way through the others if it doesn't work.",
                key="adding_accounts_description",
            ),
        )
        go_back_button = GoBackButton(self.view.children, self.view.get_embeds(i.message))
        self.view.clear_items()
        self.view.add_item(WithJavaScript())
        self.view.add_item(WithDevTools())
        self.view.add_item(WithEmailPassword())
        self.view.add_item(go_back_button)

        await i.response.edit_message(embed=embed, view=self.view)
