import flet as ft

class LiveScreen(ft.Column):
    def __init__(self, page: ft.Page, token: str):
        super().__init__(expand=True, alignment=ft.MainAxisAlignment.CENTER)
        self.controls = [
            ft.Icon(ft.Icons.LIVE_TV, size=60, color=ft.Colors.GREY),
            ft.Text("No live streams", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Go live from your device", color=ft.Colors.GREY),
        ]
