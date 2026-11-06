# 对话引擎 · 阶段 1 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在终端里用打字跟三只木偶对话；能看到谁抢到发言权、谁咽回去、谁沉默；能打断；Ctrl-C 后重开记忆还在。没有麦克风、音箱、Arduino。

**Architecture:** 一个 `Room` 做事件总线 + 现场记录 + 发言锁 + 沉默计时；三个对称的 `Puppet` 循环各自收事件、各调各的模型、各抢锁；`PrintMouth` / `PrintMotors` 是嘴和动作的关闭模式；`PuppetMemory` 原子落盘。代码只提供耳朵、嘴、锁，不提供动机 —— 任何"谁该说"的逻辑都不允许出现在代码里。

**Tech Stack:** Python 3.12（`.venv`）、asyncio、`anthropic` 1.3.0（结构化输出 `output_config.format`、prompt caching）、`tomllib`、pytest + pytest-asyncio。

**Spec:** `docs/superpowers/specs/2026-09-03-conversation-engine-design.md`

## Global Constraints

- 不指挥：代码里不得出现计分、冷却时间表、谁让谁、"这句话是问你的"之类逻辑（spec §1.1、§4.3）
- 现场记录只陈述事实，不评价、不暗示（spec §1.2）
- 一次只有一个在说；人一开口木偶立刻停（spec §1.3、§1.4）
- 每次状态改动原子落盘，随时可拔电（spec §1.5、§5.4）
- 只记印象不记原话进木偶记忆；原话只在 `state/transcript.jsonl`（spec §5.1）
- 木偶默认模型 `claude-opus-5`，`thinking: adaptive`，`effort: low`，system 开缓存（spec §4.4）
- 所有测试不调真模型、不需要 key（spec §12）
- 老代码（`tools.py`、`chat_agents.py`、各 streamlit 入口）一行不动；新代码全在 `echo/` 包里
- 用 `.venv/bin/python` 和 `.venv/bin/pytest`，不用系统 python
- 每个 commit 末尾带 `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`

---

## 文件结构

```
echo-chamber-realms/
├── pyproject.toml                # pytest 配置（asyncio_mode = auto）
├── config.toml                   # 旋钮（spec §10）
├── .gitignore                    # .venv/ state/ __pycache__/
├── echo/
│   ├── __init__.py
│   ├── clock.py        Clock / FakeClock —— 一切时间都从这儿来，测试可控
│   ├── events.py       事件 dataclass（spec §3.1）
│   ├── floor.py        Floor 发言锁（spec §3.2）
│   ├── transcript.py   Transcript 现场记录：追加、落盘、渲染给木偶看（spec §4.1）
│   ├── memory.py       原子写、PuppetMemory、Days、ChangeLog（spec §5）
│   ├── brain.py        Decision / Rumination / Brain 协议 / ClaudeBrain（spec §4.2、§4.4、§5.2）
│   ├── mouth.py        Mouth 协议 + PrintMouth（spec §8.1 关闭模式）
│   ├── motors.py       Motors 协议 + PrintMotors（spec §8.2 关闭模式）
│   ├── session.py      VisitorTracker（spec §6）
│   ├── config.py       Config / parse_config / LiveConfig 热重载（spec §10）
│   ├── room.py         Room：总线、锁的人类优先、沉默计时、到访起止（spec §3）
│   ├── puppet.py       Puppet 循环（spec §4）+ 反刍触发（spec §5.2）
│   ├── console.py      键盘替身（spec §7.2）
│   └── __main__.py     组装与启动（spec §9）
└── tests/
    ├── conftest.py
    ├── fakes.py        FakeBrain
    ├── test_clock.py
    ├── test_floor.py
    ├── test_transcript.py
    ├── test_memory.py
    ├── test_brain.py
    ├── test_mouth_motors.py
    ├── test_session_config.py
    ├── test_room.py
    ├── test_puppet.py
    └── test_console.py
```

---

### Task 1: 骨架与测试环境

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `echo/__init__.py`, `tests/conftest.py`

**Interfaces:**
- Produces: 可运行的 `.venv/bin/pytest`；`tests/conftest.py` 提供 `clock` fixture（`FakeClock`，Task 2 定义）

- [ ] **Step 1: 装测试依赖**

Run:
```bash
cd "/Users/dihu/Documents/remake echo chamber realm/echo-chamber-realms" && uv pip install --python .venv/bin/python pytest pytest-asyncio
```
Expected: 输出末尾有 `+ pytest==...` 和 `+ pytest-asyncio==...`

- [ ] **Step 2: 写 pyproject.toml 和 .gitignore**

`pyproject.toml`:
```toml
[project]
name = "echo-chamber"
version = "0.1.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

`.gitignore`:
```
.venv/
state/
__pycache__/
*.pyc
.DS_Store
```

- [ ] **Step 3: 建包和 conftest**

`echo/__init__.py`: 空文件。

`tests/conftest.py`:
```python
import pytest

from echo.clock import FakeClock


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()
```

- [ ] **Step 4: 确认 pytest 能跑（此时会因为 echo.clock 不存在而报错，属预期）**

Run: `.venv/bin/pytest -q`
Expected: `ModuleNotFoundError: No module named 'echo.clock'` —— 这就是 Task 2 的第一个失败测试的前身。

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore echo/__init__.py tests/conftest.py
git commit -m "chore: 对话引擎骨架与测试环境

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: 时钟

**Files:**
- Create: `echo/clock.py`
- Test: `tests/test_clock.py`

**Interfaces:**
- Produces:
  - `class Clock`: `now() -> float`（单调秒）、`wall() -> str`（ISO 时间字符串）、`today() -> str`（`YYYY-MM-DD`）、`async sleep(seconds: float)`
  - `class FakeClock(Clock)`: 构造 `FakeClock(start=0.0, today="2026-09-05")`；`async advance(seconds)` 推进时间并按顺序唤醒所有到期的 `sleep`；`set_today(day: str)`

- [ ] **Step 1: 写失败测试**

`tests/test_clock.py`:
```python
import asyncio

from echo.clock import FakeClock


async def test_fake_clock_wakes_sleepers_in_order():
    clock = FakeClock()
    order = []

    async def sleeper(tag, seconds):
        await clock.sleep(seconds)
        order.append(tag)

    asyncio.create_task(sleeper("b", 5))
    asyncio.create_task(sleeper("a", 2))
    await asyncio.sleep(0)

    await clock.advance(3)
    assert order == ["a"]
    assert clock.now() == 3

    await clock.advance(3)
    assert order == ["a", "b"]
    assert clock.now() == 6


async def test_fake_clock_sleep_zero_returns_immediately():
    clock = FakeClock()
    await clock.sleep(0)
    assert clock.now() == 0


async def test_fake_clock_cancelled_sleeper_is_forgotten():
    clock = FakeClock()
    task = asyncio.create_task(clock.sleep(10))
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.sleep(0)
    await clock.advance(20)  # 不应该因为被取消的 future 报错
    assert clock.now() == 20


def test_fake_clock_today_and_wall():
    clock = FakeClock(start=42, today="2026-09-05")
    assert clock.today() == "2026-09-05"
    assert clock.wall().startswith("2026-09-05")
    clock.set_today("2026-09-06")
    assert clock.today() == "2026-09-06"
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_clock.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.clock'`

- [ ] **Step 3: 实现**

`echo/clock.py`:
```python
"""一切时间都从这儿来。生产用 Clock，测试用 FakeClock，任何组件不得直接 import time/asyncio.sleep。"""
import asyncio
import time
from datetime import date, datetime


class Clock:
    def now(self) -> float:
        return time.monotonic()

    def wall(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def today(self) -> str:
        return date.today().isoformat()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeClock(Clock):
    def __init__(self, start: float = 0.0, today: str = "2026-09-05") -> None:
        self._now = start
        self._today = today
        self._waiters: list[tuple[float, asyncio.Future]] = []

    def now(self) -> float:
        return self._now

    def wall(self) -> str:
        return f"{self._today}T+{self._now:.0f}s"

    def today(self) -> str:
        return self._today

    def set_today(self, day: str) -> None:
        self._today = day

    async def sleep(self, seconds: float) -> None:
        if seconds <= 0:
            await asyncio.sleep(0)
            return
        fut = asyncio.get_running_loop().create_future()
        waiter = (self._now + seconds, fut)
        self._waiters.append(waiter)
        try:
            await fut
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    async def advance(self, seconds: float) -> None:
        target = self._now + seconds
        while True:
            due = [w for w in self._waiters if w[0] <= target]
            if not due:
                break
            wake_at, fut = min(due, key=lambda w: w[0])
            self._waiters.remove((wake_at, fut))
            self._now = wake_at
            if not fut.done():
                fut.set_result(None)
            for _ in range(3):
                await asyncio.sleep(0)  # 让被唤醒的任务跑起来（它可能又 sleep 了）
        self._now = target
        for _ in range(3):
            await asyncio.sleep(0)
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_clock.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/clock.py tests/test_clock.py
git commit -m "feat(echo): 时钟抽象，测试可控的 FakeClock

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: 事件与发言锁

**Files:**
- Create: `echo/events.py`, `echo/floor.py`
- Test: `tests/test_floor.py`

**Interfaces:**
- Produces:
  - `echo/events.py`：frozen dataclass，全部继承 `Event(at: float)`：`HumanStarted`、`HumanSaid(text)`、`PuppetStarted(name)`、`PuppetSaid(name, text)`、`PuppetCut(name, spoken)`、`Quiet(seconds)`、`VisitorArrived`、`VisitorLeft(session_id)`、`WokeUp(day)`
  - `echo/floor.py`：`HUMAN = "新朋友"`；`StopFn = Callable[[], Awaitable[str]]`；`class Floor`：`holder: str | None`、`free -> bool`、`try_acquire(name, stop: StopFn) -> bool`、`release(name)`、`async seize_by_human() -> tuple[str, str] | None`（返回被打断的木偶名和已说出的前缀）、`release_human()`

- [ ] **Step 1: 写失败测试**

`tests/test_floor.py`:
```python
from echo.floor import HUMAN, Floor


async def never_stop() -> str:
    raise AssertionError("不该被调用")


async def test_first_come_first_served():
    floor = Floor()
    assert floor.free
    assert floor.try_acquire("Kaka", never_stop)
    assert not floor.try_acquire("Charlie", never_stop)
    assert floor.holder == "Kaka"


async def test_release_only_by_holder():
    floor = Floor()
    floor.try_acquire("Kaka", never_stop)
    floor.release("Charlie")
    assert floor.holder == "Kaka"
    floor.release("Kaka")
    assert floor.free


async def test_human_seizes_and_cuts_speaker():
    floor = Floor()

    async def stop() -> str:
        return "还用问"

    floor.try_acquire("Kaka", stop)
    cut = await floor.seize_by_human()
    assert cut == ("Kaka", "还用问")
    assert floor.holder == HUMAN
    assert not floor.try_acquire("Lucy", never_stop)
    floor.release_human()
    assert floor.free


async def test_human_seizes_free_floor_without_cut():
    floor = Floor()
    assert await floor.seize_by_human() is None
    assert floor.holder == HUMAN
    assert await floor.seize_by_human() is None  # 再叫一次也不会"打断人"
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_floor.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.floor'`

- [ ] **Step 3: 实现**

`echo/events.py`:
```python
"""房间里会发生的事。全部不可变；at 是 Clock.now() 的秒数。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    at: float


@dataclass(frozen=True)
class HumanStarted(Event):
    pass


@dataclass(frozen=True)
class HumanSaid(Event):
    text: str


@dataclass(frozen=True)
class PuppetStarted(Event):
    name: str


@dataclass(frozen=True)
class PuppetSaid(Event):
    name: str
    text: str


@dataclass(frozen=True)
class PuppetCut(Event):
    name: str
    spoken: str


@dataclass(frozen=True)
class Quiet(Event):
    seconds: float


@dataclass(frozen=True)
class VisitorArrived(Event):
    pass


@dataclass(frozen=True)
class VisitorLeft(Event):
    session_id: str


@dataclass(frozen=True)
class WokeUp(Event):
    day: int
```

`echo/floor.py`:
```python
"""发言锁。任何时刻至多一个持有者：某只木偶，或者人。人有绝对优先权。"""
from typing import Awaitable, Callable

HUMAN = "新朋友"
StopFn = Callable[[], Awaitable[str]]


class Floor:
    def __init__(self) -> None:
        self.holder: str | None = None
        self._stop: StopFn | None = None

    @property
    def free(self) -> bool:
        return self.holder is None

    def try_acquire(self, name: str, stop: StopFn) -> bool:
        """木偶抢锁。先到先得；stop 是"你被打断时我怎么让你闭嘴"，返回已说出的前缀。"""
        if self.holder is not None:
            return False
        self.holder, self._stop = name, stop
        return True

    def release(self, name: str) -> None:
        if self.holder == name:
            self.holder, self._stop = None, None

    async def seize_by_human(self) -> tuple[str, str] | None:
        """人开口了。若某只木偶在说，让它停，返回 (名字, 已说出的前缀)。"""
        prev, stop = self.holder, self._stop
        self.holder, self._stop = HUMAN, None
        if prev is None or prev == HUMAN:
            return None
        spoken = await stop() if stop else ""
        return prev, spoken

    def release_human(self) -> None:
        if self.holder == HUMAN:
            self.holder = None
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_floor.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/events.py echo/floor.py tests/test_floor.py
git commit -m "feat(echo): 事件定义与发言锁，人类优先

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: 现场记录

**Files:**
- Create: `echo/transcript.py`
- Test: `tests/test_transcript.py`

**Interfaces:**
- Produces:
  - `@dataclass Entry(at: float, wall: str, kind: str, who: str, text: str = "")`，`kind ∈ {"said","cut","arrived","left","woke"}`
  - `class Transcript(path: Path | None = None)`：`entries: list[Entry]`；`add(at, wall, kind, who, text="") -> Entry`（同时追加 jsonl）；`render(*, now, me, day, visitor_present, speaker, last_spoke_at, quiet_for, window) -> str`

- [ ] **Step 1: 写失败测试**

`tests/test_transcript.py`:
```python
import json

from echo.transcript import Transcript


def test_add_appends_jsonl(tmp_path):
    t = Transcript(tmp_path / "transcript.jsonl")
    t.add(1.0, "w1", "said", "新朋友", "你们好")
    t.add(2.0, "w2", "said", "Kaka", "哼")
    lines = (tmp_path / "transcript.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1]) == {"at": 2.0, "wall": "w2", "kind": "said", "who": "Kaka", "text": "哼"}


def test_render_states_facts_only():
    t = Transcript()
    t.add(0.0, "w", "woke", "", "4")
    t.add(62.0, "w", "arrived", "新朋友")
    t.add(62.0, "w", "said", "新朋友", "你们谁最好看？")
    t.add(69.0, "w", "cut", "Kaka", "还用问吗")
    t.add(76.0, "w", "said", "新朋友", "Charlie 你说呢？")
    out = t.render(now=100.0, me="Kaka", day=4, visitor_present=True,
                   speaker=None, last_spoke_at=69.0, quiet_for=24.0, window=24)
    assert out.splitlines() == [
        "[第 4 天 · 帐篷里有人]",
        "(-100s) （关过机，重新开机。今天是第 4 天）",
        "(-38s) 新朋友 来了",
        "(-38s) 新朋友：你们谁最好看？",
        "(-31s) 你（Kaka）：还用问吗（被打断）",
        "(-24s) 新朋友：Charlie 你说呢？",
        "(现在) 没人在说，已经安静 24 秒。你上一次开口是 31 秒前。",
    ]


def test_render_window_and_speaker_and_never_spoke():
    t = Transcript()
    for i in range(30):
        t.add(float(i), "w", "said", "Lucy", f"第{i}句")
    out = t.render(now=40.0, me="Charlie", day=1, visitor_present=False,
                   speaker="Lucy", last_spoke_at=None, quiet_for=0.0, window=3)
    lines = out.splitlines()
    assert lines[0] == "[第 1 天 · 帐篷里没人]"
    assert lines[1:4] == ["(-13s) Lucy：第27句", "(-12s) Lucy：第28句", "(-11s) Lucy：第29句"]
    assert lines[4] == "(现在) Lucy 正在说。你还没开过口。"


def test_render_minutes():
    t = Transcript()
    out = t.render(now=400.0, me="Lucy", day=2, visitor_present=False,
                   speaker=None, last_spoke_at=100.0, quiet_for=2.0, window=5)
    assert out.splitlines()[-1] == "(现在) 没人在说。你上一次开口是 5 分钟前。"
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_transcript.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.transcript'`

- [ ] **Step 3: 实现**

`echo/transcript.py`:
```python
"""现场记录：只增不减的流水，和"渲染成木偶看到的样子"。渲染只陈述事实。"""
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

    def render(self, *, now: float, me: str, day: int, visitor_present: bool,
               speaker: str | None, last_spoke_at: float | None,
               quiet_for: float, window: int) -> str:
        lines = [f"[第 {day} 天 · {'帐篷里有人' if visitor_present else '帐篷里没人'}]"]
        for e in self.entries[-window:]:
            rel = f"(-{int(now - e.at)}s)"
            who = f"你（{me}）" if e.who == me else e.who
            if e.kind == "said":
                lines.append(f"{rel} {who}：{e.text}")
            elif e.kind == "cut":
                lines.append(f"{rel} {who}：{e.text}（被打断）")
            elif e.kind == "arrived":
                lines.append(f"{rel} 新朋友 来了")
            elif e.kind == "left":
                lines.append(f"{rel} 新朋友 走了")
            elif e.kind == "woke":
                lines.append(f"{rel} （关过机，重新开机。今天是第 {e.text} 天）")
        if speaker is not None:
            status = f"(现在) {speaker} 正在说。"
        elif quiet_for >= 5:
            status = f"(现在) 没人在说，已经安静 {int(quiet_for)} 秒。"
        else:
            status = "(现在) 没人在说。"
        if last_spoke_at is None:
            status += "你还没开过口。"
        else:
            status += f"你上一次开口是 {_ago(now - last_spoke_at)}前。"
        lines.append(status)
        return "\n".join(lines)
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_transcript.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/transcript.py tests/test_transcript.py
git commit -m "feat(echo): 现场记录，落盘与如实渲染

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 5: 记忆落盘

**Files:**
- Create: `echo/memory.py`
- Test: `tests/test_memory.py`

**Interfaces:**
- Produces:
  - `atomic_write_json(path: Path, data) -> None`；`append_jsonl(path: Path, record: dict) -> None`
  - `class ChangeLog(path)`: `append(record: dict)`
  - `class Days(path)`: `days: list[str]`；`wake(today: str) -> int`（今天不在列表就追加并落盘；返回第几天）
  - `@dataclass PuppetMemory(name, path, beliefs=[], relations={}, impressions=[], unspoken=[], updated_at="")`：`PuppetMemory.load(name, state_dir) -> PuppetMemory`；`save(wall)`；`add_unspoken(text, wall, keep)`；`apply(beliefs, relations, impression, session_id, wall, capacity, changelog)`

- [ ] **Step 1: 写失败测试**

`tests/test_memory.py`:
```python
import json

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


def test_apply_records_diff_and_caps(tmp_path):
    log = ChangeLog(tmp_path / "changes.jsonl")
    m = PuppetMemory.load("Charlie", tmp_path)
    m.beliefs = ["艺术是个笑话", "Lucy 需要我保护"]
    m.unspoken = [{"at": "w", "text": "算了"}]
    m.apply(beliefs=["艺术是个笑话", "Lucy 得自己扛", "多余的一条"],
            relations={"Lucy": "她该自己扛"}, impression="有个人说我油腻",
            session_id="s1", wall="w9", capacity=2, changelog=log)
    assert m.beliefs == ["艺术是个笑话", "Lucy 得自己扛"]
    assert m.unspoken == []
    assert m.impressions == [{"session": "s1", "text": "有个人说我油腻"}]
    rec = json.loads((tmp_path / "changes.jsonl").read_text().splitlines()[0])
    assert rec["who"] == "Charlie"
    assert rec["removed"] == ["Lucy 需要我保护"]
    assert rec["added"] == ["Lucy 得自己扛"]
    assert rec["relations"] == {"Lucy": "她该自己扛"}
    assert rec["session"] == "s1"


def test_days_counts_distinct_dates(tmp_path):
    d = Days(tmp_path / "days.json")
    assert d.wake("2026-09-05") == 1
    assert d.wake("2026-09-05") == 1
    assert d.wake("2026-09-06") == 2
    assert Days(tmp_path / "days.json").wake("2026-09-06") == 2
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_memory.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.memory'`

- [ ] **Step 3: 实现**

`echo/memory.py`:
```python
"""每只木偶自己的记忆，以及"随时可拔电"的落盘。只记印象，不记原话。"""
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


_FIELDS = ("beliefs", "relations", "impressions", "unspoken", "updated_at")


@dataclass
class PuppetMemory:
    name: str
    path: Path
    beliefs: list[str] = field(default_factory=list)
    relations: dict[str, str] = field(default_factory=dict)
    impressions: list[dict] = field(default_factory=list)
    unspoken: list[dict] = field(default_factory=list)
    updated_at: str = ""

    @classmethod
    def load(cls, name: str, state_dir: Path) -> "PuppetMemory":
        path = state_dir / f"{name.lower()}.json"
        if not path.exists():
            return cls(name=name, path=path)
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(name=name, path=path, **{k: data[k] for k in _FIELDS if k in data})

    def save(self, wall: str) -> None:
        self.updated_at = wall
        atomic_write_json(self.path, {k: getattr(self, k) for k in _FIELDS})

    def add_unspoken(self, text: str, wall: str, keep: int) -> None:
        self.unspoken.append({"at": wall, "text": text})
        self.unspoken = self.unspoken[-keep:]
        self.save(wall)

    def apply(self, beliefs: list[str], relations: dict[str, str], impression: str,
              session_id: str | None, wall: str, capacity: int, changelog: ChangeLog) -> None:
        beliefs = [b for b in beliefs if b.strip()][:capacity]
        removed = [b for b in self.beliefs if b not in beliefs]
        added = [b for b in beliefs if b not in self.beliefs]
        rel_changed = {k: v for k, v in relations.items() if self.relations.get(k) != v}
        self.beliefs, self.relations = beliefs, dict(relations)
        if impression and session_id:
            self.impressions.append({"session": session_id, "text": impression})
        self.unspoken = []
        self.save(wall)
        changelog.append({"at": wall, "who": self.name, "removed": removed, "added": added,
                          "relations": rel_changed, "impression": impression, "session": session_id})
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_memory.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/memory.py tests/test_memory.py
git commit -m "feat(echo): 木偶记忆与原子落盘，天数与变更日志

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 6: 脑子 —— 接口、假脑子、Claude 脑子

**Files:**
- Create: `echo/brain.py`, `tests/fakes.py`
- Test: `tests/test_brain.py`

**Interfaces:**
- Produces:
  - `@dataclass Decision(speak: bool, text: str)`；`SILENT = Decision(False, "")`
  - `@dataclass Rumination(beliefs: list[str], relations: dict[str, str], impression: str)`
  - `class Brain(Protocol)`: `async decide(system: str, situation: str) -> Decision`；`async ruminate(system: str, material: str, capacity: int) -> Rumination | None`
  - `parse_decision(text) -> Decision`、`parse_rumination(text) -> Rumination`
  - `class ClaudeBrain(model: str, effort: str = "low", ruminate_model: str | None = None, client=None)`
  - `tests/fakes.py`：`class FakeBrain(decisions: list[Decision] = [], rumination: Rumination | None = None, delay: float = 0.0, clock: Clock | None = None)`，每次 `decide` 弹出下一条（用完返回 `SILENT`），记录 `calls: list[tuple[str, str]]`（system, situation）；`ruminate` 返回预设的 rumination，记录 `ruminations: list[str]`（material）

- [ ] **Step 1: 写失败测试**

`tests/fakes.py`:
```python
"""测试用假脑子：可编排、可延迟、不花钱。"""
from echo.brain import SILENT, Decision, Rumination
from echo.clock import Clock


class FakeBrain:
    def __init__(self, decisions: list[Decision] | None = None,
                 rumination: Rumination | None = None,
                 delay: float = 0.0, clock: Clock | None = None) -> None:
        self.decisions = list(decisions or [])
        self.rumination = rumination
        self.delay, self.clock = delay, clock
        self.calls: list[tuple[str, str]] = []
        self.ruminations: list[str] = []

    async def decide(self, system: str, situation: str) -> Decision:
        self.calls.append((system, situation))
        if self.delay and self.clock:
            await self.clock.sleep(self.delay)
        # 延迟之后才弹出：木偶因为新事件取消重来时，台词不会被白白吃掉
        return self.decisions.pop(0) if self.decisions else SILENT

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        self.ruminations.append(material)
        return self.rumination
```

`tests/test_brain.py`:
```python
import json

from echo.brain import Decision, Rumination, parse_decision, parse_rumination
from tests.fakes import FakeBrain


def test_parse_decision():
    assert parse_decision('{"speak": true, "text": "  还用问吗 "}') == Decision(True, "还用问吗")
    assert parse_decision('{"speak": false, "text": ""}') == Decision(False, "")


def test_parse_rumination_relations_as_list():
    text = json.dumps({
        "beliefs": ["a", "b"],
        "relations": [{"who": "Lucy", "view": "她该自己扛"}, {"who": "Kaka", "view": "至少他敢说"}],
        "impression": " 有个人说我油腻 ",
    })
    r = parse_rumination(text)
    assert r == Rumination(["a", "b"], {"Lucy": "她该自己扛", "Kaka": "至少他敢说"}, "有个人说我油腻")


async def test_fake_brain_pops_then_silent():
    b = FakeBrain([Decision(True, "哼")])
    assert await b.decide("s", "x") == Decision(True, "哼")
    assert await b.decide("s", "y") == Decision(False, "")
    assert b.calls == [("s", "x"), ("s", "y")]
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_brain.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.brain'`

- [ ] **Step 3: 实现**

`echo/brain.py`:
```python
"""木偶的脑子。接口两个动作：decide（现在开口吗，说什么）和 ruminate（经过这些，你现在相信什么）。
调用失败 = 这一轮不开口 / 这一次不反刍，绝不把房间卡住。"""
import json
import logging
from dataclasses import dataclass
from typing import Protocol

import anthropic

log = logging.getLogger("echo.brain")


@dataclass
class Decision:
    speak: bool
    text: str


SILENT = Decision(False, "")


@dataclass
class Rumination:
    beliefs: list[str]
    relations: dict[str, str]
    impression: str


class Brain(Protocol):
    async def decide(self, system: str, situation: str) -> Decision: ...
    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None: ...


DECISION_SCHEMA = {
    "type": "object",
    "properties": {"speak": {"type": "boolean"}, "text": {"type": "string"}},
    "required": ["speak", "text"],
    "additionalProperties": False,
}

RUMINATION_SCHEMA = {
    "type": "object",
    "properties": {
        "beliefs": {"type": "array", "items": {"type": "string"}},
        "relations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"who": {"type": "string"}, "view": {"type": "string"}},
                "required": ["who", "view"],
                "additionalProperties": False,
            },
        },
        "impression": {"type": "string"},
    },
    "required": ["beliefs", "relations", "impression"],
    "additionalProperties": False,
}


def parse_decision(text: str) -> Decision:
    data = json.loads(text)
    return Decision(bool(data.get("speak")), str(data.get("text", "")).strip())


def parse_rumination(text: str) -> Rumination:
    data = json.loads(text)
    return Rumination(
        beliefs=[str(b).strip() for b in data.get("beliefs", [])],
        relations={str(r["who"]): str(r["view"]).strip() for r in data.get("relations", [])},
        impression=str(data.get("impression", "")).strip(),
    )


class ClaudeBrain:
    def __init__(self, model: str, effort: str = "low",
                 ruminate_model: str | None = None, client=None) -> None:
        self.client = client or anthropic.AsyncAnthropic()
        self.model = model
        self.effort = effort
        self.ruminate_model = ruminate_model or model

    async def _json(self, model: str, system: str, user: str, schema: dict, max_tokens: int) -> str | None:
        try:
            r = await self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort,
                               "format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APIConnectionError as e:
            log.warning("网络: %s", e)
            return None
        except anthropic.APIStatusError as e:
            log.warning("API %s: %s", e.status_code, e.message)
            return None
        if r.stop_reason == "refusal":
            log.warning("模型拒答 (%s)", getattr(r.stop_details, "category", None))
            return None
        return next((b.text for b in r.content if b.type == "text"), None)

    async def decide(self, system: str, situation: str) -> Decision:
        text = await self._json(self.model, system, situation, DECISION_SCHEMA, 800)
        if text is None:
            return SILENT
        try:
            return parse_decision(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 decision 失败: %s / %r", e, text[:200])
            return SILENT

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        text = await self._json(self.ruminate_model, system, material, RUMINATION_SCHEMA, 2000)
        if text is None:
            return None
        try:
            r = parse_rumination(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 rumination 失败: %s / %r", e, text[:200])
            return None
        r.beliefs = r.beliefs[:capacity]
        return r
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_brain.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/brain.py tests/fakes.py tests/test_brain.py
git commit -m "feat(echo): 脑子接口、结构化输出解析、Claude 实现与测试假脑

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 7: 嘴与动作（关闭模式）

**Files:**
- Create: `echo/mouth.py`, `echo/motors.py`
- Test: `tests/test_mouth_motors.py`

**Interfaces:**
- Produces:
  - `class Mouth(Protocol)`: `async say(name, text) -> tuple[str, bool]`（返回已说出的文字、是否说完）；`async stop() -> str`（立即停，返回已说出前缀；没在说返回 `""`）
  - `class PrintMouth(clock, chars_per_second=6.0, out=print)`
  - `class Motors(Protocol)`: `async speaking(name)`、`async silent(name)`、`async restless(name)`
  - `class PrintMotors(out=print)`：`log: list[tuple[str, str]]`

- [ ] **Step 1: 写失败测试**

`tests/test_mouth_motors.py`:
```python
import asyncio

from echo.motors import PrintMotors
from echo.mouth import PrintMouth


async def test_print_mouth_finishes(clock):
    lines = []
    mouth = PrintMouth(clock, chars_per_second=10, out=lines.append)
    task = asyncio.create_task(mouth.say("Kaka", "一二三四五六七八九十"))  # 10 字 = 1 秒
    await asyncio.sleep(0)
    await clock.advance(1.5)
    assert await task == ("一二三四五六七八九十", True)
    assert lines == ["@Kaka: 一二三四五六七八九十"]
    assert await mouth.stop() == ""  # 已经说完，没什么可停


async def test_print_mouth_stopped_midway(clock):
    lines = []
    mouth = PrintMouth(clock, chars_per_second=10, out=lines.append)
    task = asyncio.create_task(mouth.say("Kaka", "一二三四五六七八九十"))
    await asyncio.sleep(0)
    await clock.advance(0.4)
    prefix = await mouth.stop()
    assert prefix == "一二三四"
    assert await task == ("一二三四", False)
    assert lines[-1] == "@Kaka: …（被打断）"


async def test_print_motors_logs():
    out = []
    m = PrintMotors(out=out.append)
    await m.speaking("Lucy")
    await m.restless("Kaka")
    await m.silent("Lucy")
    assert m.log == [("speaking", "Lucy"), ("restless", "Kaka"), ("silent", "Lucy")]
    assert len(out) == 3
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_mouth_motors.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.motors'`

- [ ] **Step 3: 实现**

`echo/mouth.py`:
```python
"""嘴。阶段 1 只有关闭模式：打印 + 按字数睡眠，行为对引擎和真 TTS 一致（可被 stop 掐断）。"""
import asyncio
from typing import Callable, Protocol

from .clock import Clock


class Mouth(Protocol):
    async def say(self, name: str, text: str) -> tuple[str, bool]: ...
    async def stop(self) -> str: ...


class PrintMouth:
    def __init__(self, clock: Clock, chars_per_second: float = 6.0,
                 out: Callable[[str], None] = print) -> None:
        self.clock, self.cps, self.out = clock, chars_per_second, out
        self._stop_requested: asyncio.Event | None = None
        self._ack: asyncio.Event | None = None
        self._prefix = ""

    async def say(self, name: str, text: str) -> tuple[str, bool]:
        self.out(f"@{name}: {text}")
        self._stop_requested, self._ack, self._prefix = asyncio.Event(), asyncio.Event(), ""
        duration = max(len(text) / self.cps, 0.1)
        start = self.clock.now()
        sleeper = asyncio.ensure_future(self.clock.sleep(duration))
        stopper = asyncio.ensure_future(self._stop_requested.wait())
        try:
            done, _ = await asyncio.wait({sleeper, stopper}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for t in (sleeper, stopper):
                if not t.done():
                    t.cancel()
        if stopper in done:
            frac = min((self.clock.now() - start) / duration, 1.0)
            self._prefix = text[: int(len(text) * frac)]
            self.out(f"@{name}: …（被打断）")
            self._ack.set()
            result = (self._prefix, False)
        else:
            result = (text, True)
        self._stop_requested = self._ack = None
        return result

    async def stop(self) -> str:
        if self._stop_requested is None:
            return ""
        req, ack = self._stop_requested, self._ack
        req.set()
        await ack.wait()
        return self._prefix
```

`echo/motors.py`:
```python
"""木偶机构。阶段 1 只有关闭模式：打印。三态：说话 / 静默 / 躁动。"""
from typing import Callable, Protocol


class Motors(Protocol):
    async def speaking(self, name: str) -> None: ...
    async def silent(self, name: str) -> None: ...
    async def restless(self, name: str) -> None: ...


class PrintMotors:
    def __init__(self, out: Callable[[str], None] = print) -> None:
        self.out = out
        self.log: list[tuple[str, str]] = []

    async def speaking(self, name: str) -> None:
        self.log.append(("speaking", name))
        self.out(f"[motors] {name} 动")

    async def silent(self, name: str) -> None:
        self.log.append(("silent", name))
        self.out(f"[motors] {name} 停")

    async def restless(self, name: str) -> None:
        self.log.append(("restless", name))
        self.out(f"[motors] {name} 躁动")
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_mouth_motors.py -q`
Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/mouth.py echo/motors.py tests/test_mouth_motors.py
git commit -m "feat(echo): 嘴与动作的关闭模式，可被打断

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 8: 到访跟踪与配置

**Files:**
- Create: `echo/session.py`, `echo/config.py`, `config.toml`
- Test: `tests/test_session_config.py`

**Interfaces:**
- Produces:
  - `class VisitorTracker`: `present: bool`、`last_human_at: float | None`、`session_id: str | None`；`saw_human(now, wall) -> bool`（True = 新的一场开始）；`check_left(now, timeout) -> str | None`（返回结束的 session_id）
  - `@dataclass Config`：字段见下；`model` 属性按 `use_alt` 返回 `alt_model` 或 `puppet_model`
  - `parse_config(text: str, base: Path) -> Config`；`class LiveConfig(path)`：`current -> Config`（mtime 变了就重读）

- [ ] **Step 1: 写失败测试**

`tests/test_session_config.py`:
```python
import os
from pathlib import Path

from echo.config import LiveConfig, parse_config
from echo.session import VisitorTracker

MINIMAL = """
[model]
puppet = "claude-opus-5"
[room]
quiet_interval_alone = 120
"""


def test_visitor_tracker_sessions():
    v = VisitorTracker()
    assert v.saw_human(10.0, "w10") is True
    assert v.present and v.session_id == "w10"
    assert v.saw_human(20.0, "w20") is False
    assert v.check_left(50.0, timeout=75) is None
    assert v.check_left(96.0, timeout=75) == "w10"
    assert not v.present and v.session_id is None
    assert v.saw_human(100.0, "w100") is True


def test_parse_config_defaults_and_overrides(tmp_path):
    c = parse_config(MINIMAL, base=tmp_path)
    assert c.puppet_model == "claude-opus-5"
    assert c.puppet_effort == "low"
    assert c.quiet_interval_alone == 120
    assert c.quiet_interval_with_visitor == 8
    assert c.visitor_timeout == 75
    assert c.window == 24
    assert c.ruminate_every == 12
    assert c.belief_capacity == 6
    assert c.unspoken_keep == 8
    assert c.ears == "console" and c.mouth == "off" and c.motors == "off"
    assert c.state_dir == tmp_path / "state"
    assert c.model == "claude-opus-5"


def test_use_alt_switches_model(tmp_path):
    c = parse_config('[model]\npuppet = "claude-opus-5"\nalt = "claude-haiku-4-5"\nuse_alt = true\n', base=tmp_path)
    assert c.model == "claude-haiku-4-5"


def test_live_config_reloads_on_mtime(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(MINIMAL, encoding="utf-8")
    live = LiveConfig(p)
    assert live.current.quiet_interval_alone == 120
    p.write_text(MINIMAL.replace("120", "30"), encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
    assert live.current.quiet_interval_alone == 30
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_session_config.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.config'`

- [ ] **Step 3: 实现**

`echo/session.py`:
```python
"""一场到访：从第一句人声开始，到静默超过阈值结束。没有传感器，只有人声。"""


class VisitorTracker:
    def __init__(self) -> None:
        self.present = False
        self.last_human_at: float | None = None
        self.session_id: str | None = None

    def saw_human(self, now: float, wall: str) -> bool:
        self.last_human_at = now
        if self.present:
            return False
        self.present, self.session_id = True, wall
        return True

    def check_left(self, now: float, timeout: float) -> str | None:
        if not self.present or self.last_human_at is None or now - self.last_human_at < timeout:
            return None
        ended, self.present, self.session_id = self.session_id, False, None
        return ended
```

`echo/config.py`:
```python
"""旋钮。改 config.toml 里的数字，下一轮生效，不用重启。"""
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    puppet_model: str
    puppet_effort: str
    ruminate_model: str
    alt_model: str
    use_alt: bool
    window: int
    quiet_interval_with_visitor: float
    quiet_interval_alone: float
    visitor_timeout: float
    ruminate_every: int
    belief_capacity: int
    unspoken_keep: int
    ears: str
    mouth: str
    motors: str
    serial_port: str
    serial_baud: int
    state_dir: Path

    @property
    def model(self) -> str:
        return self.alt_model if self.use_alt else self.puppet_model


def parse_config(text: str, base: Path) -> Config:
    d = tomllib.loads(text)
    m, r, mem = d.get("model", {}), d.get("room", {}), d.get("memory", {})
    ears, mouth, motors = d.get("ears", {}), d.get("mouth", {}), d.get("motors", {})
    puppet = m.get("puppet", "claude-opus-5")
    return Config(
        puppet_model=puppet,
        puppet_effort=m.get("puppet_effort", "low"),
        ruminate_model=m.get("ruminate", puppet),
        alt_model=m.get("alt", "claude-haiku-4-5"),
        use_alt=bool(m.get("use_alt", False)),
        window=int(r.get("window", 24)),
        quiet_interval_with_visitor=float(r.get("quiet_interval_with_visitor", 8)),
        quiet_interval_alone=float(r.get("quiet_interval_alone", 120)),
        visitor_timeout=float(r.get("visitor_timeout", 75)),
        ruminate_every=int(mem.get("ruminate_every", 12)),
        belief_capacity=int(mem.get("belief_capacity", 6)),
        unspoken_keep=int(mem.get("unspoken_keep", 8)),
        ears=ears.get("mode", "console"),
        mouth=mouth.get("mode", "off"),
        motors=motors.get("mode", "off"),
        serial_port=motors.get("port", "/dev/cu.usbserial-1130"),
        serial_baud=int(motors.get("baud", 9600)),
        state_dir=base / d.get("state_dir", "state"),
    )


class LiveConfig:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._cfg: Config | None = None

    @property
    def current(self) -> Config:
        mtime = self.path.stat().st_mtime
        if self._cfg is None or mtime != self._mtime:
            self._cfg = parse_config(self.path.read_text(encoding="utf-8"), self.path.parent)
            self._mtime = mtime
        return self._cfg
```

`config.toml`（仓库根）:
```toml
# 回音室 · 旋钮。改数字，下一轮生效，不用重启。

[model]
puppet = "claude-opus-5"
puppet_effort = "low"
ruminate = "claude-opus-5"
alt = "claude-haiku-4-5"
use_alt = false

[room]
window = 24                       # 木偶看到的现场记录条数
quiet_interval_with_visitor = 8   # 秒。有人时，安静多久算"安静"
quiet_interval_alone = 120        # 秒。没人时 —— 这就是自聊的节奏
visitor_timeout = 75              # 秒。人声停多久算一场到访结束

[memory]
ruminate_every = 12               # 每听到几句反刍一次
belief_capacity = 6
unspoken_keep = 8

[ears]
mode = "console"                  # console | realtime（阶段 2）

[mouth]
mode = "off"                      # off | tts（阶段 3）

[motors]
mode = "off"                      # off | serial（阶段 4）
port = "/dev/cu.usbserial-1130"
baud = 9600
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_session_config.py -q`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/session.py echo/config.py config.toml tests/test_session_config.py
git commit -m "feat(echo): 到访跟踪与热重载配置

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 9: 房间

**Files:**
- Create: `echo/room.py`
- Test: `tests/test_room.py`

**Interfaces:**
- Consumes: `Clock`、`Transcript`、`Floor`/`HUMAN`、`VisitorTracker`、`Config`、events
- Produces: `class Room(clock, transcript, floor, cfg: Callable[[], Config])`：
  - `subscribe() -> asyncio.Queue`；`async publish(event)`（该进现场记录的进，所有订阅者都收到）
  - `day: int`；`visitor: VisitorTracker`；`last_activity: float`；`speaker -> str | None`
  - `async wake(day)`；`async human_started()`；`async human_said(text)`
  - `async run()`：每秒一拍：到访超时 → `VisitorLeft`；锁空闲且安静够久 → `Quiet`

- [ ] **Step 1: 写失败测试**

`tests/test_room.py`:
```python
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
    assert [type(e) for e in drain(q1)] == [WokeUp, VisitorArrived, HumanSaid]
    assert [type(e) for e in drain(q2)] == [WokeUp, VisitorArrived, HumanSaid]
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
    assert [type(e) for e in drain(q)] == [VisitorArrived, HumanSaid, HumanSaid]


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
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_room.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.room'`

- [ ] **Step 3: 实现**

`echo/room.py`:
```python
"""房间：事件总线、现场记录、发言锁的人类优先、沉默计时、到访起止。不决定谁该说。"""
import asyncio
from typing import Callable

from .clock import Clock
from .config import Config
from .events import (Event, HumanSaid, HumanStarted, PuppetCut, PuppetSaid, PuppetStarted,
                     Quiet, VisitorArrived, VisitorLeft, WokeUp)
from .floor import HUMAN, Floor
from .session import VisitorTracker
from .transcript import Transcript


class Room:
    def __init__(self, clock: Clock, transcript: Transcript, floor: Floor,
                 cfg: Callable[[], Config]) -> None:
        self.clock, self.transcript, self.floor, self.cfg = clock, transcript, floor, cfg
        self.visitor = VisitorTracker()
        self.day = 0
        self.last_activity = clock.now()
        self._last_quiet = clock.now()
        self._subs: list[asyncio.Queue] = []

    # --- 订阅与发布 ---

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.append(q)
        return q

    @property
    def speaker(self) -> str | None:
        return self.floor.holder

    async def publish(self, ev: Event) -> None:
        wall = self.clock.wall()
        if isinstance(ev, HumanSaid):
            self.transcript.add(ev.at, wall, "said", HUMAN, ev.text)
            self.last_activity = ev.at
        elif isinstance(ev, PuppetSaid):
            self.transcript.add(ev.at, wall, "said", ev.name, ev.text)
            self.last_activity = ev.at
        elif isinstance(ev, PuppetCut):
            self.transcript.add(ev.at, wall, "cut", ev.name, ev.spoken)
            self.last_activity = ev.at
        elif isinstance(ev, VisitorArrived):
            self.transcript.add(ev.at, wall, "arrived", HUMAN)
        elif isinstance(ev, VisitorLeft):
            self.transcript.add(ev.at, wall, "left", HUMAN)
        elif isinstance(ev, WokeUp):
            self.transcript.add(ev.at, wall, "woke", "", str(ev.day))
        elif isinstance(ev, (HumanStarted, PuppetStarted)):
            self.last_activity = ev.at
        for q in self._subs:
            q.put_nowait(ev)

    # --- 人 ---

    async def wake(self, day: int) -> None:
        self.day = day
        await self.publish(WokeUp(self.clock.now(), day))

    async def human_started(self) -> None:
        now = self.clock.now()
        cut = await self.floor.seize_by_human()
        await self.publish(HumanStarted(now))
        if cut is not None:
            name, spoken = cut
            await self.publish(PuppetCut(now, name, spoken))

    async def human_said(self, text: str) -> None:
        if self.floor.holder != HUMAN:
            await self.human_started()
        now = self.clock.now()
        self.floor.release_human()
        if self.visitor.saw_human(now, self.clock.wall()):
            await self.publish(VisitorArrived(now))
        await self.publish(HumanSaid(now, text))

    # --- 计时 ---

    async def run(self) -> None:
        while True:
            await self.clock.sleep(1.0)
            now = self.clock.now()
            c = self.cfg()
            ended = self.visitor.check_left(now, c.visitor_timeout)
            if ended is not None:
                await self.publish(VisitorLeft(now, ended))
            interval = c.quiet_interval_with_visitor if self.visitor.present else c.quiet_interval_alone
            since = now - self.last_activity
            if self.floor.free and since >= interval and now - self._last_quiet >= interval:
                self._last_quiet = now
                await self.publish(Quiet(now, since))
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_room.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add echo/room.py tests/test_room.py
git commit -m "feat(echo): 房间 —— 总线、人类优先打断、沉默计时、到访起止

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 10: 木偶

**Files:**
- Create: `echo/puppet.py`
- Test: `tests/test_puppet.py`

**Interfaces:**
- Consumes: `Room`、`PuppetMemory`、`ChangeLog`、`Brain`、`Mouth`、`Motors`、`Clock`、`Config`
- Produces: `class Puppet(name, persona, memory, brain, room, mouth, motors, clock, cfg: Callable[[], Config], changelog: ChangeLog, sessions_path: Path | None = None, log: Callable[[str], None] = print)`：
  - `system_prompt() -> str`、`situation() -> str`
  - `async run()`（永不返回）；`async consider()`；`async speak(text)`；`async ruminate(session_id: str | None)`
  - `last_spoke_at: float | None`、`speaking: bool`、`heard_since_ruminate: int`
  - 常量 `NEUTRAL`（固定的中性说明）、`RUMINATE_ASK`

- [ ] **Step 1: 写失败测试**

`tests/test_puppet.py`:
```python
import asyncio
import json
from pathlib import Path

from echo.brain import Decision, Rumination
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
belief_capacity = 2
unspoken_keep = 8
""", base=Path("/tmp"))


def build(clock, tmp_path, names_and_brains, out=None):
    out = out if out is not None else []
    room = Room(clock, Transcript(), Floor(), lambda: CFG)
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
    for _ in range(5):
        await asyncio.sleep(0)
    if seconds:
        await clock.advance(seconds)


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


async def test_loser_swallows_words(clock, tmp_path):
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
    assert [u["text"] for u in charlie_mem.unspoken] == ["荒谬的问题"]
    assert any("Charlie 想说但没抢到" in line for line in out)
    for t in tasks:
        t.cancel()


async def test_silence_is_silence(clock, tmp_path):
    lucy = FakeBrain([Decision(False, "")])
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Lucy", lucy)])
    task = asyncio.create_task(puppets["Lucy"].run())
    await room.human_said("在吗？")
    await settle(clock, 1)
    assert room.floor.free and motors.log == []
    assert any("Lucy 没开口" in line for line in out)
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
    rum = Rumination(["新的信念", "第二条", "第三条会被截掉"], {"Lucy": "她该自己扛"}, "有个人很吵")
    charlie = FakeBrain([], rumination=rum)
    room, puppets, mouth, motors, out = build(clock, tmp_path, [("Charlie", charlie)])
    task = asyncio.create_task(puppets["Charlie"].run())
    for i in range(3):  # ruminate_every = 3
        await room.human_said(f"第{i}句")
        await settle(clock)
    await settle(clock)
    assert len(charlie.ruminations) == 1
    mem = PuppetMemory.load("Charlie", tmp_path)
    assert mem.beliefs == ["新的信念", "第二条"]
    assert mem.relations == {"Lucy": "她该自己扛"}
    assert mem.impressions == []  # 没到一场结束，不记印象
    assert json.loads((tmp_path / "changes.jsonl").read_text().splitlines()[0])["added"] == ["新的信念", "第二条"]

    await room.publish(VisitorLeft(clock.now(), "s1"))
    await settle(clock)
    assert len(charlie.ruminations) == 2
    mem = PuppetMemory.load("Charlie", tmp_path)
    assert mem.impressions == [{"session": "s1", "text": "有个人很吵"}]
    star = json.loads((tmp_path / "sessions.jsonl").read_text().splitlines()[0])
    assert star == {"session": "s1", "who": "Charlie", "impression": "有个人很吵", "at": clock.wall()}
    task.cancel()


def _drain(q):
    out = []
    while not q.empty():
        out.append(q.get_nowait())
    return out
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_puppet.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.puppet'`

- [ ] **Step 3: 实现**

`echo/puppet.py`:
```python
"""一只木偶 = 一个循环。收现场记录 → 在角色里决定说不说 → 先到先得抢锁 → 说 / 咽回去。
这里没有任何"谁该说"的逻辑；有的话就是 bug。"""
import asyncio
from pathlib import Path
from typing import Callable

from .brain import Brain
from .clock import Clock
from .config import Config
from .events import Event, HumanSaid, PuppetCut, PuppetSaid, PuppetStarted, VisitorLeft
from .memory import ChangeLog, PuppetMemory, append_jsonl
from .motors import Motors
from .mouth import Mouth
from .room import Room

NEUTRAL = (
    "你在一个帐篷里，和另外两位在一起。下面是刚才发生的事。"
    "你可以开口，也可以不开口。一次只能有一个在说；如果别人先开口了，你这句就说不出来。"
    "开口就 speak=true 并把要说的话放在 text 里；不开口就 speak=false。"
)

RUMINATE_ASK = "经过这些，你现在相信什么？你怎么看另外两位？这位来过的人给你留下了什么？"


class Puppet:
    def __init__(self, name: str, persona: str, memory: PuppetMemory, brain: Brain, room: Room,
                 mouth: Mouth, motors: Motors, clock: Clock, cfg: Callable[[], Config],
                 changelog: ChangeLog, sessions_path: Path | None = None,
                 log: Callable[[str], None] = print) -> None:
        self.name, self.persona, self.memory, self.brain = name, persona, memory, brain
        self.room, self.mouth, self.motors, self.clock, self.cfg = room, mouth, motors, clock, cfg
        self.changelog, self.sessions_path, self.log = changelog, sessions_path, log
        self.last_spoke_at: float | None = None
        self.speaking = False
        self.heard_since_ruminate = 0
        self._deciding: asyncio.Task | None = None
        self._ruminate_lock = asyncio.Lock()

    # --- 它看到的世界 ---

    def system_prompt(self) -> str:
        parts = [self.persona.strip()]
        m = self.memory
        if m.beliefs:
            parts.append("你现在相信：\n" + "\n".join(f"- {b}" for b in m.beliefs))
        if m.relations:
            parts.append("你对另外两位的看法：\n" + "\n".join(f"- {k}：{v}" for k, v in m.relations.items()))
        if m.impressions:
            parts.append("来过的人给你留下的印象：\n" + "\n".join(f"- {i['text']}" for i in m.impressions[-5:]))
        parts.append(NEUTRAL)
        return "\n\n".join(parts)

    def situation(self) -> str:
        now = self.clock.now()
        return self.room.transcript.render(
            now=now, me=self.name, day=self.room.day, visitor_present=self.room.visitor.present,
            speaker=self.room.speaker, last_spoke_at=self.last_spoke_at,
            quiet_for=now - self.room.last_activity, window=self.cfg().window)

    # --- 循环 ---

    async def run(self) -> None:
        q = self.room.subscribe()
        while True:
            ev: Event = await q.get()
            while not q.empty():
                ev = q.get_nowait()  # 只对最新的现场做反应
            if isinstance(ev, (HumanSaid, PuppetSaid, PuppetCut)):
                self.heard_since_ruminate += 1
            ended = ev.session_id if isinstance(ev, VisitorLeft) else None
            if ended is not None or self.heard_since_ruminate >= self.cfg().ruminate_every:
                asyncio.create_task(self.ruminate(ended))
            if self.speaking:
                continue
            if self._deciding is not None and not self._deciding.done():
                self._deciding.cancel()
            self._deciding = asyncio.create_task(self.consider())

    async def consider(self) -> None:
        decision = await self.brain.decide(self.system_prompt(), self.situation())
        if not decision.speak or not decision.text:
            self.log(f"  ({self.name} 没开口)")
            return
        if not self.room.floor.try_acquire(self.name, self.mouth.stop):
            self.memory.add_unspoken(decision.text, self.clock.wall(), self.cfg().unspoken_keep)
            self.log(f"  ({self.name} 想说但没抢到：{decision.text})")
            return
        asyncio.create_task(self.speak(decision.text))

    async def speak(self, text: str) -> None:
        self.speaking = True
        started = self.clock.now()
        self.last_spoke_at = started
        try:
            await self.room.publish(PuppetStarted(started, self.name))
            await self.motors.speaking(self.name)
            spoken, completed = await self.mouth.say(self.name, text)
            await self.motors.silent(self.name)
            if completed:
                self.room.floor.release(self.name)
                await self.room.publish(PuppetSaid(self.clock.now(), self.name, text))
            # 被打断的情况：房间已经把锁给了人、记了 cut，这里什么都不用做
        finally:
            self.speaking = False

    # --- 反刍 ---

    async def ruminate(self, session_id: str | None) -> None:
        async with self._ruminate_lock:
            self.heard_since_ruminate = 0
            c = self.cfg()
            material = self.situation()
            if self.memory.unspoken:
                material += "\n\n你想说但没说出口的：\n" + "\n".join(f"- {u['text']}" for u in self.memory.unspoken)
            material += "\n\n" + RUMINATE_ASK
            result = await self.brain.ruminate(self.system_prompt(), material, c.belief_capacity)
            if result is None:
                return
            wall = self.clock.wall()
            impression = result.impression if session_id else ""
            self.memory.apply(result.beliefs, result.relations, impression, session_id,
                              wall, c.belief_capacity, self.changelog)
            if session_id and impression and self.sessions_path is not None:
                append_jsonl(self.sessions_path, {"session": session_id, "who": self.name,
                                                  "impression": impression, "at": wall})
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_puppet.py -q`
Expected: `5 passed`

如果 `test_loser_swallows_words` 偶发失败：检查 `settle` 的 `advance` 是否足够让 `FakeBrain.delay` 到期 —— Kaka 0.1 秒、Charlie 0.5 秒，先 `advance(0.2)` 再 `advance(0.5)`。

- [ ] **Step 5: 全量跑一遍**

Run: `.venv/bin/pytest -q`
Expected: `37 passed`（时钟 4 · 锁 4 · 现场记录 4 · 记忆 5 · 脑子 3 · 嘴与动作 3 · 到访与配置 4 · 房间 5 · 木偶 5）

- [ ] **Step 6: Commit**

```bash
git add echo/puppet.py tests/test_puppet.py
git commit -m "feat(echo): 木偶循环 —— 先到先得、咽回去、被打断、反刍

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 11: 控制台、主程序、真机冒烟

**Files:**
- Create: `echo/console.py`, `echo/__main__.py`
- Test: `tests/test_console.py`

**Interfaces:**
- Produces:
  - `class Console(room, readline: Callable[[], Awaitable[str | None]] | None = None)`：`async run()`（readline 返回 None 时退出）
  - `python -m echo [--config config.toml] [--fake]`：`--fake` 用三只脚本化的 FakeBrain（不需要 key），否则用 `ClaudeBrain`

- [ ] **Step 1: 写失败测试**

`tests/test_console.py`:
```python
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
```

- [ ] **Step 2: 跑，确认失败**

Run: `.venv/bin/pytest tests/test_console.py -q`
Expected: `ModuleNotFoundError: No module named 'echo.console'`

- [ ] **Step 3: 实现控制台**

`echo/console.py`:
```python
"""键盘替身。发出和耳朵一模一样的事件：一行 = 开口 + 说完；单独一个 "." = 只开口（测打断）。"""
import asyncio
import sys
from typing import Awaitable, Callable

ReadLine = Callable[[], Awaitable[str | None]]


async def _stdin_line() -> str | None:
    loop = asyncio.get_running_loop()
    line = await loop.run_in_executor(None, sys.stdin.readline)
    return line if line else None


class Console:
    def __init__(self, room, readline: ReadLine | None = None) -> None:
        self.room = room
        self._readline = readline or _stdin_line
        self._open = False  # 已经发过"开口"、还没发"说完"

    async def run(self) -> None:
        while True:
            line = await self._readline()
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            if line == ".":
                if not self._open:
                    await self.room.human_started()
                    self._open = True
                continue
            if not self._open:
                await self.room.human_started()
            self._open = False
            await self.room.human_said(line)
```

- [ ] **Step 4: 跑，确认通过**

Run: `.venv/bin/pytest tests/test_console.py -q`
Expected: `2 passed`

- [ ] **Step 5: 写主程序**

`echo/__main__.py`:
```python
"""组装与启动。python -m echo [--config config.toml] [--fake]"""
import argparse
import asyncio
import logging
from itertools import cycle
from pathlib import Path

from .brain import ClaudeBrain, Decision, Rumination
from .clock import Clock
from .config import LiveConfig
from .console import Console
from .floor import Floor
from .memory import ChangeLog, Days, PuppetMemory
from .motors import PrintMotors
from .mouth import PrintMouth
from .puppet import Puppet
from .room import Room
from .transcript import Transcript

NAMES = ("Charlie", "Lucy", "Kaka")
ROOT = Path(__file__).resolve().parent.parent


def load_persona(name: str) -> str:
    return (ROOT / "charactor_setting" / f"{name}.txt").read_text(encoding="utf-8")


class ScriptedBrain:
    """--fake 用：轮流说几句固定台词，让人不花钱就能看到锁、打断、反刍在跑。"""

    def __init__(self, name: str) -> None:
        lines = {
            "Charlie": ["这问题问得真荒谬。", "Lucy 你别理他。"],
            "Lucy": ["……我不知道。"],
            "Kaka": ["还用问吗，当然是我。", "你们看我的羽毛。", "哼。"],
        }[name]
        self._it = cycle([Decision(True, t) for t in lines] + [Decision(False, "")])

    async def decide(self, system: str, situation: str) -> Decision:
        await asyncio.sleep(0.3)
        return next(self._it)

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        return Rumination(["（假反刍）我更确定了"], {}, "有个人来过")


async def main_async(config_path: Path, fake: bool) -> None:
    live = LiveConfig(config_path)
    c = live.current
    clock = Clock()
    c.state_dir.mkdir(parents=True, exist_ok=True)
    day = Days(c.state_dir / "days.json").wake(clock.today())

    room = Room(clock, Transcript(c.state_dir / "transcript.jsonl"), Floor(), lambda: live.current)
    mouth = PrintMouth(clock)
    motors = PrintMotors()
    changelog = ChangeLog(c.state_dir / "changes.jsonl")
    sessions = c.state_dir / "sessions.jsonl"

    puppets = []
    for name in NAMES:
        brain = ScriptedBrain(name) if fake else ClaudeBrain(
            model=c.model, effort=c.puppet_effort, ruminate_model=c.ruminate_model)
        puppets.append(Puppet(name, load_persona(name), PuppetMemory.load(name, c.state_dir),
                              brain, room, mouth, motors, clock, lambda: live.current,
                              changelog, sessions))

    print(f"第 {day} 天。打字说话，回车发送；单独一个 . 表示先开口（打断）。Ctrl-C 退出。")
    await room.wake(day)
    background = [asyncio.create_task(room.run())] + [asyncio.create_task(p.run()) for p in puppets]
    try:
        await Console(room).run()
    finally:
        await mouth.stop()
        for name in NAMES:
            await motors.silent(name)
        for t in background:
            t.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(prog="echo")
    parser.add_argument("--config", type=Path, default=ROOT / "config.toml")
    parser.add_argument("--fake", action="store_true", help="用脚本化的假脑子，不需要 key")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
    try:
        asyncio.run(main_async(args.config, args.fake))
    except KeyboardInterrupt:
        print("\n关机（暂停，不是清空）。")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: 假脑子冒烟**

Run:
```bash
cd "/Users/dihu/Documents/remake echo chamber realm/echo-chamber-realms" && printf '你们谁最好看？\n.\n等等\n' | .venv/bin/python -m echo --fake
```
Expected（顺序可能略有不同，因为三只是并发的）：
- 第一行 `第 1 天。打字说话…`
- `@Kaka: 还用问吗，当然是我。` 和 `[motors] Kaka 动`
- 另外两只之一 `想说但没抢到` 或 `没开口`
- 收到 `.` 后：`@Kaka: …（被打断）` 或（若已说完）无打断
- 退出后 `state/` 下有 `days.json`、`transcript.jsonl`、`charlie.json`/`lucy.json`/`kaka.json`

再跑一次同样的命令：第一行应为 `第 1 天`（同一天不加），`transcript.jsonl` 追加而不是覆盖，木偶的 `unspoken` 还在。

- [ ] **Step 7: 真脑子冒烟（需要 ANTHROPIC_API_KEY）**

Run:
```bash
cd "/Users/dihu/Documents/remake echo chamber realm/echo-chamber-realms" && ANTHROPIC_API_KEY=... .venv/bin/python -m echo
```
然后手动输入几句：`你们谁最好看？`、`Lucy 你怎么看？`、安静等 10 秒看 `quiet` 之后有没有谁开口。
Expected：三只按人设各自决定；终端能看到谁抢到、谁咽回去、谁沉默。没有 key 就跳过这一步并在交接时说明。

- [ ] **Step 8: Commit**

```bash
git add echo/console.py echo/__main__.py tests/test_console.py
git commit -m "feat(echo): 控制台与主程序，可用假脑子冒烟

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 12: 把设计文档更新成"实际运行方式"

**Files:**
- Modify: `docs/superpowers/specs/2026-09-03-conversation-engine-design.md`

- [ ] **Step 1: 核对 spec 与代码的差异**

逐节对照，已知会有差异的地方：
- §3.1 事件表 → 与 `echo/events.py` 一致（`VisitorLeft` 带 `session_id`）
- §4.2 格式 → `DECISION_SCHEMA`
- §5.1 JSON 示例 → `PuppetMemory` 实际字段（`impressions` 里没有 `weight`；`unspoken` 结构）
- §5.2 → 反刍的 material 是"最近窗口 + 未说出口 + 问句"，不是"自上次反刍以来"
- §7.2 → 控制台的 `.` 语义
- §10 → `config.toml` 实际字段名

- [ ] **Step 2: 在文档顶部加"实际运行方式"一节**

在 `## 0. 一句话` 之后插入：

```markdown
## 0.5 跑起来（阶段 1 已实现）

    cd echo-chamber-realms
    .venv/bin/pytest -q                  # 不花钱的全部测试
    .venv/bin/python -m echo --fake      # 假脑子，看机制
    ANTHROPIC_API_KEY=… .venv/bin/python -m echo   # 真脑子

终端里：打一行回车 = 说一句；单独一个 `.` = 先开口（打断正在说的）；Ctrl-C = 关机（暂停）。
状态在 `state/`：`transcript.jsonl` 原话、`charlie.json`/`lucy.json`/`kaka.json` 记忆、
`changes.jsonl` 每次反刍的差异、`sessions.jsonl` 每场到访的印象（墙三的星）、`days.json` 天数。
旋钮在 `config.toml`，改了下一轮生效。

代码地图：`echo/room.py`（总线、锁、计时）→ `echo/puppet.py`（循环）→ `echo/brain.py`（模型）；
`echo/transcript.py` 是木偶看到的世界；`echo/memory.py` 是它们记住的东西。
```

并把状态行改为 `状态：阶段 1 已实现，2026-09-0X`。

- [ ] **Step 3: 修正 Step 1 列出的差异，使文档与代码一致**

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-09-03-conversation-engine-design.md
git commit -m "docs: 设计文档更新为阶段 1 实际运行方式

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

## 自查记录

**Spec 覆盖：** §1 原则 → Global Constraints；§3 房间 → Task 3、9；§4 木偶 → Task 10；§4.2 格式 → Task 6；§4.4 模型参数 → Task 6 `ClaudeBrain._json`；§5 记忆 → Task 5、10；§6 到访 → Task 8、9；§7.2 控制台 → Task 11；§8 关闭模式 → Task 7；§9 主循环 → Task 11；§10 旋钮 → Task 8；§11 错误处理 → Task 6（模型失败 = 不开口）、Task 5（写盘失败会抛异常直接退出，符合"唯一致命"）；§12 测试 → 每个 Task；§13 阶段 1 验收 → Task 11 Step 6/7。
未在阶段 1 的：§7.1 耳朵、§8.1 真 TTS、§8.2 串口、§6 声纹 —— 按 spec §13 属后续阶段。

**类型一致性：** `Floor.try_acquire(name, stop)` 在 Task 3 定义、Task 9/10 使用同签名；`Mouth.say -> (str, bool)`、`stop -> str` 在 Task 7 定义、Task 10 使用；`Brain.ruminate -> Rumination | None` 在 Task 6 定义、Task 10 处理 None；`Config` 字段名在 Task 8 定义、Task 9/10/11 使用 `window / quiet_interval_* / visitor_timeout / ruminate_every / belief_capacity / unspoken_keep / model / puppet_effort / ruminate_model / state_dir`；`VisitorLeft.session_id` 在 Task 3 定义、Task 9/10 使用。
