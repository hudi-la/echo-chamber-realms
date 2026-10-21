"""每只木偶自己的记忆，以及"随时可拔电"的落盘。只记印象，不记原话。
顺序：文件工具 → 变更日志 / 天数 / 重置 → PuppetMemory（念头、听到的句数、没说出口的、出厂、带理由的改动）。"""
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


def atomic_write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


class ChangeLog:
    """每次反刍前后的差异。以后是墙二的数据源。"""

    def __init__(self, path: Path) -> None:
        self.path = path

    def append(self, record: dict) -> None:
        append_jsonl(self.path, record)


class Days:
    """开过机的日历日。第 N 天 = 列表长度。夜里关机不动它。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.days: list[str] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def wake(self, today: str) -> int:
        if today not in self.days:
            self.days.append(today)
            atomic_write_json(self.path, self.days)
        return len(self.days)


def reset_memories(state_dir: Path, names: list[str], stamp: str) -> list[Path]:
    """把这几只木偶的记忆文件挪到 state/reset-<stamp>/ 下（不删），下次启动从人设重新长。
    改了人设就该连记忆一起重置：旧人设下反刍出来的信念会跟新人设一起喂给它，信念压过人设。"""
    moved: list[Path] = []
    for name in names:
        src = state_dir / f"{name.lower()}.json"
        if src.exists():
            dst_dir = state_dir / f"reset-{stamp}"
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / src.name
            src.replace(dst)
            moved.append(dst)
    return moved


_FIELDS = ("beliefs", "relations", "impressions", "unspoken", "thoughts", "heard", "updated_at", "pending_experiences", "companion_observations")


@dataclass
class PuppetMemory:
    name: str
    path: Path
    beliefs: list[str] = field(default_factory=list)
    relations: dict[str, str] = field(default_factory=dict)
    impressions: list[dict] = field(default_factory=list)
    unspoken: list[dict] = field(default_factory=list)
    thoughts: list[dict] = field(default_factory=list)   # 每轮的念头：感受 + 想达到什么 + 说了/没说
    heard: int = 0                                        # 上次反刍之后听到了几句。存盘，重启接着数
    updated_at: str = ""
    pending_experiences: list[dict] = field(default_factory=list)
    companion_observations: list[dict] = field(default_factory=list)

    def add_thought(self, feeling: str, intent: str, said: str | None, wall: str, keep: int) -> None:
        """每次决定都记一条，不管开没开口。反刍的原料是这些，不是它表演出来的话。"""
        if not feeling and not intent:
            return
        self.thoughts.append({"at": wall, "feeling": feeling, "intent": intent, "said": said})
        self.thoughts = self.thoughts[-keep:]
        self.save(wall)

    @classmethod
    def load(cls, name: str, state_dir: Path) -> "PuppetMemory":
        path = state_dir / f"{name.lower()}.json"
        if not path.exists():
            return cls(name=name, path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        # 作者可能手改过这个文件：空条目扔掉，别把一条空的"- "喂给模型
        data["beliefs"] = [str(b).strip() for b in data.get("beliefs", []) if str(b).strip()]
        data["relations"] = {k: str(v).strip() for k, v in data.get("relations", {}).items() if str(v).strip()}
        return cls(name=name, path=path, **{k: data[k] for k in _FIELDS if k in data})

    def save(self, wall: str) -> None:
        self.updated_at = wall
        atomic_write_json(self.path, {k: getattr(self, k) for k in _FIELDS})

    def note_heard(self, wall: str, experience: dict | None = None) -> None:
        """听到一句就记一笔并落盘：反刍的计数不能因为重启归零。"""
        self.heard += 1
        if experience is not None:
            self.pending_experiences.append(experience)
        self.save(wall)

    def add_unspoken(self, text: str, wall: str, keep: int) -> None:
        self.unspoken.append({"at": wall, "text": text})
        self.unspoken = self.unspoken[-keep:]
        self.save(wall)

    def apply_seed(self, beliefs: list[str], wall: str, capacity: int, changelog: ChangeLog) -> None:
        """出厂信念：从人设出发的第一套，整套收下。关系、印象、念头全空 —— 对彼此的看法要从第一句话开始长。"""
        self.beliefs = [b.strip() for b in beliefs if b.strip()][:capacity]
        self.relations, self.impressions, self.unspoken, self.thoughts, self.heard = {}, [], [], [], 0
        self.pending_experiences, self.companion_observations = [], []
        self.save(wall)
        changelog.append({"at": wall, "who": self.name, "kind": "seed", "beliefs": list(self.beliefs)})

    def apply_changes(self, changes, impression: str, session_id: str | None, wall: str,
                      capacity: int, changelog: ChangeLog, consumed=None, consumed_experiences=None) -> list:
        """把一次反刍的结果并进来。信念只因"有分量的事"而变：没有理由（because）的改动不收。
        每处采纳的改动连同理由写进 changes.jsonl。返回采纳了的改动。"""
        accepted = []
        for c in changes:
            if not c.because.strip() or not c.new.strip():
                changelog.append({"at": wall, "who": self.name, "kind": "rejected",
                                  "target": c.kind, "old": c.old, "new": c.new, "because": c.because})
                continue
            if c.kind == "belief":
                if c.old and c.old in self.beliefs:
                    self.beliefs[self.beliefs.index(c.old)] = c.new
                elif c.new not in self.beliefs and len(self.beliefs) < capacity:
                    self.beliefs.append(c.new)
                else:
                    continue
            elif c.kind == "relation" and c.who:
                self.relations[c.who] = c.new  # Legacy latest-view field; never used in prompts.
                self.companion_observations.append({"at": wall, "who": c.who, "view": c.new, "because": c.because})
            else:
                continue
            accepted.append(c)
            changelog.append({"at": wall, "who": self.name, "kind": c.kind, "target": c.who,
                              "old": c.old, "new": c.new, "because": c.because, "session": session_id})
        if impression and session_id:
            self.impressions.append({"session": session_id, "text": impression})
        if consumed is None:
            self.unspoken, self.thoughts, self.heard = [], [], 0
        else:
            thoughts, unspoken, heard = consumed
            self.thoughts = [t for t in self.thoughts if not any(t is old for old in thoughts)]
            self.unspoken = [t for t in self.unspoken if not any(t is old for old in unspoken)]
            self.heard = max(0, self.heard - heard)
        if consumed_experiences is not None:
            self.pending_experiences = [e for e in self.pending_experiences
                if not any(e is old for old in consumed_experiences)]
        self.save(wall)
        return accepted
