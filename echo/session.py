"""一场到访。开始和结束由两种方式之一决定：
- 有可靠的"有没有人"来源（presence.py）：来源说了算，begin() / end()。
- 没有：靠人声猜 —— 第一句人声算开始；结束靠一口安静钟（只在"没有任何人在说"时计时）加一个保底。"""


class VisitorTracker:
    def __init__(self) -> None:
        self.present = False
        self.last_human_at: float | None = None
        self.session_id: str | None = None
        self.silence = 0.0  # 自上一句人声以来，房间里真正安静的秒数

    # --- 两种方式都用 ---

    def note_human(self, now: float) -> None:
        self.last_human_at = now
        self.silence = 0.0

    def begin(self, wall: str) -> None:
        self.present, self.session_id, self.silence = True, wall, 0.0

    def end(self) -> str | None:
        ended, self.present, self.session_id, self.silence = self.session_id, False, None, 0.0
        return ended

    # --- 只有靠人声猜的时候用 ---

    def saw_human(self, now: float, wall: str) -> bool:
        """返回 True = 新的一场开始了。"""
        self.note_human(now)
        if self.present:
            return False
        self.begin(wall)
        return True

    def tick(self, dt: float, room_silent: bool) -> None:
        """每拍调一次。只有房间安静（没人也没木偶在说）时，安静钟才走。"""
        if self.present and room_silent:
            self.silence += dt

    def check_left(self, now: float, timeout: float, hard_timeout: float) -> str | None:
        if not self.present or self.last_human_at is None:
            return None
        if self.silence < timeout and now - self.last_human_at < hard_timeout:
            return None
        return self.end()
