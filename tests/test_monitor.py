import asyncio
from pathlib import Path

from echo.config import parse_config
from echo.events import HumanSaid, PuppetCut, PuppetSaid, PuppetStarted, Quiet, VisitorLeft, WokeUp
from echo.floor import Floor
from echo.memory import ChangeLog, PuppetMemory
from echo.monitor import Monitor, event_to_msg
from echo.motors import PrintMotors
from echo.mouth import PrintMouth
from echo.puppet import Puppet
from echo.room import Room
from echo.transcript import Transcript
from tests.fakes import FakeBrain

CFG = parse_config("", base=Path("/tmp"))


def test_event_to_msg():
    assert event_to_msg(HumanSaid(1.0, "你好")) == {"type": "said", "who": "新朋友", "text": "你好"}
    assert event_to_msg(PuppetSaid(1.0, "Kaka", "哼")) == {"type": "said", "who": "Kaka", "text": "哼"}
    assert event_to_msg(PuppetCut(1.0, "Kaka", "哼")) == {"type": "cut", "who": "Kaka", "text": "哼"}
    assert event_to_msg(PuppetStarted(1.0, "Lucy", "我在")) == {"type": "started", "who": "Lucy", "text": "我在"}
    assert event_to_msg(Quiet(1.0, 12.7)) == {"type": "quiet", "seconds": 12}
    assert event_to_msg(VisitorLeft(1.0, "s1")) == {"type": "left", "session": "s1"}
    assert event_to_msg(WokeUp(1.0, 3)) == {"type": "woke", "day": 3}


class FakeWs:
    def __init__(self):
        self.sent = []

    async def send_json(self, msg):
        self.sent.append(msg)


async def test_monitor_broadcasts_events_logs_and_snapshot(clock, tmp_path):
    room = Room(clock, Transcript(), Floor(), lambda: CFG)
    mem = PuppetMemory.load("Kaka", tmp_path)
    mem.beliefs = ["我的羽毛就是我的论据"]
    puppet = Puppet("Kaka", "你是Kaka。", mem, FakeBrain(), room, PrintMouth(clock, out=lambda s: None),
                    PrintMotors(out=lambda s: None), clock, lambda: CFG, ChangeLog(tmp_path / "c.jsonl"))
    monitor = Monitor(room, [puppet])
    ws = FakeWs()
    monitor._clients.add(ws)
    pump = asyncio.create_task(monitor._pump())

    await room.wake(2)
    await room.human_said("你们好")
    monitor.log("  (Kaka 没开口)")
    for _ in range(6):
        await asyncio.sleep(0)

    types = [m["type"] for m in ws.sent]
    assert "woke" in types and "said" in types and "log" in types and "status" in types
    assert {"type": "log", "text": "(Kaka 没开口)"} in ws.sent
    status = [m for m in ws.sent if m["type"] == "status"][-1]
    assert status["day"] == 2 and status["visitor"] is True and status["speaker"] is None
    assert status["puppets"]["Kaka"]["beliefs"] == ["我的羽毛就是我的论据"]
    assert status["puppets"]["Kaka"]["last_spoke_ago"] is None
    history = [m["type"] for m in monitor._history]
    assert "status" not in history  # 快照不进历史
    assert "log" in history         # log 是同步写入的，顺序在事件泵之前
    assert [t for t in history if t != "log"] == ["woke", "human_started", "arrived", "said"]
    pump.cancel()
