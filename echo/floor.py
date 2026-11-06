"""发言锁。任何时刻至多一个持有者：某只木偶，或者人。人有绝对优先权。"""
import asyncio
import random
import re
from .settings import parameters, rule
from typing import Awaitable, Callable

HUMAN = "新朋友"
StopFn = Callable[[], Awaitable[str]]



def addressed_character(text: str) -> str | None:
    """Only an unambiguous opening address; no model request or semantic guess."""
    mentioned = [name for name, aliases in rule('aliases').items()
                 if any(re.search(re.escape(a) + (r"(?![a-zA-Z])" if a.isascii() else ""), text, re.I) for a in aliases)]
    if len(mentioned) != 1:
        return None
    name = mentioned[0]
    aliases = "|".join(re.escape(a) for a in rule('aliases')[name])
    return name if re.match(r"^[啊诶哎嘿嗨，,\s]*(?:请问[，,\s]*)?(?:" + aliases + r")(?![a-zA-Z])", text, re.I) else None


class Floor:
    def __init__(self, window: float | None = None, sleep=asyncio.sleep) -> None:
        self.window, self._sleep = parameters()["defaults"]["room"]["turn_window"] if window is None else window, sleep
        self.holder: str | None = None
        self._stop: StopFn | None = None
        self._candidates = {}
        self._round = None
        self._generation = 0
        self._last_winner = None

    async def request(self, name: str, stop: StopFn, preferred: bool = False) -> bool:
        """程序登记可接话角色；点名优先，其余随机且上一位让位。"""
        if not self.free:
            return False
        future = asyncio.get_running_loop().create_future()
        self._candidates[name] = (stop, future, preferred)
        if self._round is None:
            self._round = asyncio.create_task(self._settle(self._generation))
        try:
            return await future
        finally:
            if self._candidates.get(name, (None, None))[1] is future:
                self._candidates.pop(name, None)

    async def _settle(self, generation):
        # One event-loop yield registers all subscribers without a timed AI window.
        await self._sleep(self.window)
        candidates, self._candidates = self._candidates, {}
        self._round = None
        eligible = [n for n, (_, f, _) in candidates.items() if not f.done()]
        winner = None
        if self.free and generation == self._generation and eligible:
            addressed = [n for n in eligible if candidates[n][2]] if rule("conversation.prefer_named_character") else []
            choices = addressed or ([n for n in eligible if n != self._last_winner]
                                    if rule("conversation.avoid_repeat_speaker") else eligible) or eligible
            winner = random.choice(choices) if rule("conversation.selection") == "random" else choices[0]
            self.try_acquire(winner, candidates[winner][0])
            self._last_winner = winner
        for name, (_, future, _) in candidates.items():
            if not future.done():
                future.set_result(name == winner)

    @property
    def free(self) -> bool:
        return self.holder is None

    def try_acquire(self, name: str, stop: StopFn) -> bool:
        """木偶抢锁。先到先得；stop 是"你被打断时我怎么让你闭嘴"，返回已说出的前缀。"""
        if self.holder is not None:
            return False
        self.holder, self._stop = name, stop
        return True

    def release(self, name: str) -> None:
        if self.holder == name:
            self.holder, self._stop = None, None

    async def seize_by_human(self) -> tuple[str, str] | None:
        """人开口了。若某只木偶在说，让它停，返回 (名字, 已说出的前缀)。"""
        self._generation += 1
        prev, stop = self.holder, self._stop
        self.holder, self._stop = HUMAN, None
        if prev is None or prev == HUMAN:
            return None
        spoken = await stop() if stop else ""
        return prev, spoken

    def release_human(self) -> None:
        if self.holder == HUMAN:
            self.holder = None
