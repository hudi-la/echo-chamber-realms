import asyncio
import json
from pathlib import Path

from echo.brain import Change, Decision, Rumination, Seed
from echo.config import parse_config
from echo.events import PuppetCut, PuppetSaid, VisitorLeft
from echo.floor import Floor
from echo.memory import ChangeLog, PuppetMemory
from echo.motors import PrintMotors
from echo.mouth import PrintMouth
from echo.puppet import NEUTRAL, Puppet
from echo.room import Room
from echo.transcript import Transcript
from tests.fakes import FakeBrain

CFG = parse_config("""
[room]
quiet_interval_with_visitor = 8
quiet_interval_alone = 120
[memory]
ruminate_every = 3
bedtime_min_heard = 1
belief_capacity = 2
unspoken_keep = 8
""", base=Path("/tmp"))


def build(clock, tmp_path, names_and_brains, out=None):
    out = out if out is not None else []
    room = Room(clock, Transcript(), Floor(window=0), lambda: CFG)
    mouth = PrintMouth(clock, chars_per_second=10, out=out.append)
    motors = PrintMotors(out=out.append)
    changelog = ChangeLog(tmp_path / "changes.jsonl")
    puppets = {}
    for name, brain in names_and_brains:
        mem = PuppetMemory.load(name, tmp_path)
        puppets[name] = Puppet(name, f"你是{name}。", mem, brain, room, mouth, motors, clock,
                               lambda: CFG, changelog, tmp_path / "sessions.jsonl", log=out.append)
    return room, puppets, mouth, motors, out


async def settle(clock, seconds=0.0):
    for _ in range(15):
        await asyncio.sleep(0)
    if seconds:
        await clock.advance(seconds)


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out


async def test_speaks_and_records(clock, tmp_path):
    kaka = FakeBrain([Decision(True, "还用问吗，当然是我")])
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    watcher = room.subscribe()
    await room.human_said("你们谁最好看？")
    await settle(clock, 2)
    said = [e for e in _drain(watcher) if isinstance(e, PuppetSaid)]
    assert said and said[0].name == "Kaka" and said[0].text == "还用问吗，当然是我"
    assert room.floor.free
    assert motors.log == [("speaking", "Kaka"), ("silent", "Kaka")]
    assert room.transcript.entries[-1].text == "还用问吗，当然是我"
    assert puppets["Kaka"].last_spoke_at is not None
    system, situation = kaka.calls[0]
    assert system.startswith("你是Kaka。") and system.endswith(NEUTRAL)
    assert "新朋友：你们谁最好看？" in situation
    task.cancel()


async def test_loser_swallows_words(clock, tmp_path, monkeypatch):
    monkeypatch.setattr("echo.floor.random.choice", lambda names: "Kaka" if "Kaka" in names else names[0])
    kaka = FakeBrain([Decision(True, "当然是我当然是我呀")], delay=0.1, clock=clock)  # 9 字 ≈ 0.9 秒，够 Charlie 撞上
    charlie = FakeBrain([Decision(True, "荒谬的问题")], delay=0.5, clock=clock)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka), ("Charlie", charlie)])
    tasks = [asyncio.create_task(p.run()) for p in puppets.values()]
    await room.human_said("谁最好看？")
    await settle(clock, 0.2)
    assert room.floor.holder == "Kaka"
    # Kaka 开口时 Charlie 收到 PuppetStarted，会取消重来一轮（再等 0.5 秒），所以要推到 0.2+0.5 之后
    await settle(clock, 0.6)
    charlie_mem = PuppetMemory.load("Charlie", tmp_path)
    assert charlie_mem.unspoken == []
    assert charlie.calls == []  # 未获选者不生成台词，也不请求开口判断
    for t in tasks:
        t.cancel()


async def test_empty_output_is_generation_failure(clock, tmp_path):
    lucy = FakeBrain([Decision(False, "")])
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Lucy", lucy)])
    task = asyncio.create_task(puppets["Lucy"].run())
    await room.human_said("在吗？")
    await settle(clock, 1)
    assert room.floor.free and motors.log == []
    assert any("Lucy 台词生成失败" in line for line in out)
    task.cancel()


async def test_human_interrupts_mid_sentence(clock, tmp_path):
    kaka = FakeBrain([Decision(True, "一二三四五六七八九十")])  # 10 字 = 1 秒
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    watcher = room.subscribe()
    await room.human_said("说说")
    await settle(clock, 0.4)
    assert room.floor.holder == "Kaka"
    await room.human_started()
    await settle(clock)
    events = _drain(watcher)
    cut = [e for e in events if isinstance(e, PuppetCut)]
    assert cut and cut[0].spoken == "一二三四"
    assert not any(isinstance(e, PuppetSaid) for e in events)
    assert motors.log[-1] == ("silent", "Kaka")
    await room.human_said("等等")
    assert room.floor.free
    task.cancel()


async def test_ruminates_after_n_and_on_visitor_left(clock, tmp_path):
    rum = Rumination([Change("belief", "", "", "外貌排名让关系紧张", because="新朋友连问三次谁最好看，Lucy越来越小声")],
                     impression="有个人很吵")
    charlie = FakeBrain([], rumination=rum)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Charlie", charlie)])
    task = asyncio.create_task(puppets["Charlie"].run())
    for i in range(3):  # ruminate_every = 3
        await room.human_said(f"第{i}句")
        await settle(clock)
    await settle(clock)
    assert len(charlie.ruminations) == 1
    assert "impression 留空" in charlie.ruminations[0]           # 不是一场结束，不问印象
    mem = PuppetMemory.load("Charlie", tmp_path)
    assert mem.beliefs == ["外貌排名让关系紧张"]
    assert mem.impressions == []
    rec = json.loads((tmp_path / "changes.jsonl").read_text().splitlines()[0])
    assert rec["kind"] == "belief" and rec["because"].startswith("新朋友连问三次")
    assert any("改了信念" in line and "因为" in line for line in out)

    await room.publish(VisitorLeft(clock.now(), "s1"))
    await settle(clock)
    assert len(charlie.ruminations) == 2
    assert "一场到访的结束" in charlie.ruminations[1]              # 一场结束才问印象
    mem = PuppetMemory.load("Charlie", tmp_path)
    assert mem.impressions == [{"session": "s1", "text": "有个人很吵"}]
    star = json.loads((tmp_path / "sessions.jsonl").read_text().splitlines()[0])
    assert star == {"session": "s1", "who": "Charlie", "impression": "有个人很吵", "at": clock.wall()}
    task.cancel()


async def test_rumination_without_reason_changes_nothing(clock, tmp_path):
    rum = Rumination([Change("belief", "", "", "我说多了会破坏安静", because="")])   # 没理由
    lucy = FakeBrain([], rumination=rum)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Lucy", lucy)])
    puppets["Lucy"].memory.beliefs = ["只有不说话才安全"]
    task = asyncio.create_task(puppets["Lucy"].run())
    for i in range(3):
        await room.human_said(f"第{i}句"); await settle(clock)
    await settle(clock)
    assert PuppetMemory.load("Lucy", tmp_path).beliefs == ["只有不说话才安全"]
    assert any("没有什么事分量够，信念不变" in line for line in out)
    task.cancel()


async def test_seed_if_blank_from_persona(clock, tmp_path):
    kaka = FakeBrain([], seed=Seed(["只有被羡慕才安心", "外表是我唯一的价值"]))
    room, puppets, *_ = build(clock, tmp_path, [("Kaka", kaka)])
    assert await puppets["Kaka"].seed_if_blank() is True
    assert kaka.seeds == []  # reviewed presets, no model request
    mem = PuppetMemory.load("Kaka", tmp_path)
    assert mem.beliefs == ["我的美丽和优秀证明我有价值。", "被羡慕才让我感到真实。"] and mem.relations == {}
    assert await puppets["Kaka"].seed_if_blank() is False        # 已经有信念，不重复生成


async def test_loser_records_intent_as_unspoken(clock, tmp_path, monkeypatch):
    monkeypatch.setattr("echo.floor.random.choice", lambda names: "Kaka" if "Kaka" in names else names[0])
    kaka = FakeBrain([Decision(True, "当然是我当然是我呀", feeling="兴奋", intent="让他们羡慕我")], delay=0.1, clock=clock)
    charlie = FakeBrain([Decision(True, "荒谬", feeling="紧张", intent="护住 Lucy")], delay=0.5, clock=clock)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka), ("Charlie", charlie)])
    tasks = [asyncio.create_task(p.run()) for p in puppets.values()]
    await room.human_said("谁最好看？")
    await settle(clock, 0.2)
    assert room.floor.holder == "Kaka"
    await settle(clock, 0.6)
    mem = PuppetMemory.load("Charlie", tmp_path)
    assert mem.unspoken == []   # 没抢到：没说出口的是它的意图
    assert charlie.calls == []  # 未获选者不生成台词，也不请求开口判断
    for t in tasks:
        t.cancel()


async def test_lock_is_held_while_composing(clock, tmp_path, monkeypatch):
    monkeypatch.setattr("echo.floor.random.choice", lambda names: "Kaka" if "Kaka" in names else names[0])
    # Kaka 决定得快（0.1s），但写台词要 1 秒；Charlie 0.5s 决定要说 —— 撞上正在写台词的 Kaka，咽回去
    kaka = FakeBrain([Decision(True, "当然是我", intent="炫耀")], delay=0.1, clock=clock, compose_delay=1.0)
    charlie = FakeBrain([Decision(True, "荒谬", intent="嘲笑排名")], delay=0.5, clock=clock)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka), ("Charlie", charlie)])
    tasks = [asyncio.create_task(p.run()) for p in puppets.values()]
    await room.human_said("谁最好看？")
    await settle(clock, 0.2)
    assert room.floor.holder == "Kaka" and motors.log == []          # 抢到了，台词还没到，还没动
    await settle(clock, 0.5)
    assert charlie.calls == []  # 未获选者不生成台词，也不请求开口判断
    await settle(clock, 0.6)
    assert motors.log[0] == ("speaking", "Kaka")                     # 台词到了才开始说
    for t in tasks:
        t.cancel()


async def test_empty_line_releases_lock(clock, tmp_path):
    kaka = FakeBrain([Decision(True, "", intent="想说但词穷")])      # compose 返回空
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    await room.human_said("谁？")
    await settle(clock, 0.5)
    assert room.floor.free and motors.log == []
    assert any("台词生成失败" in line for line in out)
    task.cancel()


async def test_speaker_yields_one_round_after_own_line(clock, tmp_path):
    # Kaka 说完之后，自己的"说完了"不触发再决定；别人开口或安静了才轮到它
    kaka = FakeBrain([Decision(True, "当然是我"), Decision(True, "还是我"), Decision(True, "又是我")])
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    await room.human_said("谁最好看？")
    await settle(clock, 1.0)                       # "当然是我" 4 字 = 0.4s，说完了
    assert len(kaka.calls) == 1                    # 自己的 PuppetSaid 没有引发第二次决定
    assert room.floor.free
    await room.publish(PuppetSaid(clock.now(), "Charlie", "荒谬"))   # 别人说了
    await settle(clock, 0.5)
    assert len(kaka.calls) == 2                    # 现在才再决定
    for t in [task]:
        t.cancel()


async def test_cut_puppet_does_not_react_to_its_own_cut(clock, tmp_path):
    kaka = FakeBrain([Decision(True, "一二三四五六七八九十"), Decision(True, "我还没说完")])
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    await room.human_said("说说")
    await settle(clock, 0.4)
    await room.human_started()                     # 人打断
    await settle(clock)
    assert len(kaka.calls) == 1                    # 自己被打断这件事不引发决定（人还在说）
    await room.human_said("我觉得不是")
    await settle(clock)
    assert len(kaka.calls) == 2                    # 人说完了，再决定
    task.cancel()


async def test_started_event_carries_the_line_for_the_monitor(clock, tmp_path):
    from echo.events import PuppetStarted
    kaka = FakeBrain([Decision(True, "当然是我")])
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    watcher = room.subscribe()
    await room.human_said("谁？")
    await settle(clock, 0.1)
    started = [e for e in _drain(watcher) if isinstance(e, PuppetStarted)]
    assert started and started[0].text == "当然是我"
    assert room.transcript.entries[-1].who == "新朋友"   # 木偶的现场记录里还没有这句：要等说完
    task.cancel()


async def test_actual_dialogue_replaces_private_thought_material(clock, tmp_path):
    rum = Rumination([], "")
    lucy = FakeBrain([Decision(False, "", feeling="怕", intent="别被注意到"),
                      Decision(True, "为什么？", feeling="好奇", intent="问一句")], rumination=rum)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Lucy", lucy)])
    task = asyncio.create_task(puppets["Lucy"].run())
    await room.human_said("第0句")
    await settle(clock, 1)
    mem = PuppetMemory.load("Lucy", tmp_path)
    assert mem.thoughts == []
    assert mem.pending_experiences[0]["text"] == "第0句"
    assert any("Lucy 台词生成失败" in line for line in out)
    await room.human_said("第1句")          # Lucy 开口；她自己那句也算听到的 → 凑够 3 句，反刍
    await settle(clock, 1)
    assert lucy.ruminations, "应该已经反刍了"
    material = lucy.ruminations[0]
    assert "第0句" in material and "第1句" in material
    assert "为什么？" in material and "别被注意到" not in material
    assert "当前信念最多 2 条" in material
    assert PuppetMemory.load("Lucy", tmp_path).thoughts == []   # 消化进信念就清掉
    task.cancel()


async def test_interrupted_while_composing_does_not_speak_over_human(clock, tmp_path):
    from echo.events import PuppetStarted
    kaka = FakeBrain([Decision(True, "当然是我", intent="炫耀")], compose_delay=1.0, clock=clock)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Kaka", kaka)])
    task = asyncio.create_task(puppets["Kaka"].run())
    watcher = room.subscribe()
    await room.human_said("谁？")
    await settle(clock, 0.2)
    assert room.floor.holder == "Kaka"            # 抢到了，正在写台词
    await room.human_started()                     # 人在它出声前开口
    await settle(clock, 1.2)                       # 台词写完了
    events = _drain(watcher)
    assert not any(isinstance(e, PuppetStarted) for e in events)   # 没开始说
    assert motors.log == []
    assert room.floor.holder == "新朋友"
    assert any("还没说出口就被打断" in line for line in out)
    assert puppets["Kaka"].speaking is False
    assert PuppetMemory.load("Kaka", tmp_path).unspoken == []
    await room.human_said("我来说")
    await settle(clock, 0.5)
    assert len(kaka.calls) == 2                    # 人说完了它能再决定（没卡在 speaking 上）
    task.cancel()


async def test_heard_count_survives_restart_and_bedtime_ruminates(clock, tmp_path):
    rum = Rumination([], "")
    # 第一次开机：听到 2 句（ruminate_every = 3），关机
    lucy = FakeBrain([Decision(False, "", feeling="怕", intent="躲")], rumination=rum)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Lucy", lucy)])
    task = asyncio.create_task(puppets["Lucy"].run())
    await room.human_said("一"); await settle(clock)
    await room.human_said("二"); await settle(clock)
    assert PuppetMemory.load("Lucy", tmp_path).heard == 2       # 计数在盘上
    assert not lucy.ruminations
    task.cancel()
    # 第二次开机：再听 1 句就该反刍（2 + 1 = 3），不归零
    lucy2 = FakeBrain([], rumination=rum)
    room2, puppets2, *_ = build(clock, tmp_path, [("Lucy", lucy2)])
    task2 = asyncio.create_task(puppets2["Lucy"].run())
    await room2.human_said("三"); await settle(clock)
    assert len(lucy2.ruminations) == 1
    assert PuppetMemory.load("Lucy", tmp_path).heard == 0
    task2.cancel()
    # 睡前整理：有念头就反刍，没有就不做
    lucy3 = FakeBrain([Decision(False, "", feeling="累", intent="睡")], rumination=rum)
    room3, puppets3, *_ = build(clock, tmp_path, [("Lucy", lucy3)])
    task3 = asyncio.create_task(puppets3["Lucy"].run())
    await room3.human_said("四"); await settle(clock)
    assert await puppets3["Lucy"].ruminate_if_pending() is True
    assert len(lucy3.ruminations) == 1
    assert await puppets3["Lucy"].ruminate_if_pending() is False   # 已经消化完，没东西
    task3.cancel()


async def test_seed_prefers_author_preset_over_generation(clock, tmp_path):
    kaka = FakeBrain([], seed=Seed(["模型生成的"]))
    room, puppets, *_ = build(clock, tmp_path, [("Kaka", kaka)])
    assert await puppets["Kaka"].seed_if_blank({"beliefs": ["作者写的"]}) is True
    assert kaka.seeds == []                                       # 没去问模型
    mem = PuppetMemory.load("Kaka", tmp_path)
    assert mem.beliefs == ["作者写的"] and mem.relations == {}
