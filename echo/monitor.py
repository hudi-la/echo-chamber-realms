"""作者监控台：浏览器里看流水和三只木偶的记忆，也能打字、打断。观众永远看不到这个页面。
它只是房间的一个订阅者 + 一个键盘替身，对引擎没有任何额外权力。"""

from .settings import parameter, parameters, rule
import asyncio
import json
import hashlib
from uuid import uuid4
from pathlib import Path
from typing import Iterable

from .events import (Event, HumanSaid, HumanStarted, PuppetCut, PuppetSaid, PuppetStarted,
                     Quiet, VisitorArrived, VisitorLeft, WokeUp)
from .floor import HUMAN

PAGE = Path(__file__).with_name("monitor.html")


def event_to_msg(ev: Event) -> dict | None:
    if isinstance(ev, HumanSaid):
        return {"type": "said", "who": HUMAN, "text": ev.text}
    if isinstance(ev, HumanStarted):
        return {"type": "human_started"}
    if isinstance(ev, PuppetStarted):
        return {"type": "started", "who": ev.name, "text": ev.text,
                **({"performance": dict(ev.performance)} if ev.performance else {})}
    if isinstance(ev, PuppetSaid):
        return {"type": "said", "who": ev.name, "text": ev.text}
    if isinstance(ev, PuppetCut):
        return {"type": "cut", "who": ev.name, "text": ev.spoken}
    if isinstance(ev, Quiet):
        return {"type": "quiet", "seconds": int(ev.seconds)}
    if isinstance(ev, VisitorArrived):
        return {"type": "arrived"}
    if isinstance(ev, VisitorLeft):
        return {"type": "left", "session": ev.session_id}
    if isinstance(ev, WokeUp):
        return {"type": "woke", "day": ev.day}
    return None


class Monitor:
    def __init__(self, room, puppets: Iterable, host: str | None = None, port: int | None = None,
                 on_mic_frame=None) -> None:
        self.room, self.puppets = room, list(puppets)
        self.host = parameter("monitor.host") if host is None else host
        self.port = parameters()["defaults"]["monitor"]["port"] if port is None else port
        self.on_mic_frame = on_mic_frame  # 浏览器送来的麦克风帧（二进制）交给谁
        self._inbox = room.subscribe()  # 构造时就订阅
        self._clients: set = set()
        self._history: list[dict] = []
        self._audio_client = None
        self.audio_ready = asyncio.Event()
        self.waiting_for_audio = False
        self.interaction = None
        self.on_audio_ready = None
        self.on_playback = None
        self.on_audio_disconnect = None
        self.run_id = uuid4().hex
        self._initial_thoughts = {
            p.name: {json.dumps(note, sort_keys=True) for note in p.memory.private_thoughts}
            for p in self.puppets
        }
        self._exhibition_speech = []

    # --- 对外：给 puppet 当 log 用 ---

    def log(self, line: str) -> None:
        self.broadcast({"type": "log", "text": line.strip()})

    def hearing(self, text: str | None) -> None:
        """耳朵正在转写的半句话；None = 这句结束了。不进历史。"""
        self.broadcast({"type": "hearing", "text": text or ""})

    # --- 状态快照 ---

    def snapshot(self) -> dict:
        now = self.room.clock.now()
        return {
            "type": "status",
            "run_id": self.run_id,
            "exhibition_speech": list(self._exhibition_speech),
            "day": self.room.day,
            "waiting_for_audio": self.waiting_for_audio,
            "audio_connected": self.audio_ready.is_set(),
            "visitor": self.room.visitor.present,
            "presence_reliable": self.room.presence_reliable,
            "speaker": self.room.speaker,
            "interaction": self.interaction,
            "quiet_for": int(now - self.room.last_activity),
            "puppets": {
                p.name: {
                    "usage": (p.brain.token_usage.snapshot() if getattr(getattr(p, 'brain', None), 'token_usage', None) is not None else None),
                    "private_thoughts": p.memory.private_thoughts[-parameter("thoughts.prompt_keep"):] if rule("memory.private_thoughts_enabled") else [],
                    "exhibition_thoughts": [note for note in p.memory.private_thoughts
                        if json.dumps(note, sort_keys=True) not in self._initial_thoughts[p.name]]
                        if rule("memory.private_thoughts_enabled") else [],
                    "beliefs": p.memory.beliefs,
                    "relations": p.memory.relations,
                    "impressions": [i["text"] for i in p.memory.impressions[-5:]],
                    "last_spoke_ago": None if p.last_spoke_at is None else int(now - p.last_spoke_at),
                } for p in self.puppets
            },
        }

    # --- 广播 ---

    def broadcast(self, msg: dict) -> None:
        if msg["type"] == "said" and msg.get("who") in {p.name for p in self.puppets}:
            self._exhibition_speech.append({"who": msg["who"], "text": msg.get("text", ""), "id": uuid4().hex})
            del self._exhibition_speech[:-9]
        if msg["type"] not in ("status", "play", "stop", "hearing"):  # 快照、音频、半句话不进历史
            self._history.append(msg)
            del self._history[:-parameter("monitor.history_entries")]
        clients = ([self._audio_client] if self._audio_client is not None else []) if msg["type"] in ("play", "stop") else list(self._clients)
        for ws in clients:
            asyncio.ensure_future(self._send(ws, msg))

    async def _send(self, ws, msg: dict) -> None:
        try:
            await ws.send_json(msg)
        except Exception:
            self._clients.discard(ws)

    async def _pump(self) -> None:
        while True:
            ev = await self._inbox.get()
            if isinstance(ev, PuppetStarted):
                self.interaction = {"who": ev.name, "at": ev.at, **dict(ev.performance)}
            elif isinstance(ev, (PuppetSaid, PuppetCut, HumanStarted)):
                self.interaction = None
            msg = event_to_msg(ev)
            if msg is not None:
                self.broadcast(msg)
            self.broadcast(self.snapshot())

    async def _tick(self) -> None:
        while True:
            await self.room.clock.sleep(parameter("monitor.update_seconds"))
            if self._clients:
                self.broadcast(self.snapshot())

    # --- HTTP ---

    async def _index(self, request):
        from aiohttp import web
        html = PAGE.read_text(encoding="utf-8")
        # Content-based URLs prevent an old cached renderer from bypassing run filtering.
        for asset in (PAGE.parent / "static").glob("*.js"):
            version = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
            html = html.replace(f'/static/{asset.name}"', f'/static/{asset.name}?v={version}"')
        return web.Response(text=html, content_type="text/html",
                            headers={"Cache-Control": "no-store"})

    async def _ws(self, request):
        from aiohttp import web
        ws = web.WebSocketResponse(heartbeat=parameter("monitor.websocket_heartbeat_seconds"))
        await ws.prepare(request)
        self._clients.add(ws)
        try:
            for msg in self._history:
                await ws.send_json(msg)
            await ws.send_json(self.snapshot())
            async for raw in ws:
                if raw.type == web.WSMsgType.BINARY:
                    if ws is self._audio_client and self.on_mic_frame is not None:
                        self.on_mic_frame(raw.data)
                    continue
                if raw.type != web.WSMsgType.TEXT:
                    continue
                data = json.loads(raw.data)
                if data.get("type") == "audio_ready":
                    if self._audio_client is not None and self._audio_client is not ws:
                        await ws.send_json({"type": "audio_rejected"})
                    else:
                        newly_ready = not self.audio_ready.is_set()
                        self._audio_client = ws
                        self.audio_ready.set()
                        if newly_ready and self.on_audio_ready:
                            self.on_audio_ready()
                elif data.get("type") == "audio_off" and self._audio_client is ws:
                    self._audio_client = None
                    self.audio_ready.clear()
                    if self.on_audio_disconnect:
                        self.on_audio_disconnect()
                elif data.get("type") in ("play_started", "play_ended", "play_error"):
                    if ws is self._audio_client and self.on_playback:
                        self.on_playback(data)
                elif data.get("type") == "say" and data.get("text", "").strip():
                    await self.room.human_started()
                    await self.room.human_said(data["text"].strip())
                elif data.get("type") == "interrupt":
                    await self.room.human_started()
        finally:
            self._clients.discard(ws)
            if self._audio_client is ws:
                self._audio_client = None
                self.audio_ready.clear()
                if self.on_audio_disconnect:
                    self.on_audio_disconnect()
        return ws

    async def start(self) -> list[asyncio.Task]:
        from aiohttp import web
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/console", self._index)
        app.router.add_get("/exhibition", self._index)
        app.router.add_get("/ws", self._ws)
        app.router.add_static("/static/", PAGE.parent / "static", show_index=False)
        app.router.add_get("/favicon.ico", lambda request: web.Response(status=204))
        avatars = PAGE.parent.parent / "avatar"
        if avatars.is_dir():
            app.router.add_static("/avatars/", avatars, show_index=False)
        previews = PAGE.parent.parent / "artifacts" / "voice-preview-2026-10-18"
        if previews.is_dir():
            app.router.add_static("/voice-preview/", previews, show_index=False)
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        await web.TCPSite(runner, self.host, self.port).start()
        print(f"控制台：http://{self.host}:{self.port}/console")
        print(f"展厅视觉：http://{self.host}:{self.port}/exhibition")
        return [asyncio.create_task(self._pump()), asyncio.create_task(self._tick())]
