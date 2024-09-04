from __future__ import annotations

import flet as ft

__all__ = ("ErrorPage",)


class ErrorPage(ft.View):
    def __init__(self, *, code: int, message: str) -> None:
        super().__init__(
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.Text(str(code), size=100),
                            ft.Text(message, text_align=ft.TextAlign.CENTER, size=30),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            vertical_alignment=ft.MainAxisAlignment.CENTER,
        )
