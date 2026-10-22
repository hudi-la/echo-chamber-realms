import asyncio
from pathlib import Path

from echo.config import parse_config
from echo.events import (HumanSaid, HumanStarted, PuppetCut, Quiet, VisitorArrived,
                         VisitorLeft, WokeUp)
from echo.floor import HUMAN, Floor
from echo.room import Room
from echo.transcript import Transcript

CFG = parse_config("""
[room]
quiet_interval_with_visitor = 8
quiet_interval_alone = 120
visitor_timeout = 75
visitor_hard_timeout = 300
""", base=Path("/tmp"))


def make_room(clock):
    return Room(clock, Transcript(), Floor(), lambda: CFG)


def drain(q: asyncio.Queue) -> list:
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


async def test_publish_fans_out_and_records(clock):
    room = make_room(clock)
    q1, q2 = room.subscribe(), room.subscribe()
    await room.wake(3)
    await room.human_said("你们好")
    assert [type(e) for e in drain(q1)] == [WokeUp, HumanStarted, VisitorArrived, HumanSaid]
    assert [type(e) for e in drain(q2)] == [WokeUp, HumanStarted, VisitorArrived, HumanSaid]
    assert [(e.kind, e.who, e.text) for e in room.transcript.entries] == [
        ("woke", "", "3"), ("arrived", "新朋友", ""), ("said", "新朋友", "你们好")]
    assert room.day == 3 and room.visitor.present


async def test_human_started_cuts_speaker(clock):
    room = make_room(clock)
    q = room.subscribe()

    async def stop() -> str:
        return "还用问"

    assert room.floor.try_acquire("Kaka", stop)
    await room.human_started()
    events = drain(q)
    assert [type(e) for e in events] == [HumanStarted, PuppetCut]
    assert events[1].name == "Kaka" and events[1].spoken == "还用问"
    assert room.floor.holder == HUMAN
    assert room.transcript.entries[-1].kind == "cut"
    await room.human_said("等等")
    assert room.floor.free


async def test_second_utterance_does_not_rearrive(clock):
    room = make_room(clock)
    q = room.subscribe()
    await room.human_said("一")
    await room.human_said("二")
    assert [type(e) for e in drain(q)] == [HumanStarted, VisitorArrived, HumanSaid, HumanStarted, HumanSaid]


async def test_quiet_fires_only_when_free_and_interval_depends_on_visitor(clock):
    room = make_room(clock)
    q = room.subscribe()
    runner = asyncio.create_task(room.run())
    await asyncio.sleep(0)

    await clock.advance(119)
    assert drain(q) == []
    await clock.advance(2)
    quiet = [e for e in drain(q) if isinstance(e, Quiet)]
    assert len(quiet) == 1 and quiet[0].seconds >= 120

    await room.human_said("在吗")
    drain(q)
    await clock.advance(9)
    assert any(isinstance(e, Quiet) for e in drain(q))  # 有人时 8 秒就算安静

    async def stop() -> str:
        return ""

    room.floor.try_acquire("Lucy", stop)
    await clock.advance(30)
    assert not any(isinstance(e, Quiet) for e in drain(q))  # 有人在说就不算安静
    runner.cancel()


async def test_visitor_leaves_after_timeout(clock):
    room = make_room(clock)
    q = room.subscribe()
    runner = asyncio.create_task(room.run())
    await asyncio.sleep(0)
    await room.human_said("你好")
    sid = room.visitor.session_id
    drain(q)
    await clock.advance(74)
    assert not any(isinstance(e, VisitorLeft) for e in drain(q))
    await clock.advance(2)
    left = [e for e in drain(q) if isinstance(e, VisitorLeft)]
    assert len(left) == 1 and left[0].session_id == sid
    assert room.transcript.entries[-1].kind == "left"
    runner.cancel()


async def test_listening_to_puppets_does_not_count_as_leaving(clock):
    room = make_room(clock)
    q = room.subscribe()
    runner = asyncio.create_task(room.run())
    await asyncio.sleep(0)
    await room.human_said("你好")
    drain(q)

    async def stop() -> str:
        return ""

    room.floor.try_acquire("Kaka", stop)   # Kaka 说了 100 秒，人在听
    await clock.advance(100)
    assert not any(isinstance(e, VisitorLeft) for e in drain(q))
    room.floor.release("Kaka")
    await clock.advance(60)                # 真正安静 60 秒：还没走
    assert not any(isinstance(e, VisitorLeft) for e in drain(q))
    await clock.advance(20)                # 安静满 75 秒：走了
    assert any(isinstance(e, VisitorLeft) for e in drain(q))
    runner.cancel()


async def test_reliable_presence_source_decides_arrival_and_departure(clock):
    room = Room(clock, Transcript(), Floor(), lambda: CFG, presence_reliable=True)
    q = room.subscribe()
    runner = asyncio.create_task(room.run())
    await asyncio.sleep(0)

    await room.human_said("你好")                      # 有硬件时，说话不再自动算"来了"
    assert not any(isinstance(e, VisitorArrived) for e in drain(q))
    assert not room.visitor.present

    await room.presence_changed(True)
    assert [type(e) for e in drain(q)] == [VisitorArrived]
    await room.presence_changed(True)                  # 重复报告不重复发事件
    assert drain(q) == []
    sid = room.visitor.session_id

    await clock.advance(400)                           # 安静很久也不算走 —— 硬件说人还在
    assert not any(isinstance(e, VisitorLeft) for e in drain(q))

    await room.presence_changed(False)
    left = [e for e in drain(q) if isinstance(e, VisitorLeft)]
    assert len(left) == 1 and left[0].session_id == sid
    runner.cancel()
