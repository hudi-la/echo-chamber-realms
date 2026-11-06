import json

from echo.brain import Change, Decision, Rumination, Seed, parse_decision, parse_rumination, parse_seed
from tests.fakes import FakeBrain


def test_parse_decision():
    assert parse_decision('{"speak": true, "text": "  还用问吗 "}') == Decision(True, "还用问吗")
    assert parse_decision('{"speak": false, "text": ""}') == Decision(False, "")


def test_parse_rumination_changes_and_seed():
    text = json.dumps({"changes": [
        {"kind": "belief", "who": "", "old": "安静最重要", "new": "该说的时候要说", "because": "Lucy被逼问时我没出声，她更小了"},
        {"kind": "relation", "who": "Kaka", "old": "", "new": "他被骂装的时候没退，还护了Lucy", "because": "新朋友说他装，他没躲"},
    ], "impression": " 说话很短，爱逼问 "})
    r = parse_rumination(text)
    assert r == Rumination([
        Change("belief", "", "安静最重要", "该说的时候要说", "Lucy被逼问时我没出声，她更小了"),
        Change("relation", "Kaka", "", "他被骂装的时候没退，还护了Lucy", "新朋友说他装，他没躲"),
    ], "说话很短，爱逼问")
    assert parse_rumination('{"changes": [], "impression": ""}') == Rumination([], "")
    seed = parse_seed(json.dumps({"beliefs": [" 只有聪明才会被喜欢 ", ""]}))
    assert seed == Seed(["只有聪明才会被喜欢"])


async def test_fake_brain_pops_then_silent():
    b = FakeBrain([Decision(True, "哼")])
    assert await b.decide("s", "x") == Decision(True, "哼")
    assert await b.decide("s", "y") == Decision(False, "")
    assert b.calls == [("s", "x"), ("s", "y")]


class _StubResponses:
    def __init__(self, output_text: str, status: str = "completed"):
        self.output_text, self.status, self.calls = output_text, status, []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self


class _StubOpenAI:
    def __init__(self, output_text: str, status: str = "completed"):
        self.responses = _StubResponses(output_text, status)


async def test_openai_brain_request_shape_and_parse():
    from echo.brain import OpenAIBrain
    stub = _StubOpenAI('{"speak": true, "text": "哼"}')
    b = OpenAIBrain("gpt-5.5", effort="low", client=stub)
    assert await b.decide("你是Kaka。", "(现在) 没人在说。") == Decision(True, "哼")
    call = stub.responses.calls[0]
    assert call["model"] == "gpt-5.5"
    assert call["instructions"] == "你是Kaka。"
    assert call["input"].startswith("(现在) 没人在说。")
    assert call["text"]["format"]["schema"]["required"] == ["speak"]
    assert call["reasoning"] == {"effort": "low"}
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert call["text"]["format"]["schema"]["required"] == ["speak"]
    assert call["store"] is False


async def test_openai_brain_incomplete_is_silent():
    from echo.brain import OpenAIBrain, SILENT
    b = OpenAIBrain("gpt-5.5", client=_StubOpenAI("", status="incomplete"))
    assert await b.decide("s", "x") == SILENT
    assert await b.ruminate("s", "x", 6) is None


def test_parse_decision_feeling_and_intent():
    d = parse_decision('{"feeling": " 有点慌 ", "intent": "让他们别看我", "speak": false}')
    assert d.feeling == "有点慌" and d.intent == "让他们别看我" and not d.speak
    assert parse_decision('{"speak": true, "text": "x"}').feeling == ""


async def test_openai_brain_compose_uses_line_schema_and_decision():
    from echo.brain import COMPOSE_ASK, Decision, OpenAIBrain, parse_line
    stub = _StubOpenAI('{"text": "当然是我。"}')
    b = OpenAIBrain("gpt-5.5", client=stub)
    line = await b.compose("你是Kaka。", "(现在) 没人在说。", Decision(True, feeling="兴奋", intent="让他们看我"))
    assert line == "当然是我。"
    call = stub.responses.calls[0]
    assert call["text"]["format"]["schema"]["required"] == ["text", "performance"]
    assert call["input"].startswith("(现在) 没人在说。")
    assert call["input"] == "(现在) 没人在说。"
    assert "兴奋" not in call["input"] and "让他们看我" not in call["input"]
    assert parse_line('{"text": " 哼 "}') == "哼"


def test_disabled_social_memories_are_excluded_from_generation_schema():
    from echo.brain import rumination_schema, parse_rumination
    schema = rumination_schema()
    assert schema['properties']['changes']['items']['properties']['kind']['enum'] == ['belief']
    assert 'impression' not in schema['properties']
    assert schema['required'] == ['changes']
    assert parse_rumination('{"changes": []}').impression == ''
