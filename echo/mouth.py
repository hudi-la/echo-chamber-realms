"""嘴。两种：PrintMouth（关闭模式：打印 + 按字数睡眠）和 TtsMouth（真声音：合成 → 升调 → 分声道播放）。
两种对引擎一样：say() 可被 stop() 掐断，返回已说出的前缀。"""
import asyncio
import io
import re
import time
from collections import deque
from typing import Awaitable, Callable, Protocol

from .clock import Clock


class Mouth(Protocol):
    async def say(self, name: str, text: str) -> tuple[str, bool]: ...
    async def stop(self) -> str: ...


class _Recent:
    """嘴最近说过的话（带结束时间），耳朵用来识别"自听"：麦克风听见的会比播放晚一两秒。"""

    def __init__(self) -> None:
        self.current: str | None = None
        self._done: deque = deque(maxlen=6)  # (text, ended_at)

    def begin(self, text: str) -> None:
        self.current = text

    def end(self) -> None:
        if self.current is not None:
            self._done.append((self.current, time.monotonic()))
        self.current = None

    @property
    def playing(self) -> bool:
        return self.current is not None

    def text(self, within: float = 8.0) -> str | None:
        """正在放的 + 最近 within 秒内放完的，拼成一段。"""
        now = time.monotonic()
        parts = [t for t, ended in self._done if now - ended <= within]
        if self.current:
            parts.append(self.current)
        return "\n".join(parts) if parts else None


# ---------- 关闭模式 ----------

class PrintMouth:
    def __init__(self, clock: Clock, chars_per_second: float = 6.0,
                 out: Callable[[str], None] = print) -> None:
        self.clock, self.cps, self.out = clock, chars_per_second, out
        self._stop_requested: asyncio.Event | None = None
        self._ack: asyncio.Event | None = None
        self._prefix = ""
        self.recent = _Recent()

    async def say(self, name: str, text: str) -> tuple[str, bool]:
        self.out(f"@{name}: {text}")
        self.recent.begin(text)
        self._stop_requested, self._ack, self._prefix = asyncio.Event(), asyncio.Event(), ""
        duration = max(len(text) / self.cps, 0.1)
        start = self.clock.now()
        sleeper = asyncio.ensure_future(self.clock.sleep(duration))
        stopper = asyncio.ensure_future(self._stop_requested.wait())
        try:
            done, _ = await asyncio.wait({sleeper, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in (sleeper, stopper):
                if not t.done():
                    t.cancel()
        if stopper in done:
            frac = min((self.clock.now() - start) / duration, 1.0)
            self._prefix = text[: int(len(text) * frac)]
            self.out(f"@{name}: …（被打断）")
            self._ack.set()
            result = (self._prefix, False)
        else:
            result = (text, True)
        self._stop_requested = self._ack = None
        self.recent.end()
        return result

    async def stop(self) -> str:
        if self._stop_requested is None:
            return ""
        req, ack = self._stop_requested, self._ack
        req.set()
        await ack.wait()
        return self._prefix


# ---------- 真声音 ----------

_SENTENCE_END = re.compile(r"(?<=[。！？!?；;\n])")
_STAGE_DIRECTION = re.compile(r"[（(][^）)]*[）)]")


def split_sentences(text: str) -> list[str]:
    """按句号/问号/感叹号切句，太短的碎片并回上一句。嘴一句一句合成、一句一句播。"""
    parts = [p.strip() for p in _SENTENCE_END.split(text)]
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        if out and len(p) <= 2:
            out[-1] += p
        else:
            out.append(p)
    return out


def speakable(sentence: str) -> str:
    """去掉括号里的舞台提示（"（沉默了一会儿）"），嘴只念括号外的。"""
    return _STAGE_DIRECTION.sub("", sentence).strip()


Audio = tuple  # (numpy float32 单声道, 采样率)
Synth = Callable[[str, str], Awaitable[Audio | None]]  # (name, sentence) -> 音频；失败返回 None


class Player(Protocol):
    def play(self, pcm, sr: int, pan: tuple[float, float]) -> None: ...
    def busy(self) -> bool: ...
    def stop(self) -> None: ...


class TtsMouth:
    """一句一句来：播第 i 句的时候已经在合成第 i+1 句。stop() 立即静音，返回已说出的前缀。"""

    def __init__(self, synth: Synth, player: Player, pan: dict[str, tuple[float, float]],
                 out: Callable[[str], None] = print, fallback_cps: float = 6.0) -> None:
        self.synth, self.player, self.pan, self.out, self.fallback_cps = synth, player, pan, out, fallback_cps
        self._stop_evt: asyncio.Event | None = None
        self._ack: asyncio.Event | None = None
        self._prefix = ""
        self.recent = _Recent()
        self.performance = None

    async def _prepare(self, name: str, sentence: str) -> Audio | None:
        text = speakable(sentence)
        if not text:
            return None
        return await self.synth(name, text)

    async def say(self, name: str, text: str) -> tuple[str, bool]:
        self.out(f"@{name}: {text}")
        self._stop_evt, self._ack, self._prefix = asyncio.Event(), asyncio.Event(), ""
        sentences = split_sentences(text) or [text]
        spoken: list[str] = []
        completed = True
        pending = asyncio.create_task(self._prepare(name, sentences[0]))
        try:
            for i, sentence in enumerate(sentences):
                stopper = asyncio.create_task(self._stop_evt.wait())
                try:
                    done, _ = await asyncio.wait({pending, stopper}, timeout=20,
                                                 return_when=asyncio.FIRST_COMPLETED)
                    if stopper in done:
                        completed = False
                        break
                    if pending not in done:
                        raise TimeoutError("TTS synthesis timed out")
                    audio = pending.result()
                finally:
                    stopper.cancel()
                pending = (asyncio.create_task(self._prepare(name, sentences[i + 1]))
                           if i + 1 < len(sentences) else None)
                if self._stop_evt.is_set():
                    completed = False
                    break
                started = time.monotonic()
                if audio is None:
                    if speakable(sentence):
                        raise RuntimeError("TTS returned no audio")
                    continue
                else:
                    pcm, sr = audio
                    duration = max(len(pcm) / sr, 0.05)
                    self.recent.begin(sentence)
                    self.player.play(pcm, sr, self.pan.get(name, (0.5, 0.5)))
                    acting = False
                    try:
                        while self.player.busy() and not self._stop_evt.is_set():
                            if self.performance and not acting and getattr(self.player, "playback_started", True):
                                acting = True
                                self.performance.start(name, text, i, duration)
                            if self.performance and acting:
                                self.performance.tick()
                            await asyncio.sleep(0.03)
                    finally:
                        if self.performance:
                            self.performance.stop()
                if self._stop_evt.is_set():
                    frac = (self.player.progress() if audio is not None and hasattr(self.player, "progress")
                            else min((time.monotonic() - started) / duration, 1.0))
                    spoken.append(sentence[: int(len(sentence) * frac)])
                    completed = False
                    break
                spoken.append(sentence)
                self.recent.end()
        except BaseException:
            completed = False
            raise
        finally:
            if pending is not None:
                if not pending.done():
                    pending.cancel()
                elif not pending.cancelled():
                    pending.exception()
            if self._stop_evt.is_set():
                completed = False
            if not completed:
                self.player.stop()
                self.out(f"@{name}: …（被打断）")
            self._prefix = text if completed else "".join(spoken)
            self._ack.set()
            self.recent.end()
            self._stop_evt = self._ack = None
        return self._prefix, completed

    async def stop(self) -> str:
        if self._stop_evt is None:
            return ""
        evt, ack = self._stop_evt, self._ack
        evt.set()
        self.player.stop()
        await ack.wait()
        return self._prefix


class OpenAISynth:
    """OpenAI TTS → 解码 → librosa 升调（沿用原来的做法）。"""

    def __init__(self, client, model: str, voices: dict[str, str], pitch: dict[str, float],
                 instructions: dict[str, str] | None = None, playback_speed: float = 1.0) -> None:
        self.playback_speed = playback_speed
        self.client, self.model, self.voices, self.pitch = client, model, voices, pitch
        self.instructions = instructions or {}

    def warmup(self) -> None:
        """librosa 第一次调用要编译两三秒，开机先跑一次，别让第一句话卡住。"""
        import numpy as np
        import librosa
        librosa.effects.pitch_shift(np.full(24000, 1e-4, dtype="float32"), sr=24000, n_steps=6)

    def _decode_and_shift(self, data: bytes, steps: float, playback_speed: float = 1.0) -> Audio:
        import numpy as np
        import soundfile as sf
        y, sr = sf.read(io.BytesIO(data), dtype="float32")
        if y.ndim > 1:
            y = y.mean(axis=1)
        if steps:
            import librosa
            y = librosa.effects.pitch_shift(y, sr=sr, n_steps=steps)
        # Faster sample clock raises both tempo and pitch; no pitch-preserving stretch.
        return np.nan_to_num(y).astype("float32"), round(sr * playback_speed)

    async def __call__(self, name: str, text: str) -> Audio | None:
        import openai
        kwargs = dict(model=self.model, voice=self.voices[name], input=text, response_format="wav")
        if self.instructions.get(name):
            kwargs["instructions"] = self.instructions[name]
        try:
            r = await self.client.audio.speech.create(**kwargs)
            data = await r.aread() if hasattr(r, "aread") else r.content
        except (openai.APIConnectionError, openai.APIStatusError) as e:
            print(f"[mouth] TTS 失败，本轮不计作已说完: {e}")
            return None
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._decode_and_shift, data, self.pitch.get(name, 0), self.playback_speed)


class PygamePlayer:
    """本机扬声器（[audio] io = "local"）。浏览器模式用 audio_io.BrowserPlayer。"""

    def __init__(self) -> None:
        self._sr: int | None = None
        self._channel = None
        self._sound = None

    def _ensure(self, sr: int) -> None:
        import pygame
        if self._sr != sr:
            if pygame.mixer.get_init():
                pygame.mixer.quit()
            pygame.mixer.init(frequency=sr, size=-16, channels=2)
            self._sr = sr

    def play(self, pcm, sr: int, pan: tuple[float, float]) -> None:
        import numpy as np
        import pygame
        self._ensure(sr)
        i16 = (np.clip(pcm, -1.0, 1.0) * 32767).astype(np.int16)
        stereo = np.ascontiguousarray(np.repeat(i16[:, None], 2, axis=1))
        self._sound = pygame.sndarray.make_sound(stereo)
        self._channel = self._sound.play()
        if self._channel is not None:
            self._channel.set_volume(*pan)

    def busy(self) -> bool:
        return bool(self._channel is not None and self._channel.get_busy())

    def stop(self) -> None:
        import pygame
        if pygame.mixer.get_init():
            pygame.mixer.stop()
