import json

import pytest

from echo import settings
from echo.brain import Decision, OpenAIBrain, PerformedLine
from echo.config import parse_config
from echo.floor import Floor
from echo.performance import Performance
from tests.test_brain import _StubOpenAI
from tests.test_performance import Stage


def use_tables(monkeypatch, tmp_path, parameter_edit=None, rule_edit=None):
    parameters = settings.PARAMETERS_FILE.read_text()
    rules = settings.RULES_FILE.read_text()
    if parameter_edit:
        parameters = parameter_edit(parameters)
    if rule_edit:
        rules = rule_edit(rules)
    p, r = tmp_path / 'parameters.toml', tmp_path / 'rules.toml'
    p.write_text(parameters)
    r.write_text(rules)
    monkeypatch.setattr(settings, 'PARAMETERS_FILE', p)
    monkeypatch.setattr(settings, 'RULES_FILE', r)
    return p, r


def test_profiles_and_legacy_override_use_one_parameter_table(tmp_path):
    zh = parse_config('profile="zh"', tmp_path)
    en = parse_config('profile="en"', tmp_path)
    assert zh.prompt_language == 'zh' and en.prompt_language == 'en'
    assert en.state_dir == tmp_path / settings.parameters()['profiles']['en']['state_dir']
    master = settings.parameters()['profiles']['zh']
    assert zh.mouth_speed == master['mouth']['playback_speed']
    override = parse_config('profile="zh"\n[room]\nwindow=7', tmp_path)
    assert override.window == 7
    assert override.mouth_speed == zh.mouth_speed
    with pytest.raises(ValueError, match='profile'):
        parse_config('profile="missing"', tmp_path)


async def test_model_token_parameter_reaches_request(monkeypatch, tmp_path):
    use_tables(monkeypatch, tmp_path, lambda s: s.replace('openai_compose_tokens = 1500', 'openai_compose_tokens = 777'))
    stub = _StubOpenAI('{"text":"hello"}')
    brain = OpenAIBrain('test', client=stub)
    await brain.compose('SYSTEM', 'SCENE', Decision(True))
    assert stub.responses.calls[-1]['max_output_tokens'] == 777


def test_body_parameter_and_rule_reach_actions(monkeypatch, tmp_path):
    p, r = use_tables(monkeypatch, tmp_path, lambda s: s.replace('lease_ms = 1200', 'lease_ms = 900'))
    stage = Stage()
    action = Performance(stage)
    action.start('Lucy', PerformedLine('hello'), 0, 3)
    assert ('body', 'Lucy', 900) in stage.commands
    r.write_text(r.read_text().replace('body_during_speech = true', 'body_during_speech = false'))
    stage = Stage()
    action = Performance(stage)
    action.start('Lucy', PerformedLine('hello'), 0, 3)
    assert not any(isinstance(command, tuple) and command[0] == 'body' for command in stage.commands)


async def test_speaker_selection_switches_are_executed(monkeypatch, tmp_path):
    use_tables(monkeypatch, tmp_path, rule_edit=lambda s: s.replace('selection = "random"', 'selection = "first"').replace('prefer_named_character = true', 'prefer_named_character = false'))
    import asyncio
    floor = Floor()
    async def stop(): return ''
    winners = await asyncio.gather(floor.request('Charlie', stop), floor.request('Lucy', stop, preferred=True))
    assert winners == [True, False]


def test_runtime_record_never_writes_source_tables(monkeypatch, tmp_path):
    p, r = use_tables(monkeypatch, tmp_path)
    prompt = tmp_path / 'prompts.txt'
    prompt.write_text('PROMPT_SOURCE')
    sources = {file: file.read_bytes() for file in (p, r, prompt)}
    # Returned mappings cannot mutate the read-only source or shared parsed cache.
    modified = settings.parameters()
    modified['profiles']['zh']['room']['window'] = 999
    assert settings.parameters()['profiles']['zh']['room']['window'] != 999
    config = parse_config('profile="zh"', tmp_path)
    run = settings.capture_run_configuration(tmp_path / 'state', config, prompt)
    record = json.loads((run / 'configuration.json').read_text())
    assert record['effective_config']['window'] == config.window
    assert record['sources']['prompts.txt']['content'] == 'PROMPT_SOURCE'
    assert all(file.read_bytes() == before for file, before in sources.items())


@pytest.mark.parametrize('edit, message', [
    (lambda s: s.replace('lease_ms = 1200', 'lease_ms = 1300'), 'body lease'),
    (lambda s: s.replace('renew_seconds = 0.4', 'renew_seconds = 1.3'), 'body lease'),
    (lambda s: s.replace('blink_probability = 0.35', 'blink_probability = 1.5'), 'blink_probability'),
])
def test_invalid_timing_is_rejected_before_startup(monkeypatch, tmp_path, edit, message):
    use_tables(monkeypatch, tmp_path, parameter_edit=edit)
    with pytest.raises(ValueError, match=message):
        settings.validate_controls()


def test_english_inherits_an_edited_chinese_speed(monkeypatch, tmp_path):
    use_tables(monkeypatch, tmp_path, lambda s: s.replace('playback_speed = 1.15', 'playback_speed = 1.25'))
    assert parse_config('profile="zh"', tmp_path).mouth_speed == 1.25
    assert parse_config('profile="en"', tmp_path).mouth_speed == 1.25


def test_profile_inheritance_cycle_is_rejected(monkeypatch, tmp_path):
    use_tables(monkeypatch, tmp_path, lambda s: s.replace('[profiles.zh]\n', '[profiles.zh]\nextends = "en"\n'))
    with pytest.raises(ValueError, match='circular'):
        parse_config('profile="en"', tmp_path)
