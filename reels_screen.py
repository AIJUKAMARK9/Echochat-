import flet as ft

class ReelsScreen(ft.Column):
    def __init__(self, page: ft.Page, token: str):
        super().__init__(expand=True, alignment=ft.MainAxisAlignment.CENTER)
        self.controls = [
            ft.Icon(ft.Icons.VIDEO_LIBRARY, size=60, color=ft.Colors.GREY),
            ft.Text("No reels yet", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Upload a short video to get started", color=ft.Colors.GREY),
        ]
