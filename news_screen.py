import flet as ft
from collections import OrderedDict
import asyncio, aiohttp, json
from config import settings

chart_cache = OrderedDict()
MAX_CACHE_ITEMS = 100

def add_to_cache(key, value):
    if key in chart_cache:
        chart_cache.move_to_end(key)
    chart_cache[key] = value
    if len(chart_cache) > MAX_CACHE_ITEMS:
        chart_cache.popitem(last=False)

ANALYTICS_KEYWORDS = {
    "%", "percent", "statistics", "stats", "budget",
    "growth", "increase", "decrease", "trend", "data",
    "analysis", "report"
}

def contains_stats(text: str) -> bool:
    return any(word in text.lower() for word in ANALYTICS_KEYWORDS)

async def call_ai_router(text: str, token: str):
    if not contains_stats(text):
        return {"decision": "text"}
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {token}"}
            data = {"message": text, "user_id": "news_user"}
            async with session.post(f"{settings.API_BASE}/chat", headers=headers, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("chart_data"):
                        return {"decision": "chart", "chart_data": result["chart_data"]}
                return {"decision": "text"}
    except:
        return {"decision": "text"}

def ai_news_banner(item):
    if not item.get("is_fake"):
        return None
    return ft.Container(
        content=ft.Text("⚠️ FAKE NEWS DETECTED\nStep 1: Check source", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.RED_600, padding=10, border_radius=8
    )

def NewsScreen(page: ft.Page, token: str = "", user_id="u123"):
    page.title = "EchoChat News"
    news_list = ft.ListView(expand=True, spacing=15, padding=15)

    def notify(message: str):
        page.snack_bar = ft.SnackBar(content=ft.Text(message))
        page.snack_bar.open = True
        page.update()

    async def build_news_card(item):
        chart_container = ft.Container(visible=False)

        async def show_chart(e):
            btn = e.control
            article_key = item["title"]
            if not contains_stats(item["content"]):
                notify("No chartable statistics found.")
                return
            btn.text = "Loading..."; btn.disabled = True; page.update()
            try:
                if article_key in chart_cache:
                    chart_container.content = chart_cache[article_key]
                    chart_container.visible = True
                else:
                    ai_result = await call_ai_router(item["content"], token)
                    if ai_result["decision"] != "chart":
                        notify("No chart available."); return
                    data = ai_result["chart_data"]
                    chart = ft.BarChart(
                        bar_groups=[ft.BarChartGroup(x=i, bar_rods=[ft.BarChartRod(from_y=0, to_y=val, width=25, color=ft.Colors.BLUE_400, border_radius=5)]) for i, val in enumerate(data["values"])],
                        bottom_axis=ft.ChartAxis(labels=[ft.ChartAxisLabel(value=i, label=ft.Text(lbl)) for i, lbl in enumerate(data["labels"])]),
                        height=250
                    )
                    chart_ui = ft.Column([ft.Text(data["title"], size=18, weight=ft.FontWeight.BOLD), chart])
                    chart_container.content = chart_ui
                    chart_container.visible = True
                    add_to_cache(article_key, chart_ui)
                page.update()
            except Exception as ex:
                notify(f"Chart error: {ex}")
            finally:
                btn.text = "📊 View Chart"; btn.disabled = False; page.update()

        card_controls = []
        if banner := ai_news_banner(item):
            card_controls.append(banner)
        card_controls += [
            ft.Text(item["title"], size=18, weight=ft.FontWeight.BOLD),
            ft.Text(item["content"]),
            ft.ElevatedButton("📊 View Chart", on_click=show_chart),
            chart_container
        ]
        return ft.Card(content=ft.Container(content=ft.Column(card_controls), padding=15))

    sample_items = [
        {"title": "Budget 2026", "content": "Education 35%, Health 20%, Defense 15%, Infrastructure 30%", "is_fake": False},
        {"title": "Viral Fake News", "content": "Alien invasion tomorrow!", "is_fake": True}
    ]
    for item in sample_items:
        news_list.controls.append(ft.Container(content=ft.Text("Loading..."), data=item))

    async def load_news():
        for i, item in enumerate(sample_items):
            card = await build_news_card(item)
            news_list.controls[i] = card
            page.update()
    asyncio.run(load_news())

    return news_list
