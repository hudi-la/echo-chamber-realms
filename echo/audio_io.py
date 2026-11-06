"""音频进出走浏览器：麦克风在浏览器里抓（自带声学回声消除 AEC），木偶的声音也从浏览器放。
引擎这边只多两样东西：一个从浏览器收麦克风帧的队列，一个把 PCM 发给浏览器播的 Player。

为什么：Mac 内置麦 + 扬声器下，用 PortAudio 抓的原始麦克风流没有回声消除，木偶会被自己的声音打断
（2026-09-25 实测）。浏览器的 WebRTC 音频栈有成熟的 AEC —— 它知道自己在放什么，能从麦克风里减掉。
ChatGPT 语音聊天不会自己打断自己，靠的就是这个，不是模型。"""

from .settings import parameter
import asyncio
import base64
import time
from typing import AsyncIterator, Callable

import numpy as np

RATE = 24000


class BrowserMic:
    """浏览器送来的麦克风帧（int16 24k 单声道，二进制 WebSocket 消息）。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue = asyncio.Queue()
        self.connected = False
        self.max_bytes = int(RATE * 2 * parameter("audio.mic_queue_seconds"))  # 最多一秒 PCM；断网后不补播旧人声
        self._queued_bytes = 0
        self.dropped_bytes = 0

    def disconnect(self):
        self.connected = False
        while not self._queue.empty():
            self._queue.get_nowait()
        self._queued_bytes = 0

    def push(self, frame: bytes) -> None:
        self.connected = True
        frame = frame[-self.max_bytes:]
        while self._queued_bytes + len(frame) > self.max_bytes:
            dropped = len(self._queue.get_nowait())
            self._queued_bytes -= dropped
            self.dropped_bytes += dropped
        self._queue.put_nowait(frame)
        self._queued_bytes += len(frame)

    async def frames(self) -> AsyncIterator[bytes]:
        while True:
            frame = await self._queue.get()
            self._queued_bytes -= len(frame)
            yield frame


class BrowserPlayer:
    """PCM 发给唯一音频页面；开始/结束由页面确认，失联有有界超时。"""

    def __init__(self, send: Callable[[dict], None], now: Callable[[], float] = time.monotonic,
                 log: Callable[[str], None] | None = None) -> None:
        self._send, self._now, self._log = send, now, log
        self._until = 0.0
        self._seq = 0
        self._active = False
        self._started = None
        self._duration = 0.0
        self._failure = None

    def acknowledge(self, msg):
        if msg.get("id") != self._seq or not self._active:
            return
        if msg.get("type") == "play_started":
            self._started = self._now()
            self._until = self._now() + self._duration + parameter("speech.browser_end_grace")
        elif msg.get("type") in ("play_ended", "play_error"):
            if msg["type"] == "play_error":
                self._failure = "browser playback failed"
            self._active = False

    def disconnect(self):
        if self._active:
            self._failure = "audio browser disconnected"
        self._active = False

    @property
    def playback_started(self):
        return self._started is not None

    def progress(self):
        if self._started is None:
            return 0.0
        return min(1.0, max(0.0, (self._now() - self._started) / max(self._duration, 0.001)))

    def play(self, pcm, sr: int, pan: tuple[float, float]) -> None:
        pcm16 = (np.clip(np.asarray(pcm, dtype=np.float32), -1.0, 1.0) * 32767).astype(np.int16)
        self._seq += 1
        self._duration = len(pcm16) / sr
        self._until = self._now() + parameter("speech.browser_start_timeout")  # 等真实开始确认，不能凭发送时间算已播放
        self._active, self._started, self._failure = True, None, None
        if self._log:
            self._log(f"  [嘴→浏览器] 第 {self._seq} 段，{len(pcm16) / sr:.1f} 秒，声像 {list(pan)}")
        self._send({"type": "play", "id": self._seq, "sr": sr, "pan": list(pan),
                    "pcm": base64.b64encode(pcm16.tobytes()).decode()})

    def busy(self) -> bool:
        if self._active and self._now() >= self._until:
            self._failure = "browser playback acknowledgement timed out"
            self._active = False
            self._send({"type": "stop"})
        if self._failure:
            failure, self._failure = self._failure, None
            raise RuntimeError(failure)
        return self._active

    def stop(self) -> None:
        self._until = 0.0
        self._active, self._failure = False, None
        self._send({"type": "stop"})
