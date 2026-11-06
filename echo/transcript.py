"""现场记录：只增不减的流水，和"渲染成木偶看到的样子"。渲染只陈述事实。"""

from .settings import parameter
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Entry:
    at: float
    wall: str
    kind: str  # said | cut | arrived | left | woke
    who: str
    text: str = ""


def _ago(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds} 秒"
    return f"{seconds // 60} 分钟"


class Transcript:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.entries: list[Entry] = []

    def add(self, at: float, wall: str, kind: str, who: str, text: str = "") -> Entry:
        entry = Entry(at, wall, kind, who, text)
        self.entries.append(entry)
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return entry

    def render(self, *, now: float, me: str, speaker: str | None, last_spoke_at: float | None,
               quiet_for: float, window: int, show_presence: bool = False, language: str = "zh") -> str:
        """木偶看到的现场。只写它们确切知道的事：谁说了什么、谁在说、安静了多久。
        天数、开关机不给它们看（那是墙的事）；"来了/走了"只在有可靠来源时才是事实（show_presence）。"""
        lines: list[str] = []
        for e in self.entries[-window:]:
            rel = f"(-{int(now - e.at)}s)"
            who = (f"you ({me})" if language == "en" else f"你（{me}）") if e.who == me else e.who
            if language == "en" and who == "新朋友":
                who = "Visitor"
            if e.kind == "said":
                lines.append(f"{rel} {who}：{e.text}")
            elif e.kind == "cut":
                lines.append(f"{rel} {who}：{e.text}（被打断）")
            elif e.kind == "arrived" and show_presence:
                lines.append(f"{rel} 新朋友 来了")
            elif e.kind == "left" and show_presence:
                lines.append(f"{rel} 新朋友 走了")
        if speaker is not None:
            status = f"(现在) {speaker} 正在说。"
        elif quiet_for >= parameter("transcript.show_quiet_after_seconds"):
            status = f"(现在) 没人在说，已经安静 {int(quiet_for)} 秒。"
        else:
            status = "(现在) 没人在说。"
        if last_spoke_at is not None:  # 不知道就不说（开机后第一轮不写"你还没开过口"，那不是真的）
            status += f"你上一次开口是 {_ago(now - last_spoke_at)}前。"
        if language == "en":
            status = f"(now) {speaker} is speaking." if speaker else (f"(now) Nobody is speaking; quiet for {int(quiet_for)} seconds." if quiet_for >= parameter("transcript.show_quiet_after_seconds") else "(now) Nobody is speaking.")
            if last_spoke_at is not None:
                status += f" You last started speaking {int(now - last_spoke_at)} seconds ago."
            lines = [line.replace("（被打断）", " (interrupted)").replace("新朋友 来了", "Visitor arrived").replace("新朋友 走了", "Visitor left") for line in lines]
        lines.append(status)
        return "\n".join(lines)
