from __future__ import annotations

import os
from typing import TYPE_CHECKING

import flet as ft
from cryptography.fernet import Fernet

from ..l10n import LocaleStr, Translator

if TYPE_CHECKING:
    from discord import Locale


class LoadingSnackBar(ft.SnackBar):
    def __init__(self, *, translator: Translator, locale: Locale) -> None:
        super().__init__(
            ft.Row(
                [
                    ft.ProgressRing(
                        width=16, height=16, stroke_width=2, color=ft.colors.ON_SECONDARY_CONTAINER
                    ),
                    ft.Text(
                        translator.translate(LocaleStr(key="loading_text"), locale),
                        color=ft.colors.ON_SECONDARY_CONTAINER,
                    ),
                ]
            ),
            bgcolor=ft.colors.SECONDARY_CONTAINER,
        )


class ErrorSnackBar(ft.SnackBar):
    def __init__(self, message: str) -> None:
        super().__init__(
            ft.Row(
                [
                    ft.Icon(ft.icons.ERROR, color=ft.colors.ON_ERROR_CONTAINER),
                    ft.Text(message, color=ft.colors.ON_ERROR_CONTAINER),
                ]
            ),
            bgcolor=ft.colors.ERROR_CONTAINER,
        )


async def show_loading_snack_bar(page: ft.Page, *, translator: Translator, locale: Locale) -> None:
    await page.show_snack_bar_async(LoadingSnackBar(translator=translator, locale=locale))


async def show_error_snack_bar(page: ft.Page, *, message: str) -> None:
    await page.show_snack_bar_async(ErrorSnackBar(message))


def decrypt_string(encrypted: str) -> str:
    key = Fernet(os.environ["FERNET_KEY"])
    return key.decrypt(encrypted.encode()).decode()


def encrypt_string(string: str) -> str:
    key = Fernet(os.environ["FERNET_KEY"])
    return key.encrypt(string.encode()).decode()
