"""木偶机构（阶段 4，Arduino 还没接）。现在只有关闭模式：打印。
三态：说话 / 静默 / 躁动 —— 串口协议沿用 legacy/tools.py：1/2/3 = Charlie/Kaka/Lucy 开始动，4/5/6 = 停；
躁动 = 短促脉冲，是否启用等实测机构惯性。"""
from typing import Callable, Protocol


class Motors(Protocol):
    async def speaking(self, name: str) -> None: ...
    async def silent(self, name: str) -> None: ...
    async def restless(self, name: str) -> None: ...


class PrintMotors:
    def __init__(self, out: Callable[[str], None] = print) -> None:
        self.out = out
        self.log: list[tuple[str, str]] = []

    async def speaking(self, name: str) -> None:
        self.log.append(("speaking", name))
        self.out(f"[motors] {name} 动")

    async def silent(self, name: str) -> None:
        self.log.append(("silent", name))
        self.out(f"[motors] {name} 停")

    async def restless(self, name: str) -> None:
        self.log.append(("restless", name))
        self.out(f"[motors] {name} 躁动")
