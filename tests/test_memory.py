import json

from echo.brain import Change
from echo.memory import ChangeLog, Days, PuppetMemory, atomic_write_json


def test_atomic_write_leaves_no_tmp(tmp_path):
    p = tmp_path / "x.json"
    atomic_write_json(p, {"a": 1})
    atomic_write_json(p, {"a": 2})
    assert json.loads(p.read_text()) == {"a": 2}
    assert [f.name for f in tmp_path.iterdir()] == ["x.json"]


def test_memory_roundtrip(tmp_path):
    m = PuppetMemory.load("Kaka", tmp_path)
    assert m.beliefs == [] and m.relations == {} and m.path == tmp_path / "kaka.json"
    m.beliefs = ["我的羽毛就是我的论据"]
    m.relations = {"Lucy": "她的沉默是一种冒犯"}
    m.save("w1")
    again = PuppetMemory.load("Kaka", tmp_path)
    assert again.beliefs == ["我的羽毛就是我的论据"]
    assert again.relations == {"Lucy": "她的沉默是一种冒犯"}
    assert again.updated_at == "w1"


def test_unspoken_keeps_last_n(tmp_path):
    m = PuppetMemory.load("Lucy", tmp_path)
    for i in range(5):
        m.add_unspoken(f"想说{i}", f"w{i}", keep=3)
    assert [u["text"] for u in m.unspoken] == ["想说2", "想说3", "想说4"]
    assert [u["text"] for u in PuppetMemory.load("Lucy", tmp_path).unspoken] == ["想说2", "想说3", "想说4"]


def test_apply_changes_requires_a_reason_and_logs_it(tmp_path):
    log = ChangeLog(tmp_path / "changes.jsonl")
    m = PuppetMemory.load("Charlie", tmp_path)
    m.beliefs = ["安静最重要", "Lucy 需要我保护"]
    m.relations = {"Lucy": "她怕"}
    m.unspoken = [{"at": "w", "text": "算了"}]
    m.thoughts = [{"at": "w", "feeling": "x", "intent": "y", "said": None}]
    m.heard = 7
    accepted = m.apply_changes([
        Change("belief", "", "安静最重要", "该说的时候要说", because="Lucy被逼问时我没出声，她更小了"),
        Change("belief", "", "Lucy 需要我保护", "Lucy 会自己扛", because=""),          # 没理由：不收
        Change("belief", "", "", "新朋友说话很短", because="他连着三句都在逼问"),      # 新加一条
        Change("relation", "Kaka", "", "他被骂装的时候没退", because="新朋友说他装，他没躲"),
    ], impression="有个人爱逼问", session_id="s1", wall="w9", capacity=6, changelog=log)
    assert [c.new for c in accepted] == ["该说的时候要说", "新朋友说话很短", "他被骂装的时候没退"]
    assert m.beliefs == ["该说的时候要说", "Lucy 需要我保护", "新朋友说话很短"]
    assert m.relations == {"Lucy": "她怕", "Kaka": "他被骂装的时候没退"}
    assert m.impressions == [{"session": "s1", "text": "有个人爱逼问"}]
    assert m.unspoken == [] and m.thoughts == [] and m.heard == 0
    recs = [json.loads(l) for l in (tmp_path / "changes.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in recs] == ["belief", "rejected", "belief", "relation"]
    assert recs[0]["because"] == "Lucy被逼问时我没出声，她更小了"
    assert recs[1]["old"] == "Lucy 需要我保护"


def test_apply_changes_respects_capacity_and_unknown_old(tmp_path):
    log = ChangeLog(tmp_path / "c.jsonl")
    m = PuppetMemory.load("Kaka", tmp_path)
    m.beliefs = ["A", "B"]
    accepted = m.apply_changes([
        Change("belief", "", "不存在的原句", "X", because="有事"),   # 原句找不到，又没空位 → 不收
        Change("belief", "", "", "C", because="有事"),
    ], "", None, "w", capacity=2, changelog=log)
    assert accepted == [] and m.beliefs == ["A", "B"]


def test_apply_seed_takes_full_set(tmp_path):
    log = ChangeLog(tmp_path / "c.jsonl")
    m = PuppetMemory.load("Lucy", tmp_path)
    m.relations = {"Kaka": "很吵"}
    m.apply_seed(["只有不说话才安全", "", "好看不是我的事"], "w", 6, log)
    assert m.beliefs == ["只有不说话才安全", "好看不是我的事"]
    assert m.relations == {}                                     # 关系不出厂，清空
    assert json.loads((tmp_path / "c.jsonl").read_text())["kind"] == "seed"


def test_days_counts_distinct_dates(tmp_path):
    d = Days(tmp_path / "days.json")
    assert d.wake("2026-09-05") == 1
    assert d.wake("2026-09-05") == 1
    assert d.wake("2026-09-06") == 2
    assert Days(tmp_path / "days.json").wake("2026-09-06") == 2


def test_thoughts_recorded_and_cleared_by_rumination(tmp_path):
    m = PuppetMemory.load("Lucy", tmp_path)
    m.add_thought("怕", "别被注意到", None, "w1", keep=3)
    m.add_thought("", "", None, "w2", keep=3)          # 空的不记
    m.add_thought("好奇", "问一句", "为什么？", "w3", keep=3)
    assert [t["intent"] for t in PuppetMemory.load("Lucy", tmp_path).thoughts] == ["别被注意到", "问一句"]
    assert m.thoughts[1]["said"] == "为什么？"
    m.apply_changes([], "", None, "w4", 6, ChangeLog(tmp_path / "c.jsonl"))
    assert m.thoughts == []


def test_reset_memories_moves_files_aside(tmp_path):
    from echo.memory import reset_memories
    PuppetMemory.load("Charlie", tmp_path).save("w")
    PuppetMemory.load("Kaka", tmp_path).save("w")
    moved = reset_memories(tmp_path, ["Charlie", "Lucy"], "20260926T1800")
    assert [p.name for p in moved] == ["charlie.json"]                  # Lucy 没文件，跳过
    assert not (tmp_path / "charlie.json").exists()
    assert (tmp_path / "reset-20260926T1800" / "charlie.json").exists()  # 挪走，不删
    assert (tmp_path / "kaka.json").exists()                             # 没点名的不动
    assert PuppetMemory.load("Charlie", tmp_path).beliefs == []          # 从白纸开始


def test_load_drops_blank_entries_from_hand_edited_file(tmp_path):
    (tmp_path / "charlie.json").write_text(json.dumps({
        "beliefs": ["只有当我聪明，才可以被人喜欢。", "", "  "],
        "relations": {"Lucy": "", "Kaka": "还算识相"},
        "impressions": [], "unspoken": [], "thoughts": [], "updated_at": "w"}), encoding="utf-8")
    m = PuppetMemory.load("Charlie", tmp_path)
    assert m.beliefs == ["只有当我聪明，才可以被人喜欢。"]
    assert m.relations == {"Kaka": "还算识相"}


