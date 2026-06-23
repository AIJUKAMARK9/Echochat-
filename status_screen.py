import flet as ft

class StatusScreen(ft.Column):
    def __init__(self, page: ft.Page, token: str):
        super().__init__(expand=True, alignment=ft.MainAxisAlignment.CENTER)
        self.controls = [
            ft.Icon(ft.Icons.CIRCLE, size=60, color=ft.Colors.GREY),
            ft.Text("No status updates", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Share a photo or video that disappears in 24h", color=ft.Colors.GREY),
        ]
