import flet as ft
import asyncio
from typing import List, Optional

class AINewsBanner(ft.Container):
    def __init__(self, headline: str, is_fake: bool = False):
        super().__init__()
        self.bgcolor = ft.Colors.RED_600 if is_fake else ft.Colors.GREEN_600
        self.padding = 15
        self.border_radius = 10
        self.margin = ft.margin.only(bottom=10)
        icon = ft.Icons.WARNING if is_fake else ft.Icons.CHECK_CIRCLE
        self.content = ft.Row([
            ft.Icon(icon, color=ft.Colors.WHITE),
            ft.Text(headline, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=16, expand=True),
        ])

class ChartPopup(ft.AlertDialog):
    def __init__(self, title: str, chart_data: List):
        super().__init__()
        self.modal = True
        self.title = ft.Text(title, weight=ft.FontWeight.BOLD)
        bars = []
        labels = []
        max_value = max((item.get("value", 0) for item in chart_data), default=0)
        for item in chart_data:
            value = max(0, int(item.get("value", 0)))
            bar_height = max(10, min(200, int((value / max_value) * 200))) if max_value else 0
            bars.append(ft.Container(
                height=bar_height, width=50, bgcolor=ft.Colors.BLUE_400,
                border_radius=5, tooltip=f"{item.get('label', '')}: {value}",
                animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_OUT),
            ))
            labels.append(ft.Text(item.get("label", ""), size=11))
        self.content = ft.Column([
            ft.Text("AI Generated Stats", size=14, color=ft.Colors.GREY_700),
            ft.Row(controls=bars, alignment=ft.MainAxisAlignment.CENTER, spacing=12),
            ft.Row(controls=labels, alignment=ft.MainAxisAlignment.CENTER, spacing=12),
        ], tight=True, spacing=10)
        self.actions = [ft.TextButton("Close", on_click=self.close_dialog)]

    def close_dialog(self, e):
        self.open = False
        if self.page:
            self.page.dialog = None
            self.page.update()

class AIHelperBubble(ft.Container):
    def __init__(self, page: ft.Page):
        super().__init__()
        self.page = page
        self.width = 60
        self.height = 60
        self.border_radius = 30
        self.bgcolor = ft.Colors.PURPLE_500
        self.shadow = ft.BoxShadow(blur_radius=12, color=ft.Colors.BLACK45)
        self.right = 20
        self.bottom = 80
        self.content = ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=30)
        self.on_click = self.show_snackbar
        self.animate_scale = ft.animation.Animation(250, ft.AnimationCurve.EASE_IN_OUT)

    def show_snackbar(self, e):
        if self.page:
            self.page.show_snack_bar(ft.SnackBar(content=ft.Text("AI Helper: Ask me anything!")))

    async def animate_pulse(self):
        if not self.page:
            return
        self.scale = ft.transform.Scale(1.15)
        self.update()
        await asyncio.sleep(0.25)
        self.scale = ft.transform.Scale(1.0)
        self.update()

class SafetyWarning(ft.Container):
    def __init__(self, reason: str, chunk_id: Optional[int] = None):
        super().__init__()
        self.reason = reason
        self.chunk_id = chunk_id
        self.visible = True
        self.bgcolor = ft.Colors.ORANGE_800
        self.padding = 12
        self.border_radius = 8
        self.margin = ft.margin.only(top=10, bottom=10)
        controls = [
            ft.Row([
                ft.Icon(ft.Icons.BLOCK, color=ft.Colors.WHITE, size=20),
                ft.Text("Safety Warning", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            ]),
            ft.Text(reason, color=ft.Colors.WHITE70, size=13),
        ]
        if chunk_id is not None:
            controls.append(ft.Text(f"Chunk: {chunk_id}", color=ft.Colors.WHITE54, size=11))
        controls.append(ft.TextButton("Dismiss", style=ft.ButtonStyle(color=ft.Colors.WHITE), on_click=self.dismiss))
        self.content = ft.Column(controls=controls, spacing=5, tight=True)

    def dismiss(self, e=None):
        self.visible = False
        if self.page:
            self.update()
