"""键盘替身。发出和耳朵一模一样的事件：一行 = 开口 + 说完；单独一个 "." = 只开口（测打断）。

读 stdin 用一个 daemon 线程：2026-09-26 发现引擎异常退出时，进程会卡在等这个线程结束（它阻塞在 readline 上），
永远退不出去，端口还开着、页面连不上、看起来像"活着但不听"。daemon 线程不会挡退出。"""
import asyncio
import sys
import threading
from typing import Awaitable, Callable

ReadLine = Callable[[], Awaitable[str | None]]


class _StdinLines:
    """后台 daemon 线程读 stdin，一行一行塞进 asyncio 队列；EOF 塞 None。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue | None = None
        self._thread: threading.Thread | None = None

    def _start(self, loop: asyncio.AbstractEventLoop) -> None:
        q = self._queue = asyncio.Queue()

        def reader() -> None:
            while True:
                line = sys.stdin.readline()
                loop.call_soon_threadsafe(q.put_nowait, line if line else None)
                if not line:
                    return

        self._thread = threading.Thread(target=reader, name="stdin-reader", daemon=True)
        self._thread.start()

    async def readline(self) -> str | None:
        if self._queue is None:
            self._start(asyncio.get_running_loop())
        return await self._queue.get()


class Console:
    def __init__(self, room, readline: ReadLine | None = None) -> None:
        self.room = room
        self._readline = readline or _StdinLines().readline
        self._open = False  # 已经发过"开口"、还没发"说完"

    async def run(self) -> None:
        while True:
            line = await self._readline()
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            if line == ".":
                if not self._open:
                    await self.room.human_started()
                    self._open = True
                continue
            if not self._open:
                await self.room.human_started()
            self._open = False
            await self.room.human_said(line)
