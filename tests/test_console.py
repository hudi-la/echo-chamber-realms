from echo.console import Console


class RoomSpy:
    def __init__(self):
        self.calls = []

    async def human_started(self):
        self.calls.append("started")

    async def human_said(self, text):
        self.calls.append(("said", text))


async def test_console_line_is_started_then_said():
    lines = iter(["你们好\n", "  \n", "再见\n", None])

    async def readline():
        return next(lines)

    spy = RoomSpy()
    await Console(spy, readline).run()
    assert spy.calls == ["started", ("said", "你们好"), "started", ("said", "再见")]


async def test_console_dot_opens_mouth_first():
    lines = iter([".\n", ".\n", "等等\n", "又一句\n", None])

    async def readline():
        return next(lines)

    spy = RoomSpy()
    await Console(spy, readline).run()
    assert spy.calls == ["started", ("said", "等等"), "started", ("said", "又一句")]
