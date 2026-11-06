from echo.ears import Ears, looks_like_echo
from echo.floor import HUMAN, Floor


def test_looks_like_echo():
    assert looks_like_echo("当然是我", "当然是我，Kaka。你看我这身羽毛。")           # 子串
    assert looks_like_echo("当然是我卡卡你看我这身羽毛", "当然是我，Kaka。你看我这身羽毛。")  # 相似
    assert not looks_like_echo("你们谁最好看", "当然是我，Kaka。你看我这身羽毛。")
    assert not looks_like_echo("你好", None)
    assert not looks_like_echo("", "什么")


class RoomSpy:
    def __init__(self):
        self.floor = Floor()
        self.calls = []

    async def human_started(self):
        self.calls.append("started")
        await self.floor.seize_by_human()

    async def human_said(self, text):
        self.calls.append(("said", text))
        self.floor.release_human()


async def gen(*events):
    for e in events:
        yield e


async def test_started_then_said_is_one_utterance():
    room = RoomSpy()
    ears = Ears(room, lambda: None, log_line=lambda s: None)
    await ears.consume(gen(("started",), ("said", "你们好")))
    assert room.calls == ["started", ("said", "你们好")]
    assert room.floor.free


async def test_said_without_started_still_opens_first():
    room = RoomSpy()
    ears = Ears(room, lambda: None, log_line=lambda s: None)
    await ears.consume(gen(("said", "你好"),))
    assert room.calls == ["started", ("said", "你好")]


async def test_empty_or_punctuation_transcripts_are_dropped():
    room = RoomSpy()
    ears = Ears(room, lambda: None, log_line=lambda s: None)
    await ears.consume(gen(("started",), ("said", "  "), ("said", "……"), ("started",), ("said", "嗯，在。")))
    assert room.calls == ["started", "started", ("said", "嗯，在。")]  # "嗯，在。" 去掉标点是两个字，够


async def test_echo_of_own_voice_is_dropped_and_floor_returned():
    room = RoomSpy()
    logs = []
    playing = "当然是我，Kaka。你看我这身羽毛。"

    async def stop() -> str:
        return "当然是我"

    room.floor.try_acquire("Kaka", stop)
    ears = Ears(room, lambda: playing, interrupt="immediate", log_line=logs.append)
    await ears.consume(gen(("started",), ("said", "当然是我卡卡你看我这身羽毛")))
    assert room.calls == ["started"]          # immediate 模式：先打断了
    assert room.floor.free                     # 发现是自听，把发言权还回去
    assert any("木偶自己" in line for line in logs)


async def test_confirm_mode_waits_for_transcript_when_puppet_speaking():
    room = RoomSpy()

    async def stop() -> str:
        return ""

    room.floor.try_acquire("Kaka", stop)
    ears = Ears(room, lambda: "当然是我", interrupt="confirm", log_line=lambda s: None)
    await ears.on_started()
    assert room.calls == []                    # 木偶在说，先不打断
    await ears.on_said("你们谁最好看？")
    assert room.calls == ["started", ("said", "你们谁最好看？")]   # 确认是人，才打断并说


async def test_confirm_mode_interrupts_immediately_when_nobody_speaking():
    room = RoomSpy()
    ears = Ears(room, lambda: None, interrupt="confirm", log_line=lambda s: None)
    await ears.on_started()
    assert room.calls == ["started"]
    assert room.floor.holder == HUMAN


# ---------- 播放期闸门 ----------

from echo.ears import PlaybackGate


def test_gate_passes_everything_when_not_playing():
    g = PlaybackGate()
    assert all(g.feed(rms, playing=False, now=i * 0.1) for i, rms in enumerate([50, 150, 5000]))


def test_gate_learns_leak_then_blocks_echo_and_passes_loud_voice():
    g = PlaybackGate(factor=3.0, floor=400, learn_chunks=5)
    t = 0.0
    for _ in range(5):                       # 学习期：漏音 800，全部不送
        assert g.feed(800, playing=True, now=t) is False
        t += 0.1
    assert g.leak == 800
    assert g.feed(900, playing=True, now=t) is False    # 跟漏音差不多 → 不送
    assert g.feed(2600, playing=True, now=t) is True    # 3 倍以上 → 人在说话，送
    assert g.feed(300, playing=True, now=t) is False    # 比漏音还轻 → 不送


def test_gate_tail_after_playback_and_floor():
    g = PlaybackGate(factor=3.0, floor=400, tail=0.5, learn_chunks=1)
    g.feed(100, playing=True, now=0.0)                  # 学习：漏音很小
    assert g.feed(350, playing=True, now=0.1) is False  # 低于 floor 不送，哪怕远超漏音
    assert g.feed(450, playing=False, now=0.3) is True  # 尾巴期内但超过 floor → 送
    assert g.feed(50, playing=False, now=0.4) is False  # 尾巴期内、太轻 → 不送
    assert g.feed(50, playing=False, now=0.9) is True   # 尾巴过了 → 全送


async def test_short_responses_are_retained_and_floor_returned():
    room = RoomSpy()
    logs = []
    ears = Ears(room, lambda: None, min_chars=2, log_line=logs.append)
    await ears.consume(gen(("started",), ("said", "嗯"), ("started",), ("said", "山圳"), ("started",), ("said", "在的")))
    # “嗯”作为有效短回答保留；两个陌生字仍通过原有长度门槛。
    assert room.calls == ["started", ("said", "嗯"), "started", ("said", "山圳"), "started", ("said", "在的")]
    assert room.floor.free
    assert not any("太短" in line for line in logs)


async def test_echo_matches_recently_finished_text_too():
    room = RoomSpy()
    ears = Ears(room, lambda: "……哼，来得突然，说得也像没梳过的草。更是如此。", log_line=lambda s: None)
    await ears.consume(gen(("started",), ("said", "更是")))   # 木偶刚说完，麦克风晚一步听见
    assert room.calls == ["started"] and room.floor.free


# ---------- 流式转写触发的打断（confirm 模式）----------

async def test_partial_words_interrupt_speaking_puppet():
    room = RoomSpy()

    async def stop() -> str:
        return "汪"

    room.floor.try_acquire("Charlie", stop)
    ears = Ears(room, lambda: "汪，Lucy，我听见你说害怕了。", interrupt="confirm", log_line=lambda s: None)
    await ears.consume(gen(("started",), ("partial", "玩")))          # 木偶自己的"汪"→"玩"：一个字，不够
    assert room.calls == []
    await ears.consume(gen(("partial", "等一"), ("partial", "等一下"), ("said", "等一下。")))
    assert room.calls == ["started", ("said", "等一下。")]           # 凑够两个陌生字就打断，说完再落地
    assert room.floor.free


async def test_partial_echo_does_not_interrupt():
    room = RoomSpy()

    async def stop() -> str:
        return ""

    room.floor.try_acquire("Kaka", stop)
    ears = Ears(room, lambda: "当然是我，Kaka。你看我这身羽毛。", interrupt="confirm", log_line=lambda s: None)
    await ears.consume(gen(("started",), ("partial", "当然"), ("partial", "当然是我"), ("said", "当然是我卡卡")))
    assert room.calls == []                                           # 全是木偶原话，从头到尾不打断
    assert room.floor.holder == "Kaka"


async def test_partial_ignored_when_nobody_speaking_or_already_open():
    room = RoomSpy()
    ears = Ears(room, lambda: None, interrupt="confirm", log_line=lambda s: None)
    await ears.consume(gen(("started",), ("partial", "你们"), ("said", "你们好")))
    assert room.calls == ["started", ("said", "你们好")]              # 没木偶在说：started 就开门，partial 不重复开


def test_echo_ignores_names_and_catches_short_fragments():
    playing = "当然是我，Kaka。你看我这身羽毛。"
    assert looks_like_echo("当然是我卡卡", playing)           # 短碎片：去掉名字后整段都在原话里
    assert not looks_like_echo("Kaka 你好", playing)          # 名字不算相似；"你好"不在原话里 → 是人
    assert not looks_like_echo("Lucy 你怎么看", "汪，Lucy，我听见你说害怕了。")


async def test_live_partials_and_timing_log():
    room = RoomSpy()
    logs, live = [], []
    t = [10.0]
    ears = Ears(room, lambda: None, log_line=logs.append, live=live.append, now=lambda: t[0])
    await ears.on_started()
    t[0] = 10.4; await ears.on_partial("你们")
    t[0] = 11.3; await ears.on_said("你们好")
    assert live == ["你们", None]                                  # 半句推出去，说完清掉
    assert any("有人开口了" in l for l in logs)
    assert any("转写用了 1.3 秒：「你们好」" in l for l in logs)
    assert room.calls == ["started", ("said", "你们好")]
