"""木偶的脑子。四个动作：decide（要不要开口）、compose（说什么）、ruminate（有没有分量够的事让我改信念）、
seed（出厂信念）。两家实现（Claude / OpenAI），同一个接口。调用失败 = 这一轮不开口 / 这一次不反刍，绝不把房间卡住。
提示词的文字在 prompts.py，这里只有 JSON 格式（schema）和调用。"""
import json
import logging
from .usage import record_usage
from dataclasses import dataclass
from typing import Protocol

import anthropic

from .prompts import catalog, COMPOSE_ASK  # noqa: F401 —— 提示词集中在 prompts.py

log = logging.getLogger("echo.brain")


@dataclass
class Decision:
    """Live decision uses speak only; other fields remain for old test doubles."""
    speak: bool
    text: str = ""      # 只有测试用的假脑子会预先带台词；真脑子留空，由 compose 填
    feeling: str = ""   # 它此刻的感受（私下的，别人听不到）
    intent: str = ""    # 它这次想达到什么（私下的）


SILENT = Decision(False)


@dataclass
class Change:
    """反刍提出的一处改动。必须带理由（because）：哪件事、为什么够分量。没理由的代码不收。"""
    kind: str          # "belief" | "relation"
    who: str = ""      # relation 时是对谁的看法
    old: str = ""      # 改哪条（原句）；新加的留空
    new: str = ""      # 改成什么
    because: str = ""  # 因为哪件事


@dataclass
class Rumination:
    changes: list[Change]
    impression: str = ""   # 一场到访结束时，这个人留下的印象；平时留空


@dataclass
class Seed:
    """出厂信念：从人设出发、什么都还没发生时相信的东西。只有信念 —— 关系是长出来的，不出厂。"""
    beliefs: list[str]


class Brain(Protocol):
    async def decide(self, system: str, situation: str) -> Decision: ...
    async def compose(self, system: str, situation: str, decision: Decision) -> str: ...
    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None: ...
    async def seed(self, system: str, material: str) -> Seed | None: ...


DECISION_SCHEMA = {
    "type": "object", "properties": {"speak": {"type": "boolean"}},
    "required": ["speak"], "additionalProperties": False,
}

class PerformedLine(str):
    def __new__(cls, text, performance=None):
        obj = super().__new__(cls, text)
        obj.performance = performance or {}
        return obj


# Compatibility export; runtime calls read the selected language from prompts.txt.
PERFORMANCE_ASK = "\n\n" + catalog()["performance"] + "\n"

LINE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "minLength": 1},
        "performance": {
            "type": "object", "properties": {
                "target": {"type": "string", "enum": ["audience", "Charlie", "Lucy", "Kaka"]},
                "tone": {"type": "string", "enum": ["neutral", "curious", "hesitant", "emphatic", "excited"]},
            }, "required": ["target", "tone"], "additionalProperties": False,
        },
    },
    "required": ["text", "performance"], "additionalProperties": False,
}

RUMINATION_SCHEMA = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["belief", "relation"]},
                    "who": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                    "because": {"type": "string"},
                },
                "required": ["kind", "who", "old", "new", "because"],
                "additionalProperties": False,
            },
        },
        "impression": {"type": "string"},
    },
    "required": ["changes", "impression"],
    "additionalProperties": False,
}

SEED_SCHEMA = {
    "type": "object",
    "properties": {"beliefs": {"type": "array", "items": {"type": "string"}}},
    "required": ["beliefs"],
    "additionalProperties": False,
}


def parse_decision(text: str) -> Decision:
    data = json.loads(text)
    return Decision(bool(data.get("speak")), feeling=str(data.get("feeling", "")).strip(),
                    intent=str(data.get("intent", "")).strip(), text=str(data.get("text", "")).strip())


def parse_line(text: str) -> str:
    data = json.loads(text)
    return PerformedLine(str(data.get("text", "")).strip(), data.get("performance"))


def parse_rumination(text: str) -> Rumination:
    data = json.loads(text)
    changes = [Change(kind=str(c.get("kind", "")), who=str(c.get("who", "")).strip(),
                      old=str(c.get("old", "")).strip(), new=str(c.get("new", "")).strip(),
                      because=str(c.get("because", "")).strip())
               for c in data.get("changes", [])]
    return Rumination(changes=changes, impression=str(data.get("impression", "")).strip())


def parse_seed(text: str) -> Seed:
    data = json.loads(text)
    return Seed(beliefs=[str(b).strip() for b in data.get("beliefs", []) if str(b).strip()])


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
        text = await self._json(self.model, system, situation + "\n\n" + catalog(getattr(self, "language", "zh"))["decide"], DECISION_SCHEMA, 400)
        if text is None:
            return SILENT
        try:
            return parse_decision(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 decision 失败: %s / %r", e, text[:200])
            return SILENT

    async def compose(self, system: str, situation: str, decision: Decision) -> str:
        ask = situation + "\n\n" + catalog(getattr(self, "language", "zh"))["compose"] + "\n\n" + catalog(getattr(self, "language", "zh"))["performance"] + "\n"
        text = await self._json(self.model, system, ask, LINE_SCHEMA, 800)
        if text is None:
            return ""
        try:
            return parse_line(text)
        except (json.JSONDecodeError, TypeError) as e:
            log.warning("解析 line 失败: %s / %r", e, text[:200])
            return ""

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        text = await self._json(self.ruminate_model, system, material, RUMINATION_SCHEMA, 2000)
        if text is None:
            return None
        try:
            return parse_rumination(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 rumination 失败: %s / %r", e, text[:200])
            return None

    async def seed(self, system: str, material: str) -> Seed | None:
        text = await self._json(self.ruminate_model, system, material, SEED_SCHEMA, 1500)
        if text is None:
            return None
        try:
            return parse_seed(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 seed 失败: %s / %r", e, text[:200])
            return None


class OpenAIBrain:
    """同一个接口，换成 OpenAI 的 Responses API。人设走 instructions，现场走 input，强制 JSON schema。"""

    def __init__(self, model: str, effort: str = "low",
                 ruminate_model: str | None = None, client=None) -> None:
        import openai  # 只有真用它的时候才 import，测试环境不强求装

        self._openai = openai
        self.client = client or openai.AsyncOpenAI()
        self.model = model
        self.effort = effort
        self.ruminate_model = ruminate_model or model

    async def _json(self, model: str, system: str, user: str, schema: dict,
                    name: str, max_tokens: int) -> str | None:
        try:
            r = await self.client.responses.create(
                model=model,
                instructions=system,
                input=user,
                max_output_tokens=max_tokens,
                reasoning={"effort": self.effort},
                text={"format": {"type": "json_schema", "name": name, "schema": schema, "strict": True}},
                store=False,
            )
        except self._openai.APIConnectionError as e:
            log.warning("网络: %s", e)
            return None
        except self._openai.APIStatusError as e:
            log.warning("API %s: %s", e.status_code, getattr(e, "message", e))
            return None
        record_usage(self, getattr(r, "usage", None), model, name)
        if r.status != "completed":
            log.warning("回复未完成 (%s)", r.status)
            return None
        return r.output_text or None

    async def decide(self, system: str, situation: str) -> Decision:
        text = await self._json(self.model, system, situation + "\n\n" + catalog(getattr(self, "language", "zh"))["decide"], DECISION_SCHEMA, "decision", 800)
        if text is None:
            return SILENT
        try:
            return parse_decision(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 decision 失败: %s / %r", e, text[:200])
            return SILENT

    async def compose(self, system: str, situation: str, decision: Decision) -> str:
        ask = situation + "\n\n" + catalog(getattr(self, "language", "zh"))["compose"] + "\n\n" + catalog(getattr(self, "language", "zh"))["performance"] + "\n"
        text = await self._json(self.model, system, ask, LINE_SCHEMA, "line", 1500)
        if text is None:
            return ""
        try:
            return parse_line(text)
        except (json.JSONDecodeError, TypeError) as e:
            log.warning("解析 line 失败: %s / %r", e, text[:200])
            return ""

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        text = await self._json(self.ruminate_model, system, material, RUMINATION_SCHEMA, "rumination", 3000)
        if text is None:
            return None
        try:
            return parse_rumination(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 rumination 失败: %s / %r", e, text[:200])
            return None

    async def seed(self, system: str, material: str) -> Seed | None:
        text = await self._json(self.ruminate_model, system, material, SEED_SCHEMA, "seed", 2000)
        if text is None:
            return None
        try:
            return parse_seed(text)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            log.warning("解析 seed 失败: %s / %r", e, text[:200])
            return None


def make_brain(provider: str, model: str, effort: str, ruminate_model: str | None = None,
               *, auth: str = "api", subscription_session=None) -> Brain:
    if provider == "openai":
        if auth == "subscription":
            return SubscriptionBrain(model, effort, ruminate_model, session=subscription_session)
        if auth != "api":
            raise ValueError("Unknown brain authentication mode")
        return OpenAIBrain(model, effort, ruminate_model)
    if provider == "anthropic":
        return ClaudeBrain(model, effort, ruminate_model)
    raise ValueError(f"不认识的 provider: {provider!r}（anthropic | openai）")


class SubscriptionBrain(OpenAIBrain):
    """Same role logic, billed to an explicitly authorized ChatGPT plan.

    No API-key fallback. Token rotation is shared by all three puppets.
    """
    def __init__(self, model: str, effort: str = 'none', ruminate_model: str | None = None,
                 session=None, client_factory=None) -> None:
        import openai
        from .subscription import RESOURCE, SubscriptionSession
        self.model, self.effort = model, effort
        self.ruminate_model = ruminate_model or model
        self.session = session or SubscriptionSession()
        self._openai = openai
        self._client_factory = client_factory or (lambda token: openai.AsyncOpenAI(
            api_key=token, base_url=RESOURCE, max_retries=0, timeout=15))

    async def _json(self, model: str, system: str, user: str, schema: dict,
                    name: str, max_tokens: int) -> str | None:
        import asyncio
        from .subscription import SubscriptionError
        try:
            async with asyncio.timeout(15):
                token = await self.session.access_token()
                async with self._client_factory(token) as client:
                    stream = await client.responses.create(
                        model=model, instructions=system,
                        input=[{'role': 'user', 'content': user}],
                        reasoning={'effort': self.effort}, store=False, stream=True,
                        text={'format': {'type': 'json_schema', 'name': name,
                                         'schema': schema, 'strict': True}},
                    )
                    pieces, size, completed = [], 0, False
                    try:
                        async for event in stream:
                            if event.type == 'response.output_text.delta':
                                size += len(event.delta)
                                if size > 100_000:
                                    raise SubscriptionError('订阅模型回复超过本地接收上限。')
                                pieces.append(event.delta)
                            elif event.type == 'response.completed':
                                completed = True
                                response = getattr(event, 'response', None)
                                record_usage(self, getattr(response, 'usage', None), model, name)
                                if not pieces:
                                    return event.response.output_text or None
                                return ''.join(pieces)
                            elif event.type in ('response.failed', 'response.incomplete', 'error'):
                                response = getattr(event, 'response', None)
                                record_usage(self, getattr(response, 'usage', None), model, name)
                                log.warning('订阅脑子回复未完成；本轮不开口，不切换到收费 API。')
                                return None
                        if not completed:
                            log.warning('订阅脑子的流式连接中断；本轮不开口。')
                            return None
                    finally:
                        await stream.close()
        except SubscriptionError as error:
            log.warning('%s', error)
        except (self._openai.OpenAIError, TimeoutError) as error:
            log.warning('订阅脑子调用失败 (%s, HTTP %s)；不会切换收费 API。',
                        type(error).__name__, getattr(error, 'status_code', None))
        return None
