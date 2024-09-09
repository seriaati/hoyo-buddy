from __future__ import annotations

import operator
import os
from typing import TYPE_CHECKING

import flet as ft
from flet.auth import OAuthProvider

from hoyo_buddy.l10n import LocaleStr, Translator

if TYPE_CHECKING:
    from discord import Locale

__all__ = ("LoginPage",)


class LoginPage(ft.View):
    def __init__(self, *, translator: Translator, locale: Locale) -> None:
        self.provider = OAuthProvider(
            client_id=os.environ["DISCORD_CLIENT_ID"],
            client_secret=os.environ["DISCORD_CLIENT_SECRET"],
            authorization_endpoint="https://discord.com/oauth2/authorize",
            token_endpoint="https://discord.com/api/oauth2/token",  # noqa: S106
            user_endpoint="https://discord.com/api/users/@me",
            user_scopes=["identify"],
            user_id_fn=operator.itemgetter("id"),
            redirect_url="http://localhost:8645/oauth_callback"
            if os.environ["ENV"] == "dev"
            else "https://hb-app.seriaati.xyz/oauth_callback",
        )
        super().__init__(
            "login",
            [
                ft.SafeArea(
                    ft.Container(
                        ft.FilledButton(
                            translator.translate(LocaleStr(key="login_button_label"), locale),
                            on_click=self.on_login_button_click,
                            icon=ft.icons.DISCORD,
                        ),
                        margin=ft.margin.all(10),
                    )
                )
            ],
        )

    async def on_login_button_click(self, e: ft.ControlEvent) -> None:
        page: ft.Page = e.page
        await page.login_async(self.provider)  # pyright: ignore[reportArgumentType]
