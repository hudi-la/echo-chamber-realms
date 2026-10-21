"""房间：事件总线、现场记录、发言锁的人类优先、沉默计时、到访起止。不决定谁该说。"""
import asyncio
from typing import Callable

from .clock import Clock
from .config import Config
from .events import (Event, HumanSaid, HumanStarted, PuppetCut, PuppetSaid, PuppetStarted,
                     Quiet, VisitorArrived, VisitorLeft, WokeUp)
from .floor import HUMAN, Floor
from .session import VisitorTracker
from .transcript import Transcript


class Room:
    def __init__(self, clock: Clock, transcript: Transcript, floor: Floor,
                 cfg: Callable[[], Config], presence_reliable: bool = False) -> None:
        self.clock, self.transcript, self.floor, self.cfg = clock, transcript, floor, cfg
        self.presence_reliable = presence_reliable  # True = 有硬件来源，"来了/走了"是事实，会告诉木偶
        self.visitor = VisitorTracker()
        self.day = 0
        self.last_activity = clock.now()
        self._last_quiet = clock.now()
        self._subs: list[asyncio.Queue] = []

    # --- 订阅与发布 ---

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(q)
        return q

    @property
    def speaker(self) -> str | None:
        return self.floor.holder

    async def publish(self, ev: Event) -> None:
        wall = self.clock.wall()
        if isinstance(ev, HumanSaid):
            self.transcript.add(ev.at, wall, "said", HUMAN, ev.text)
            self.last_activity = ev.at
        elif isinstance(ev, PuppetSaid):
            self.transcript.add(ev.at, wall, "said", ev.name, ev.text)
            self.last_activity = ev.at
        elif isinstance(ev, PuppetCut):
            self.transcript.add(ev.at, wall, "cut", ev.name, ev.spoken)
            self.last_activity = ev.at
        elif isinstance(ev, VisitorArrived):
            self.transcript.add(ev.at, wall, "arrived", HUMAN)
        elif isinstance(ev, VisitorLeft):
            self.transcript.add(ev.at, wall, "left", HUMAN)
        elif isinstance(ev, WokeUp):
            self.transcript.add(ev.at, wall, "woke", "", str(ev.day))
        elif isinstance(ev, (HumanStarted, PuppetStarted)):
            self.last_activity = ev.at
        for q in self._subs:
            q.put_nowait(ev)

    # --- 人 ---

    async def wake(self, day: int) -> None:
        self.day = day
        await self.publish(WokeUp(self.clock.now(), day))

    async def human_started(self) -> None:
        now = self.clock.now()
        cut = await self.floor.seize_by_human()
        await self.publish(HumanStarted(now))
        if cut is not None:
            name, spoken = cut
            await self.publish(PuppetCut(now, name, spoken))

    async def human_said(self, text: str) -> None:
        if self.floor.holder != HUMAN:
            await self.human_started()
        now = self.clock.now()
        self.floor.release_human()
        if self.presence_reliable:
            self.visitor.note_human(now)
        elif self.visitor.saw_human(now, self.clock.wall()):
            await self.publish(VisitorArrived(now))
        await self.publish(HumanSaid(now, text))

    # --- 可靠的"有没有人"来源从这里进来（presence.py）---

    async def presence_changed(self, present: bool) -> None:
        now = self.clock.now()
        if present and not self.visitor.present:
            self.visitor.begin(self.clock.wall())
            await self.publish(VisitorArrived(now))
        elif not present and self.visitor.present:
            ended = self.visitor.end()
            await self.publish(VisitorLeft(now, ended or ""))

    # --- 计时 ---

    async def run(self) -> None:
        while True:
            await self.clock.sleep(1.0)
            now = self.clock.now()
            c = self.cfg()
            if not self.presence_reliable:
                self.visitor.tick(1.0, room_silent=self.floor.free)
                ended = self.visitor.check_left(now, c.visitor_timeout, c.visitor_hard_timeout)
                if ended is not None:
                    await self.publish(VisitorLeft(now, ended))
            interval = c.quiet_interval_with_visitor if self.visitor.present else c.quiet_interval_alone
            since = now - self.last_activity
            if self.floor.free and since >= interval and now - self._last_quiet >= interval:
                self._last_quiet = now
                await self.publish(Quiet(now, since))
