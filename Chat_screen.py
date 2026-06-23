import flet as ft
import aiohttp
import asyncio
import json
from urllib.parse import urlparse
from config import settings

class ChatScreen(ft.Column):
    def __init__(self, page: ft.Page, token: str):
        super().__init__(expand=True, spacing=10)
        self.page = page
        self.token = token
        self.user_id = "chat_user"
        self.current_conversation_id = None
        self.ws = None
        self.http_session = aiohttp.ClientSession()

        self.tabs = ft.Tabs(
            selected_index=0,
            on_change=self.tab_changed,
            tabs=[
                ft.Tab(text="AI Chat"),
                ft.Tab(text="Friends"),
            ]
        )
        self.controls.append(self.tabs)

        # AI Chat Panel
        self.ai_list = ft.ListView(expand=True, auto_scroll=True)
        self.ai_input = ft.TextField(
            hint_text="Ask EchoChat AI anything...",
            expand=True,
            on_submit=self.send_ai_message
        )
        self.ai_send = ft.IconButton(icon=ft.Icons.SEND, on_click=self.send_ai_message)
        self.ai_loading = ft.ProgressBar(visible=False)
        self.ai_panel = ft.Column([
            self.ai_list,
            ft.Row([self.ai_input, self.ai_send]),
            self.ai_loading
        ], visible=True)

        # Friends Panel
        self.friends_list = ft.ListView(expand=True, auto_scroll=True)
        self.friends_empty = ft.Text("No conversations yet.", size=14, color=ft.Colors.GREY)
        self.friends_panel = ft.Column([self.friends_list, self.friends_empty], visible=False)

        # Conversation Panel
        self.conv_title = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
        self.conv_list = ft.ListView(expand=True, auto_scroll=True)
        self.conv_empty = ft.Text("No messages yet.", size=14, color=ft.Colors.GREY)
        self.conv_input = ft.TextField(
            hint_text="Type a message...",
            expand=True,
            on_submit=self.send_conv_message
        )
        self.conv_send = ft.IconButton(icon=ft.Icons.SEND, on_click=self.send_conv_message)
        self.back_btn = ft.TextButton("← Back", on_click=self.back_to_friends)
        self.reconnect_label = ft.Text("", size=12, color=ft.Colors.YELLOW, visible=False)
        self.conv_panel = ft.Column([
            ft.Row([self.back_btn, self.conv_title]),
            self.conv_list,
            self.conv_empty,
            ft.Row([self.conv_input, self.conv_send]),
            self.reconnect_label
        ], visible=False)

        self.controls.append(ft.Stack([
            self.ai_panel,
            self.friends_panel,
            self.conv_panel
        ]))

        self.page.run_task(self.load_initial_data)

    async def load_initial_data(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.http_session.get(f"{settings.API_BASE}/auth/me", headers=headers) as resp:
                if resp.status == 200:
                    user = await resp.json()
                    self.user_id = str(user["id"])
        except:
            pass
        await self.load_friends()

    # ----------------- AI Chat -----------------
    async def send_ai_message(self, e):
        text = self.ai_input.value.strip()
        if not text:
            return
        self.ai_list.controls.append(self._user_bubble(text))
        self.ai_input.value = ""
        self.ai_input.disabled = True
        self.ai_send.disabled = True
        self.ai_loading.visible = True
        self.page.update()

        ai_bubble = self._ai_bubble("")
        self.ai_list.controls.append(ai_bubble)
        self.page.update()

        headers = {"Authorization": f"Bearer {self.token}"}
        data = {"message": text, "user_id": self.user_id}
        full_reply = ""
        try:
            async with self.http_session.post(
                f"{settings.API_BASE}/chat/stream",
                headers=headers,
                data=data
            ) as resp:
                if resp.status == 200:
                    async for line in resp.content:
                        line = line.decode().strip()
                        if line.startswith("data: "):
                            token = line[6:]
                            if token == "[DONE]":
                                break
                            full_reply += token
                            ai_bubble.content = self._ai_bubble_content(full_reply)
                            self.page.update()
                else:
                    full_reply = f"Error: {resp.status}"
        except Exception as ex:
            full_reply = f"Error: {ex}"
        finally:
            ai_bubble.content = self._ai_bubble_content(full_reply)
            self.ai_input.disabled = False
            self.ai_send.disabled = False
            self.ai_loading.visible = False
            self.page.update()

    def _user_bubble(self, text):
        return ft.Container(
            content=ft.Text(f"You: {text}", color=ft.Colors.WHITE),
            bgcolor=ft.Colors.PURPLE_500,
            border_radius=10,
            padding=10,
            margin=ft.margin.only(right=10, bottom=5),
        )

    def _ai_bubble(self, text):
        return ft.Container(
            content=self._ai_bubble_content(text),
            bgcolor=ft.Colors.BLUE_700,
            border_radius=10,
            padding=10,
            margin=ft.margin.only(left=10, bottom=5),
        )

    def _ai_bubble_content(self, text):
        return ft.Text(f"EchoChat AI: {text}", color=ft.Colors.WHITE)

    # ----------------- Friends / Conversations -----------------
    async def load_friends(self):
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.http_session.get(f"{settings.API_BASE}/social/conversations", headers=headers) as resp:
                if resp.status == 200:
                    convs = await resp.json()
                    self.friends_list.controls.clear()
                    self.friends_empty.visible = len(convs) == 0
                    for c in convs:
                        self.friends_list.controls.append(
                            ft.TextButton(
                                text=c["other_user"],
                                on_click=lambda e, cid=c["id"]: self.open_conversation(cid)
                            )
                        )
                    self.page.update()
        except:
            pass

    async def open_conversation(self, conv_id):
        self.current_conversation_id = conv_id
        self.ai_panel.visible = False
        self.friends_panel.visible = False
        self.conv_panel.visible = True
        self.page.update()

        self.conv_title.value = f"Chat {conv_id[:8]}"
        self.conv_list.controls.clear()
        self.conv_empty.visible = False
        self.page.update()

        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self.http_session.get(
                f"{settings.API_BASE}/social/messages/{conv_id}?limit=50",
                headers=headers
            ) as resp:
                if resp.status == 200:
                    msgs = await resp.json()
                    self.conv_empty.visible = len(msgs) == 0
                    for msg in msgs:
                        if msg["sender_id"] == int(self.user_id):
                            self.conv_list.controls.append(self._user_bubble(msg["content"]))
                        else:
                            self.conv_list.controls.append(
                                ft.Container(
                                    content=ft.Text(
                                        f"{msg['sender_username']}: {msg['content']}",
                                        color=ft.Colors.WHITE
                                    ),
                                    bgcolor=ft.Colors.GREEN_700,
                                    border_radius=10,
                                    padding=10,
                                    margin=ft.margin.only(left=10, bottom=5),
                                )
                            )
                    self.page.update()
        except:
            pass

        await self.connect_websocket()

    async def connect_websocket(self):
        if self.ws:
            await self.ws.close()
            self.ws = None
        proto = "wss://" if settings.API_BASE.startswith("https") else "ws://"
        host = urlparse(settings.API_BASE).netloc
        ws_url = f"{proto}{host}/social/ws/chat?token={self.token}"
        retry_delay = 1
        while self.current_conversation_id:
            try:
                self.ws = await aiohttp.ClientSession().ws_connect(ws_url)
                self.reconnect_label.visible = False
                self.page.update()
                self.page.run_task(self._listen_ws_with_reconnect())
                return
            except:
                self.reconnect_label.value = "Reconnecting..."
                self.reconnect_label.visible = True
                self.page.update()
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)

    async def _listen_ws_with_reconnect(self):
        while self.current_conversation_id:
            try:
                async for msg in self.ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if ("conversation_id" in data and data["conversation_id"] == self.current_conversation_id) or \
                           ("group_id" in data and data.get("group_id") == self.current_conversation_id):
                            if data.get("sender_id") != int(self.user_id):
                                self.conv_list.controls.append(
                                    ft.Container(
                                        content=ft.Text(
                                            f"{data['sender_username']}: {data['content']}",
                                            color=ft.Colors.WHITE
                                        ),
                                        bgcolor=ft.Colors.GREEN_700,
                                        border_radius=10,
                                        padding=10,
                                        margin=ft.margin.only(left=10, bottom=5),
                                    )
                                )
                                self.conv_empty.visible = False
                                self.page.update()
                    elif msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
            except:
                pass
            if self.current_conversation_id:
                await self.connect_websocket()
            else:
                break

    async def send_conv_message(self, e):
        text = self.conv_input.value.strip()
        if not text or not self.ws:
            return
        await self.ws.send_json({
            "action": "send_message",
            "conversation_id": self.current_conversation_id,
            "content": text
        })
        self.conv_list.controls.append(self._user_bubble(text))
        self.conv_input.value = ""
        self.conv_empty.visible = False
        self.page.update()

    async def back_to_friends(self, e):
        self.conv_panel.visible = False
        self.friends_panel.visible = True
        self.ai_panel.visible = False
        if self.ws:
            await self.ws.close()
            self.ws = None
        self.current_conversation_id = None
        self.page.update()

    def tab_changed(self, e):
        idx = e.control.selected_index
        self.ai_panel.visible = (idx == 0)
        self.friends_panel.visible = (idx == 1)
        self.conv_panel.visible = False
        if idx == 1:
            self.page.run_task(self.load_friends())
        self.page.update()

    async def dispose(self):
        if self.http_session:
            await self.http_session.close()
        if self.ws:
            await self.ws.close()
