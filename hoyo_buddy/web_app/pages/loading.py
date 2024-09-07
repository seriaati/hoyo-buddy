from __future__ import annotations

import flet as ft

__all__ = ("LoadingPage",)


class LoadingPage(ft.View):
    def __init__(self) -> None:
        super().__init__(
            controls=[
                ft.SafeArea(
                    ft.Column(
                        [
                            ft.ProgressRing(
                                width=64, height=64, stroke_width=2, color=ft.colors.ON_SURFACE
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            vertical_alignment=ft.MainAxisAlignment.CENTER,
        )
