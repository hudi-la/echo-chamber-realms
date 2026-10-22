""""有没有人"的信号源 —— 可插拔。

规则：一件我们自己都没把握的事，不当事实说给木偶听。

- `source = "none"`（默认）：没有可靠来源。木偶**不被告知**有人来了或走了；靠人声的猜测（`session.VisitorTracker`）
  只在幕后管两件事 —— 安静的节奏切档、什么时候落一颗星 / 触发反刍。
- 其它来源（压力垫、摄像头、人体感应…）：接上后把 config 里 `source` 改成对应名字，来源在人进来 / 出去时
  调用 `room.presence_changed(True / False)`。这时"新朋友 来了 / 走了"是事实，会写进木偶看到的现场 ——
  打不打招呼、谁先打，仍然是它们自己的事。

接一个新来源 = 写一个类，实现下面这个协议，在 `__main__` 里按 source 名字挂上。"""
from typing import Protocol


class PresenceSource(Protocol):
    async def run(self, room) -> None:
        """长跑；观察硬件，在状态变化时 await room.presence_changed(present)。"""
        ...
