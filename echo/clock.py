"""一切时间都从这儿来。生产用 Clock，测试用 FakeClock，任何组件不得直接 import time/asyncio.sleep。"""
import asyncio
import time
from datetime import date, datetime


class Clock:
    def now(self) -> float:
        return time.monotonic()

    def wall(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def today(self) -> str:
        return date.today().isoformat()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeClock(Clock):
    def __init__(self, start: float = 0.0, today: str = "2026-09-05") -> None:
        self._now = start
        self._today = today
        self._waiters: list[tuple[float, asyncio.Future]] = []

    def now(self) -> float:
        return self._now

    def wall(self) -> str:
        return f"{self._today}T+{self._now:.0f}s"

    def today(self) -> str:
        return self._today

    def set_today(self, day: str) -> None:
        self._today = day

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        fut = asyncio.get_running_loop().create_future()
        waiter = (self._now + seconds, fut)
        self._waiters.append(waiter)
        try:
            await fut
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    async def advance(self, seconds: float) -> None:
        for _ in range(3):
            await asyncio.sleep(0)  # 先让刚创建的任务把它们的 sleep 登记上，再开始推进
        target = self._now + seconds
        while True:
            due = [w for w in self._waiters if w[0] <= target]
            if not due:
                break
            wake_at, fut = min(due, key=lambda w: w[0])
            self._waiters.remove((wake_at, fut))
            self._now = wake_at
            if not fut.done():
                fut.set_result(None)
            for _ in range(3):
                await asyncio.sleep(0)  # 让被唤醒的任务跑起来（它可能又 sleep 了）
        self._now = target
        for _ in range(3):
            await asyncio.sleep(0)
