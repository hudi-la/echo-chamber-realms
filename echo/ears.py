"""耳朵：麦克风 → 实时转写 → 房间的两个事件（有人开口了 / 一句话文字）。

三层：
- PlaybackGate：响度闸门。只在本机音频模式（[audio] io = "local"）用；浏览器模式有真的回声消除，不装闸门。
- Ears：逻辑。收简单事件流（("started",) / ("partial", text) / ("said", text)），做打断策略、过滤太短的转写、
  对照嘴最近说过的话（自听）。不碰任何 SDK，可以用假事件流测。
- RealtimeSource：OpenAI Realtime 转写会话 + 麦克风（本机 sounddevice，或浏览器送来的帧）+ 断线重连。

打断策略（[ears] interrupt）：
- "confirm"（默认）：没木偶在说 → 一有人声就开门；木偶在说 → 不凭"有声音"打断，凭流式转写吐出来的字，
  凑够至少四个不像木偶原话的字才打断；停/等一下等明确指令除外。仍需现场验证误收音率。
- "immediate"：一听到人声就打断。只在麦克风完全听不见扬声器时用（比如观众戴耳机）。

自听问题的来龙去脉见 docs/superpowers/specs/…design.md §7.1。"""

from .settings import parameter, parameters, rule
import asyncio
import base64
import difflib
import logging
import re
from typing import AsyncIterator, Callable

log = logging.getLogger("echo.ears")

SimpleEvent = tuple  # ("started",) | ("said", str)

_PUNCT_ONLY = re.compile(r"^[\s\W_]*$")




def _bare(text: str) -> str:
    """去标点、去名字。名字两边都会出现（"Kaka 你好" vs Kaka 的自述），不能拿来判自听。"""
    names = re.compile("|".join(re.escape(n) for n in rule("ears.echo_name_tokens")), re.IGNORECASE)
    return re.sub(r"\W", "", names.sub("", text))


def looks_like_echo(heard: str, playing: str | None, threshold: float | None = None) -> bool:
    """转写出来的话跟嘴正在放 / 刚放过的文字很像 → 是麦克风听见了木偶自己。
    两个尺度：整体相似度，或者听见的那几个字大部分能在木偶原话里连着找到（短碎片常见）。"""
    threshold = parameter("ears.echo_threshold") if threshold is None else threshold
    if not playing or not heard:
        return False
    a, b = _bare(heard), _bare(playing)
    if not a or not b:
        return False
    if a in b:
        return True
    matcher = difflib.SequenceMatcher(None, a, b)
    if matcher.ratio() >= threshold:
        return True
    longest = matcher.find_longest_match(0, len(a), 0, len(b)).size
    return longest >= parameter("ears.echo_min_match_chars") and longest / len(a) >= threshold


class PlaybackGate:
    """每 100ms 一块麦克风音频，问一句：这块送不送去转写？

    不在播放期：全送。
    播放期（含尾巴）：先用前几块学"漏音"电平；之后只有 rms 明显高于漏音（factor 倍，且不低于 floor）才送。
    漏音电平慢升快降，短暂的人声不会把它拉高。"""

    def __init__(self, factor: float | None = None, floor: float | None = None, tail: float | None = None, learn_chunks: int | None = None) -> None:
        self.factor = parameters()["defaults"]["ears"]["gate_factor"] if factor is None else factor
        self.floor = parameters()["defaults"]["ears"]["gate_floor"] if floor is None else floor
        self.tail = parameter("ears.gate_tail_seconds") if tail is None else tail
        self.learn_chunks = parameter("ears.gate_learn_chunks") if learn_chunks is None else learn_chunks
        self.leak = 0.0
        self._learned = 0
        self._last_play: float | None = None

    def feed(self, rms: float, playing: bool, now: float) -> bool:
        if playing:
            self._last_play = now
        in_play = playing or (self._last_play is not None and now - self._last_play < self.tail)
        if not in_play:
            return True
        if self._learned < self.learn_chunks:  # 头一两秒：只学，不送
            self.leak = max(self.leak, rms)
            self._learned += 1
            return False
        loud = rms > max(self.factor * self.leak, self.floor)
        if not loud:  # 只用"不响"的块更新漏音估计；人声不该把门槛抬高
            if rms > self.leak:
                self.leak += parameter("ears.gate_rise_rate") * (rms - self.leak)
            else:
                self.leak += parameter("ears.gate_fall_rate") * (rms - self.leak)
        return loud


class Ears:
    def __init__(self, room, recent_mouth_text: Callable[[], str | None],
                 interrupt: str | None = None, min_chars: int | None = None,
                 log_line: Callable[[str], None] = print,
                 live: Callable[[str | None], None] | None = None,
                 now: Callable[[], float] | None = None) -> None:
        self.room = room
        self.recent_mouth_text = recent_mouth_text
        self.interrupt = parameters()["defaults"]["ears"]["interrupt"] if interrupt is None else interrupt
        self.min_chars = parameters()["defaults"]["ears"]["min_chars"] if min_chars is None else min_chars
        self.log_line = log_line
        self.live = live          # 把正在转写的半句话推给监控台（None = 说完了/丢了）
        self.now = now or __import__("time").monotonic
        self._guarded = False  # 本轮开始时有角色在说，打断后也保留严格确认规则
        self._opened = False  # 已经发过 human_started、还没发 human_said
        self._started_at: float | None = None
        self.pause_grace = parameters()["defaults"]["ears"]["pause_grace"]
        self.transcript_timeout = parameters()["defaults"]["ears"]["transcript_timeout"]
        self.activity_timeout = parameters()["defaults"]["ears"]["activity_timeout"]
        self._active = False
        self._activity_at = self.now()
        self._stopped_at = None
        self._pending = set()
        self._segments = {}

    def _puppet_speaking(self) -> bool:
        holder = self.room.floor.holder
        return holder is not None and holder != "新朋友"

    async def on_started(self) -> None:
        self._guarded = self._guarded or self._puppet_speaking()
        self._started_at = self.now()
        self.log_line("  [耳朵] 有人开口了")
        if self._opened:
            return
        if self.interrupt == "confirm" and self._puppet_speaking():
            return  # 木偶在说：不凭"有声音"打断，等 on_partial 听出了什么再说
        await self.room.human_started()
        self._opened = True

    def _real_words(self, text: str, guarded: bool = False) -> bool:
        clean = re.sub(r"\W", "", text).lower()
        command = clean in rule("ears.interrupt_commands")
        minimum = max(self.min_chars, parameter("ears.guarded_min_chars")) if guarded else self.min_chars
        return (len(clean) >= minimum or command) and not looks_like_echo(text, self.recent_mouth_text())

    async def on_partial(self, text: str) -> None:
        """流式转写吐到一半。木偶在说话时，凑够几个不像木偶原话的字，就立刻打断。"""
        guarded = self._guarded or self._puppet_speaking()
        if self.live and (not guarded or self._real_words(text, guarded=True)):
            self.live(text)
        if self._opened or not self._puppet_speaking():
            return
        if self._real_words(text, guarded=True):
            await self.room.human_started()
            self._opened = True

    def _give_back(self) -> None:
        if self._opened:
            self.room.floor.release_human()  # 已经错误地打断了，把发言权还回去
            self._opened = False

    async def on_said(self, text: str) -> None:
        text = text.strip()
        if self.live:
            self.live(None)
        took = f"{self.now() - self._started_at:.1f} 秒" if self._started_at is not None else "?"
        self._started_at = None
        self.log_line(f"  [耳朵] 转写用了 {took}：「{text}」")
        guarded = self._guarded or self._puppet_speaking()
        self._guarded = False
        if guarded and not self._real_words(text, guarded=True) and not looks_like_echo(text, self.recent_mouth_text()):
            self.log_line(f"  (耳朵：播放期间未确认的短句或回声，不作为访客发言：「{text}」)")
            self._give_back()
            return
        if not text or _PUNCT_ONLY.match(text):
            self._give_back()
            return
        if len(re.sub(r"\W", "", text)) < self.min_chars and text.strip("。！？!?，, ") not in {"嗯", "好", "对", "不", "是", "停", "啊"}:
            self.log_line(f"  (耳朵：太短，丢掉「{text}」)")
            self._give_back()
            return
        if looks_like_echo(text, self.recent_mouth_text()):
            self.log_line(f"  (耳朵：听见的是木偶自己 —— 丢掉「{text}」)")
            self._give_back()
            return
        if not self._opened:
            await self.room.human_started()
        self._opened = False
        await self.room.human_said(text)

    async def _finish_turn(self):
        text = "".join(self._segments.values())
        self._segments.clear()
        self._pending.clear()
        self._active = False
        self._stopped_at = None
        if text:
            await self.on_said(text)
        else:
            self._give_back()
            self._guarded = False
            if self.live:
                self.live(None)

    async def _check_turn(self):
        now = self.now()
        if self._active and now - self._activity_at >= self.activity_timeout:
            self.log_line("  [耳朵] 人声活动失联，释放发言权")
            await self._finish_turn()
        elif not self._active and self._stopped_at is not None:
            elapsed = now - self._stopped_at
            if elapsed >= self.transcript_timeout or (not self._pending and elapsed >= self.pause_grace):
                await self._finish_turn()

    async def consume(self, events: AsyncIterator[SimpleEvent]) -> None:
        iterator = events.__aiter__()
        pending = asyncio.create_task(anext(iterator))
        try:
            while True:
                done, _ = await asyncio.wait({pending}, timeout=parameter("ears.event_poll_seconds"))
                if not done:
                    await self._check_turn()
                    continue
                try:
                    ev = pending.result()
                except StopAsyncIteration:
                    break
                kind = ev[0]
                if kind == "started":
                    self._active = True
                    self._activity_at = self.now()
                    self._stopped_at = None
                    if len(ev) > 1:
                        self._pending.add(ev[1])
                        self._segments.setdefault(ev[1], "")
                    await self.on_started()
                elif kind == "activity":
                    self._activity_at = self.now()
                elif kind == "stopped":
                    self._active = False
                    self._stopped_at = self.now()
                elif kind == "partial":
                    await self.on_partial(ev[1])
                elif kind == "said" and len(ev) > 2 and ev[2] in self._pending:
                    self._pending.discard(ev[2])
                    clean = re.sub(r"\W", "", ev[1])
                    accepted = bool(clean) and not looks_like_echo(ev[1], self.recent_mouth_text())
                    self._segments[ev[2]] = ev[1] if accepted else ""
                    if accepted and not self._opened and self._real_words("".join(self._segments.values()), guarded=self._guarded or self._puppet_speaking()):
                        await self.room.human_started()
                        self._opened = True
                elif kind == "said" and len(ev) == 2:  # 简单事件源兼容（键盘/离线测试）
                    self._active = False
                    await self.on_said(ev[1])
                elif kind == "failed":
                    self._pending.discard(ev[1])
                elif kind == "disconnected":
                    await self._finish_turn()
                await self._check_turn()
                pending = asyncio.create_task(anext(iterator))
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
            await self._finish_turn()


class RealtimeSource:
    """OpenAI Realtime 转写会话 + 麦克风。产出 ("started",) / ("said", text)。"""

    RATE = 24000

    def __init__(self, client, is_playing: Callable[[], bool], model: str | None = None,
                 language: str | None = None, silence_ms: int | None = None, vad_threshold: float | None = None,
                 gate: PlaybackGate | None = None, device=None,
                 frames: Callable[[], AsyncIterator[bytes]] | None = None,
                 on_status: Callable[[str], None] = print) -> None:
        self.client, self.is_playing = client, is_playing
        self.model = parameters()["defaults"]["ears"]["model"] if model is None else model
        self.language = parameters()["defaults"]["prompts"]["language"] if language is None else language
        self.silence_ms = parameters()["defaults"]["ears"]["silence_ms"] if silence_ms is None else silence_ms
        self.vad_threshold = parameters()["defaults"]["ears"]["vad_threshold"] if vad_threshold is None else vad_threshold
        self.gate = gate  # None = 不设闸门（浏览器那边有真的回声消除时用）
        self.device, self.on_status = device, on_status
        self.frames = frames  # 不为 None = 麦克风帧从别处来（浏览器），不开本地麦

    async def events(self) -> AsyncIterator[SimpleEvent]:
        """长跑：断了就等两秒重连。"""
        while True:
            try:
                async for ev in self._session():
                    yield ev
            except asyncio.CancelledError:
                raise
            except Exception as e:  # 网络、鉴权、设备 —— 都不该把房间弄死
                self.on_status(f"[ears] 断开（{type(e).__name__}: {str(e)[:80]}），2 秒后重连")
                yield ("disconnected",)
                await asyncio.sleep(2)

    async def _session(self) -> AsyncIterator[SimpleEvent]:
        import time
        import numpy as np

        async with self.client.realtime.connect(
                extra_query={"intent": "transcription"}, max_retries=0,
                websocket_connection_options={"open_timeout": 10}) as conn:
            await conn.session.update(session={
                "type": "transcription",
                "audio": {"input": {
                    "format": {"type": "audio/pcm", "rate": self.RATE},
                    "noise_reduction": {"type": "near_field"},
                    "transcription": {"model": self.model, "language": self.language},
                    "turn_detection": {"type": "server_vad", "threshold": self.vad_threshold,
                                       "silence_duration_ms": self.silence_ms, "prefix_padding_ms": 300},
                }},
            })
            queue: asyncio.Queue = asyncio.Queue(maxsize=parameter("ears.max_upload_queue_chunks"))
            voice_at = [0.0]

            def enqueue(chunk):
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(chunk)
            loop = asyncio.get_running_loop()
            gate, is_playing = self.gate, self.is_playing
            stats = {"frames": 0, "loud": 0, "started": 0, "said": 0}

            def gated(chunk: bytes) -> bytes:
                stats["frames"] += 1
                samples = np.frombuffer(chunk, dtype=np.int16)
                if len(samples) and float(np.abs(samples.astype(np.float32)).mean()) > parameter("ears.voice_activity_level"):
                    voice_at[0] = time.monotonic()
                if gate is None:
                    samples = np.frombuffer(chunk, dtype=np.int16)
                    if len(samples) and float(np.abs(samples).mean()) > parameter("ears.voice_activity_level"):
                        stats["loud"] += 1
                    return chunk
                samples = np.frombuffer(chunk, dtype=np.int16)
                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) if len(samples) else 0.0
                return chunk if gate.feed(rms, is_playing(), time.monotonic()) else bytes(len(chunk))

            stream = None
            feeder = None
            if self.frames is None:
                import sounddevice as sd
                from contextvars import copy_context
                audio_context = copy_context()
                def on_audio(indata, frames, t, status):
                    loop.call_soon_threadsafe(enqueue, audio_context.run(gated, bytes(indata)))

                stream = sd.InputStream(samplerate=self.RATE, channels=1, dtype="int16",
                                        blocksize=self.RATE // 10, device=self.device, callback=on_audio)
                stream.start()
                self.on_status(f"[ears] 在听（{self.model} · 麦克风 {sd.query_devices(stream.device)['name']}）")
            else:
                async def feed():
                    async for chunk in self.frames():
                        enqueue(gated(chunk))

                feeder = asyncio.create_task(feed())
                self.on_status(f"[ears] 在听（{self.model} · 麦克风来自浏览器，带回声消除）")

            async def pump():
                while True:
                    chunk = await queue.get()
                    await conn.input_audio_buffer.append(audio=base64.b64encode(chunk).decode())

            pumper = asyncio.create_task(pump())

            async def heartbeat():  # 每 30 秒报一次流量，没声音的时候一眼能看出是哪一段断了
                while True:
                    await asyncio.sleep(30)
                    self.on_status(f"[ears] 30 秒内：麦克风帧 {stats['frames']}（有响声的 {stats['loud']}）"
                                   f"，开口 {stats['started']} 次，转写 {stats['said']} 条")
                    for k in stats:
                        stats[k] = 0

            beater = asyncio.create_task(heartbeat())
            partial: dict[str, str] = {}  # item_id -> 已经吐出来的字
            try:
                receiver = conn.__aiter__()
                incoming = asyncio.create_task(anext(receiver))
                while True:
                    done, _ = await asyncio.wait({incoming, pumper}, timeout=parameter("ears.stream_poll_seconds"),
                                                 return_when=asyncio.FIRST_COMPLETED)
                    if pumper in done:
                        pumper.result()
                        raise ConnectionError("audio upload stopped")
                    if time.monotonic() - voice_at[0] < parameter("ears.voice_activity_tail_seconds"):
                        yield ("activity",)
                    if incoming not in done:
                        continue
                    try:
                        ev = incoming.result()
                    except StopAsyncIteration:
                        raise ConnectionError("transcription connection closed")
                    incoming = asyncio.create_task(anext(receiver))
                    if ev.type == "input_audio_buffer.speech_started":
                        stats["started"] += 1
                        yield ("started", ev.item_id)
                    elif ev.type == "input_audio_buffer.speech_stopped":
                        yield ("stopped", ev.item_id)
                    elif ev.type == "conversation.item.input_audio_transcription.delta":
                        partial[ev.item_id] = partial.get(ev.item_id, "") + (ev.delta or "")
                        yield ("partial", partial[ev.item_id])
                    elif ev.type == "conversation.item.input_audio_transcription.completed":
                        partial.pop(ev.item_id, None)
                        stats["said"] += 1
                        yield ("said", ev.transcript or "", ev.item_id)
                    elif ev.type == "conversation.item.input_audio_transcription.failed":
                        partial.pop(ev.item_id, None)
                        yield ("failed", ev.item_id)
                    elif ev.type == "error":
                        self.on_status(f"[ears] 服务端错误：{ev.error.message}")
            finally:
                incoming.cancel()
                pumper.cancel()
                beater.cancel()
                if feeder is not None:
                    feeder.cancel()
                await asyncio.gather(incoming, pumper, beater, *([feeder] if feeder else []), return_exceptions=True)
                if stream is not None:
                    stream.stop()
                    stream.close()
