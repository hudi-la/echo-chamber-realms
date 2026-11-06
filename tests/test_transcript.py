import json

from echo.transcript import Transcript


def test_add_appends_jsonl(tmp_path):
    t = Transcript(tmp_path / "transcript.jsonl")
    t.add(1.0, "w1", "said", "新朋友", "你们好")
    t.add(2.0, "w2", "said", "Kaka", "哼")
    lines = (tmp_path / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1]) == {"at": 2.0, "wall": "w2", "kind": "said", "who": "Kaka", "text": "哼"}


def test_render_states_only_what_they_know():
    t = Transcript()
    t.add(0.0, "w", "woke", "", "4")
    t.add(62.0, "w", "arrived", "新朋友")
    t.add(62.0, "w", "said", "新朋友", "你们谁最好看？")
    t.add(69.0, "w", "cut", "Kaka", "还用问吗")
    t.add(76.0, "w", "said", "新朋友", "Charlie 你说呢？")
    out = t.render(now=100.0, me="Kaka", speaker=None, last_spoke_at=69.0, quiet_for=24.0, window=24)
    assert out.splitlines() == [
        "(-38s) 新朋友：你们谁最好看？",
        "(-31s) 你（Kaka）：还用问吗（被打断）",
        "(-24s) 新朋友：Charlie 你说呢？",
        "(现在) 没人在说，已经安静 24 秒。你上一次开口是 31 秒前。",
    ]  # 没有天数、没有开机、没有"来了"——那些不是它们确切知道的事


def test_render_presence_only_when_reliable():
    t = Transcript()
    t.add(10.0, "w", "arrived", "新朋友")
    t.add(12.0, "w", "said", "新朋友", "你好")
    t.add(90.0, "w", "left", "新朋友")
    hidden = t.render(now=100.0, me="Lucy", speaker=None, last_spoke_at=None, quiet_for=10.0, window=24)
    assert "来了" not in hidden and "走了" not in hidden
    shown = t.render(now=100.0, me="Lucy", speaker=None, last_spoke_at=None, quiet_for=10.0, window=24,
                     show_presence=True)
    assert shown.splitlines()[0] == "(-90s) 新朋友 来了"
    assert shown.splitlines()[2] == "(-10s) 新朋友 走了"


def test_render_window_speaker_and_unknown_last_spoke():
    t = Transcript()
    for i in range(30):
        t.add(float(i), "w", "said", "Lucy", f"第{i}句")
    out = t.render(now=40.0, me="Charlie", speaker="Lucy", last_spoke_at=None, quiet_for=0.0, window=3)
    lines = out.splitlines()
    assert lines[:3] == ["(-13s) Lucy：第27句", "(-12s) Lucy：第28句", "(-11s) Lucy：第29句"]
    assert lines[3] == "(现在) Lucy 正在说。"  # 不知道上次什么时候开的口，就不提


def test_render_minutes():
    t = Transcript()
    out = t.render(now=400.0, me="Lucy", speaker=None, last_spoke_at=100.0, quiet_for=2.0, window=5)
    assert out.splitlines()[-1] == "(现在) 没人在说。你上一次开口是 5 分钟前。"
