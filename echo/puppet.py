"""一只木偶 = 一个循环。登记接话 → 程序选人 → 获选者写出有效台词 → 说；生成失败单独记录。"""
import asyncio
import re
from pathlib import Path
from typing import Callable

from .brain import Brain, Decision
from .clock import Clock
from .config import Config
from .events import Event, HumanSaid, PuppetCut, PuppetSaid, PuppetStarted, Quiet, VisitorLeft
from .memory import ChangeLog, PuppetMemory, append_jsonl
from .motors import Motors
from .mouth import Mouth, speakable
from .room import Room
from .floor import addressed_character

from .prompts import catalog, NEUTRAL  # noqa: F401 —— 集中在 prompts.py


class Puppet:
    def __init__(self, name: str, persona: str, memory: PuppetMemory, brain: Brain, room: Room,
                 mouth: Mouth, motors: Motors, clock: Clock, cfg: Callable[[], Config],
                 changelog: ChangeLog, sessions_path: Path | None = None,
                 log: Callable[[str], None] = print) -> None:
        self.name, self.persona, self.memory, self.brain = name, persona, memory, brain
        self.room, self.mouth, self.motors, self.clock, self.cfg = room, mouth, motors, clock, cfg
        self.changelog, self.sessions_path, self.log = changelog, sessions_path, log
        self.last_spoke_at: float | None = None
        self.speaking = False
        self._deciding: asyncio.Task | None = None
        self._speech_task: asyncio.Task | None = None
        self._audible = False
        self._ruminate_lock = asyncio.Lock()
        self._ruminations: set[asyncio.Task] = set()
        self._inbox = room.subscribe()  # 构造时就订阅，run() 还没轮到跑也不会漏事件

    # --- 它看到的世界 ---

    def system_prompt(self) -> str:
        parts = [self.persona.strip()]
        m = self.memory
        if m.beliefs:
            parts.append(catalog(self.cfg().prompt_language)["belief_heading"] + "\n" + "\n".join(f"- {b}" for b in m.beliefs))
        return "\n\n".join(parts)

    def situation(self) -> str:
        now = self.clock.now()
        return catalog(self.cfg().prompt_language)["recent_heading"] + "\n" + self.room.transcript.render(
            now=now, me=self.name, speaker=self.room.speaker, last_spoke_at=self.last_spoke_at,
            quiet_for=now - self.room.last_activity, window=self.cfg().window,
            show_presence=self.room.presence_reliable, language=self.cfg().prompt_language)

    # --- 循环 ---

    async def run(self) -> None:
        q = self._inbox
        try:
            while True:
                ev: Event = await q.get()
                batch = [ev]
                while not q.empty():
                    batch.append(q.get_nowait())
                for item in batch:
                    if isinstance(item, (HumanSaid, PuppetSaid, PuppetCut)):
                        self.memory.note_heard(self.clock.wall(), {"at": self.clock.wall(),
                            "who": "Visitor" if isinstance(item, HumanSaid) and self.cfg().prompt_language == "en" else ("新朋友" if isinstance(item, HumanSaid) else item.name),
                            "text": item.spoken if isinstance(item, PuppetCut) else item.text,
                            "cut": isinstance(item, PuppetCut)})
                ev = batch[-1]  # 合并反应，不丢记忆计数或离场事件
                ended = next((e.session_id for e in reversed(batch) if isinstance(e, VisitorLeft)), None)
                every = self.cfg().ruminate_every
                if ended is not None or (every > 0 and self.memory.heard >= every and not self._ruminations):
                    task = asyncio.create_task(self.ruminate(ended))
                    self._ruminations.add(task)
                    task.add_done_callback(self._ruminations.discard)
                if self.speaking:
                    continue
                if isinstance(ev, PuppetStarted):
                    continue  # 不取消已经在进行的自主决定。
                if isinstance(ev, (PuppetSaid, PuppetCut)) and ev.name == self.name:
                    # 自己刚说完（或刚被打断）不算"新事"：刚说完的人让一轮，等别人先。
                    # 别人都不接、安静下来（Quiet）或有人开口了，再轮到它决定 —— 这就是"没人接，原说话人才可以继续"。
                    continue
                if self._deciding is not None and not self._deciding.done():
                    if isinstance(ev, Quiet):
                        continue  # 安静提醒不包含新话，不重启尚未完成的决定。
                    self._deciding.cancel()
                preferred = isinstance(ev, HumanSaid) and addressed_character(ev.text) == self.name
                self._deciding = asyncio.create_task(self.consider(preferred=preferred))
        finally:
            tasks = [t for t in (self._deciding, self._speech_task, *self._ruminations) if t is not None]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _inner(self, d) -> str:
        bits = [b for b in (d.feeling and f"感受：{d.feeling}", d.intent and f"想：{d.intent}") if b]
        return " · ".join(bits)

    async def _stop_speech(self) -> str:
        if self._speech_task is not None and not self._audible:
            self._speech_task.cancel()
            await asyncio.gather(self._speech_task, return_exceptions=True)
            self.speaking = False
            return ""
        return await self.mouth.stop()

    async def consider(self, preferred: bool = False) -> None:
        """程序选人后只生成台词；不向模型请求 speak 判断。"""
        self.brain.language = self.cfg().prompt_language
        if not self.room.floor.free:
            return
        selection_started = self.clock.now()
        if not await self.room.floor.request(self.name, self._stop_speech, preferred=preferred):
            return
        system, situation = self.system_prompt(), self.situation()
        decision = Decision(True)  # Compatibility argument only; no decide() call.
        self.log(f"  ({self.name} 程序选中（{self.clock.now() - selection_started:.2f}s），开始写台词)")
        # 预留发言权写台词；此时尚未播放，人类开口会取消合成前的准备。
        self.speaking = True  # 现在就置位，免得下一件事又让它自己再决定一次
        self._speech_task = asyncio.create_task(self.speak_after_composing(system, situation, decision))

    async def speak_after_composing(self, system: str, situation: str, decision) -> None:
        generation = self.room.floor._generation
        compose_started = self.clock.now()
        try:
            text = await asyncio.wait_for(self.brain.compose(system, situation, decision), 15)
        except asyncio.CancelledError:
            self.room.floor.release(self.name)
            self.speaking = False
            self.log(f"  ({self.name} 还没说出口就被打断了)")
            return
        except Exception as e:  # 写台词失败不该把锁卡死
            self.log(f"  ({self.name} 写不出来：{e})")
            text = ""
        if self.room.floor.holder != self.name or generation != self.room.floor._generation:
            # 写台词的这一两秒里被人打断了：锁已经不在自己手里。话还没出口，就当没说
            self.speaking = False
            self.log(f"  ({self.name} 还没说出口就被打断了)")
            return
        text = text.strip() if isinstance(text, str) else ""
        if not re.search(r"\w", speakable(text)):
            self.room.floor.release(self.name)
            self.speaking = False
            self.log(f"  ({self.name} 台词生成失败：没有可朗读内容，本轮未播放)")
            return
        self.log(f"  ({self.name} 写台词耗时 {self.clock.now() - compose_started:.2f}s)")
        await self.speak(text)

    async def speak(self, text: str) -> None:
        self.speaking = True
        self._audible = True
        started = self.clock.now()
        self.last_spoke_at = started
        try:
            await self.room.publish(PuppetStarted(started, self.name, text))
            await self.motors.speaking(self.name)
            spoken, completed = await self.mouth.say(self.name, text)
            if completed:
                self.room.floor.release(self.name)
                await self.room.publish(PuppetSaid(self.clock.now(), self.name, text))
            # 被打断的情况：房间已经把锁给了人、记了 cut，这里什么都不用做
        except Exception as e:
            self.log(f"  ({self.name} 播放失败：{e})")
        finally:
            self.room.floor.release(self.name)
            self.speaking = False
            self._audible = False
            await self.motors.silent(self.name)

    # --- 反刍 ---

    async def seed_if_blank(self, preset: dict | None = None) -> bool:
        """Only initialize blank memories from reviewed presets; no model call."""
        if self.memory.beliefs:
            return False
        if preset:
            beliefs, how = preset.get("beliefs", []), "作者审定"
        else:
            data = catalog(self.cfg().prompt_language)["personas"][self.name]
            beliefs, how = data["initial_beliefs"], "reviewed preset"
        self.memory.apply_seed(beliefs, self.clock.wall(), self.cfg().belief_capacity, self.changelog)
        self.log(f"  ({self.name} 出厂信念（{how}）：" + "；".join(self.memory.beliefs) + ")")
        return True

    async def ruminate_if_pending(self) -> bool:
        """关机前的"睡前整理"：听够了、又有没消化的实际对话，才反刍一次。返回有没有做。"""
        if not self.memory.pending_experiences:
            return False
        if self.memory.heard < self.cfg().bedtime_min_heard:
            return False
        await self.ruminate(None, bedtime=True)
        return True

    async def ruminate(self, session_id: str | None, bedtime: bool = False) -> None:
        async with self._ruminate_lock:
            snapshot = (list(self.memory.thoughts), list(self.memory.unspoken), self.memory.heard)
            c = self.cfg()
            data = catalog(c.prompt_language)
            experiences = list(self.memory.pending_experiences)
            material = data["experience_heading"] + "\n" + "\n".join(
                f"[{e['at']}] {e['who']}: {e['text']}" +
                ((" (interrupted)" if c.prompt_language == "en" else "（被打断）") if e.get("cut") else "")
                for e in experiences)
            context = data["end"] if session_id else (data["bedtime"] if bedtime else data["daily"])
            material += "\n\n" + data["context_heading"] + context + "\n\n"
            material += data["ruminate"].format(
                impression_ask=data["impression"] if session_id else data["no_impression"],
                capacity=c.belief_capacity)
            self.brain.language = c.prompt_language
            result = await self.brain.ruminate(self.system_prompt(), material, c.belief_capacity)
            if result is None:
                return
            wall = self.clock.wall()
            impression = result.impression if session_id else ""
            accepted = self.memory.apply_changes(result.changes, impression, session_id,
                                                 wall, c.belief_capacity, self.changelog, consumed=snapshot,
                                                 consumed_experiences=experiences)
            for ch in accepted:
                what = f"对 {ch.who} 的看法" if ch.kind == "relation" else "信念"
                self.log(f"  ({self.name} 改了{what}：「{ch.old or '（新）'}」→「{ch.new}」，因为：{ch.because})")
            if not accepted:
                self.log(f"  ({self.name} 反思了一下，没有什么事分量够，信念不变)")
            if session_id and impression and self.sessions_path is not None:
                append_jsonl(self.sessions_path, {"session": session_id, "who": self.name,
                                                  "impression": impression, "at": wall})
