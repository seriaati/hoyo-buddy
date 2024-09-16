from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING

import flet as ft

from hoyo_buddy.l10n import LocaleStr, Translator

if TYPE_CHECKING:
    from discord import Locale

__all__ = ("LoginPage",)


class LoginPage(ft.View):
    def __init__(self, *, translator: Translator, locale: Locale) -> None:
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
        state = secrets.token_urlsafe(32)
        await page.client_storage.set_async("hb.oauth_state", state)
        redirect_url = (
            "http://localhost:8645/custom_oauth_callback"
            if os.environ["ENV"] == "dev"
            else "https://hb-app.seria.moe/custom_oauth_callback"
        )
        oauth_url = f"https://discord.com/oauth2/authorize?response_type=code&client_id={os.environ['DISCORD_CLIENT_ID']}&redirect_uri={redirect_url}&scope=identify&state={state}"
        await page.launch_url_async(oauth_url, web_window_name=ft.UrlTarget.SELF.value)
