"""A run keeps one validated immutable version, including after files disappear."""
import asyncio
from dataclasses import FrozenInstanceError
import json

import pytest

from echo import prompts, settings
from echo.brain import Decision, OpenAIBrain, line_schema
from echo.clock import FakeClock
from echo.config import LiveConfig, parse_config
from echo.floor import addressed_character
from echo.memory import ChangeLog, PuppetMemory
from echo.mouth import PrintMouth
from echo.performance import gaze
from tests.test_brain import _StubOpenAI
from tests.test_control_tables import use_tables


def setup_run(monkeypatch, tmp_path):
    p, r = use_tables(monkeypatch, tmp_path)
    prompt = tmp_path / 'prompts.txt'
    prompt.write_text(prompts.PROMPT_FILE.read_text())
    monkeypatch.setattr(prompts, 'PROMPT_FILE', prompt)
    config = tmp_path / 'launch.toml'
    config.write_text('profile="zh"')
    return p, r, prompt, config


async def test_one_snapshot_survives_edits_and_is_inherited_by_tasks(monkeypatch, tmp_path):
    p, r, prompt, config = setup_run(monkeypatch, tmp_path)
    with settings.runtime_configuration(config) as run:
        old_compose = prompts.catalog()['compose_system']
        old_lease = settings.parameter('body.lease_ms')
        p.write_text(p.read_text().replace('lease_ms = 1200', 'lease_ms = 900'))
        r.write_text(r.read_text().replace('selection = "random"', 'selection = "first"'))
        prompt.write_text(prompt.read_text().replace(old_compose, 'NEW_COMPOSE', 1))
        config.write_text('profile="en"')
        monkeypatch.setenv('ECR_SERIAL_PORT', 'changed-after-start')
        async def child():
            assert settings.active_configuration() is run
            assert settings.parameter('body.lease_ms') == old_lease
            assert settings.rule('conversation.selection') == 'random'
            assert prompts.catalog()['compose_system'] == old_compose
            assert run.config.prompt_language == 'zh'
        await asyncio.create_task(child())
        saved = settings.capture_run_configuration(tmp_path / 'state', run.config)
        record = json.loads((saved / 'configuration.json').read_text())
        assert record['sources']['prompts.txt']['content'] == run.sources['prompts.txt']['content']
        assert record['startup_overrides'] == settings.plain(run.overrides)
    with settings.runtime_configuration(config) as restarted:
        assert settings.parameter('body.lease_ms') == 900
        assert settings.rule('conversation.selection') == 'first'
        assert restarted.catalogs['zh']['compose_system'] == 'NEW_COMPOSE'
        assert restarted.config.prompt_language == 'en'


def test_deep_immutability_and_memory_remains_mutable(monkeypatch, tmp_path):
    *_, config = setup_run(monkeypatch, tmp_path)
    with settings.runtime_configuration(config) as run:
        with pytest.raises(FrozenInstanceError):
            run.config.window = 99
        with pytest.raises(TypeError):
            run.config.voices['Lucy'] = 'other'
        with pytest.raises(TypeError):
            run.rules['aliases']['Lucy'][0] = 'other'
        with pytest.raises(TypeError):
            run.catalogs['zh']['personas']['Lucy']['initial_beliefs'][0] = 'other'
        memory = PuppetMemory('Lucy', tmp_path / 'lucy.json')
        memory.apply_seed(run.catalogs['zh']['personas']['Lucy']['initial_beliefs'],
                          'now', run.config.belief_capacity, ChangeLog(tmp_path / 'changes.jsonl'))
        memory.beliefs.append('A new experience')
        assert 'A new experience' not in run.catalogs['zh']['personas']['Lucy']['initial_beliefs']


async def test_runtime_consumers_and_record_do_not_read_source_files(monkeypatch, tmp_path):
    p, r, prompt, config = setup_run(monkeypatch, tmp_path)
    # Import modules first, then edit: startup values must beat import-time defaults.
    p.write_text(p.read_text().replace('print_chars_per_second = 6.0', 'print_chars_per_second = 9.0'))
    r.write_text(r.read_text().replace('["Kaka", "Lucy", "Charlie"]', '["Charlie", "Lucy", "Kaka"]')
                 .replace('"小狗"', '"新称呼"').replace('"excited"]', '"joyful"]'))
    with settings.runtime_configuration(config) as run:
        for source in (p, r, prompt, config):
            source.unlink()
        assert LiveConfig(config).current is run.config
        assert PrintMouth(FakeClock()).cps == 9
        assert gaze('Lucy', 'Charlie') == 2
        assert addressed_character('新称呼，你好') == 'Charlie'
        assert 'joyful' in line_schema()['properties']['performance']['properties']['tone']['enum']
        stub = _StubOpenAI('{"text":"hello"}')
        brain = OpenAIBrain('test', client=stub)
        await brain.compose(prompts.persona('Lucy'), 'SCENE', Decision(True))
        assert run.catalogs['zh']['compose_system'] in stub.responses.calls[-1]['instructions']
        assert parse_config('profile="zh"', tmp_path).window == run.config.window
        assert settings.capture_run_configuration(tmp_path / 'state', run.config).exists()


@pytest.mark.parametrize('target, before, after, error', [
    ('parameters', 'renew_seconds = 0.4', 'renew_seconds = 1.3', 'body lease'),
    ('parameters', 'window = 24', 'window = -1', 'window'),
    ('rules', 'selection = "random"', 'selection = "unknown"', 'selection'),
    ('prompts', '{identity}', '{unknown}', 'placeholder'),
])
def test_invalid_configuration_rejected_and_context_restored(monkeypatch, tmp_path, target, before, after, error):
    p, r, prompt, config = setup_run(monkeypatch, tmp_path)
    path = {'parameters': p, 'rules': r, 'prompts': prompt}[target]
    path.write_text(path.read_text().replace(before, after))
    with pytest.raises(ValueError, match=error):
        with settings.runtime_configuration(config):
            pytest.fail('Invalid settings reached runtime')
    assert settings.active_configuration() is None
    assert not (tmp_path / 'state').exists()


def test_inputs_are_read_once_at_startup(monkeypatch, tmp_path):
    sources = setup_run(monkeypatch, tmp_path)
    from pathlib import Path
    read_text = Path.read_text
    reads = {source: 0 for source in sources}
    def counted(path, *args, **kwargs):
        if path in reads:
            reads[path] += 1
        return read_text(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', counted)
    with settings.runtime_configuration(sources[-1]) as run:
        settings.parameter('body.lease_ms')
        settings.rule('aliases')
        prompts.catalog('en')
        settings.capture_run_configuration(tmp_path / 'state', run.config)
    assert list(reads.values()) == [1, 1, 1, 1]


async def test_fake_application_uses_snapshot_and_saves_normal_memory(monkeypatch, tmp_path):
    from echo import __main__ as application
    *_, config = setup_run(monkeypatch, tmp_path)
    config.write_text('''profile="zh"
[ears]
mode="console"
[mouth]
mode="off"
[monitor]
port=0
[memory]
reset_on_start=false
''')
    monkeypatch.setenv('ECR_SERIAL_PORT', '')
    monkeypatch.setenv('ECR_RELAY_ACTIVE', '')
    class Console:
        def __init__(self, room):
            self.room = room
        async def run(self):
            assert self.room.cfg() is settings.active_configuration().config
    monkeypatch.setattr(application, 'Console', Console)
    await application.main_async(config, fake=True)
    assert settings.active_configuration() is None
    state = tmp_path / 'state'
    assert len(list((state / 'runs').glob('*/configuration.json'))) == 1
    for name in ('charlie', 'lucy', 'kaka'):
        assert json.loads((state / f'{name}.json').read_text())['beliefs']
