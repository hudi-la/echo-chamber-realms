import asyncio
from dataclasses import replace
from pathlib import Path
import pytest
from echo.brain import Change, Rumination, OpenAIBrain
from echo.config import parse_config
from echo.memory import PuppetMemory
from echo.prompt_docs import render
from echo.prompts import ROOT, catalog, persona
from tests.test_puppet import build
from tests.fakes import FakeBrain
from tests.test_brain import _StubOpenAI
from echo.clock import FakeClock


def test_reviewed_docs_match_both_runtime_catalogs():
    for language in ('zh', 'en'):
        assert (ROOT / 'docs' / f'prompts-and-flow.{language}.md').read_text() == render(language)
        for name, p in catalog(language)['personas'].items():
            assert p['history'] == ''
            assert len(p['initial_beliefs']) <= 6
            assert '不要求你每次' not in p['strategy']
            assert '初始信念' not in persona(name, language)


def test_english_config_isolated_and_fully_adapted():
    c = parse_config((ROOT / 'config.en.toml').read_text(), ROOT)
    assert c.prompt_language == 'en' and c.ears_language == 'en'
    assert c.state_dir == ROOT / 'state-en'
    for voice in c.instructions.values():
        assert 'English' in voice and 'Mandarin' not in voice and '普通话' not in voice
    with pytest.raises(ValueError):
        parse_config('[prompts]\nlanguage="xx"', Path('/tmp'))


async def test_observations_are_saved_but_never_fed_back(tmp_path):
    brain = FakeBrain(rumination=Rumination([
        Change('relation', 'Kaka', '', 'COMPANION_PRIVATE', 'Evidence')], 'VISITOR_PRIVATE'))
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    p.memory.beliefs = ['CURRENT_BELIEF']
    p.memory.add_thought('LEGACY_FEELING', 'LEGACY_INTENT', None, 'old', 8)
    p.memory.note_heard('now', {'at': 'now', 'who': '新朋友', 'text': 'ACTUAL_LINE', 'cut': False})
    await p.ruminate('visit')
    saved = PuppetMemory.load('Lucy', tmp_path)
    assert saved.companion_observations[-1]['view'] == 'COMPANION_PRIVATE'
    assert saved.impressions[-1]['text'] == 'VISITOR_PRIVATE'
    assert saved.pending_experiences == []
    await p.ruminate(None)
    for value in (p.system_prompt(), *brain.ruminations):
        assert 'COMPANION_PRIVATE' not in value and 'VISITOR_PRIVATE' not in value
        assert 'LEGACY_FEELING' not in value and 'LEGACY_INTENT' not in value
    assert 'CURRENT_BELIEF' in p.system_prompt()
    assert 'ACTUAL_LINE' in brain.ruminations[0]


async def test_pending_experiences_survive_restart_failure_and_concurrent_arrival(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()
    class Slow(FakeBrain):
        async def ruminate(self, *args):
            self.ruminations.append(args[1])
            entered.set()
            await release.wait()
            return self.rumination
    brain = Slow(rumination=None)
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    for i in range(31):
        p.memory.note_heard('w', {'at':'w','who':'Visitor','text':f'LINE_{i}','cut':False})
    p.memory = PuppetMemory.load('Lucy', tmp_path)
    task = asyncio.create_task(p.ruminate(None))
    await entered.wait()
    p.memory.note_heard('w', {'at':'w','who':'Visitor','text':'NEW','cut':False})
    release.set()
    await task
    assert len(p.memory.pending_experiences) == 32 and p.memory.heard == 32
    assert "LINE_0" in brain.ruminations[0] and "LINE_30" in brain.ruminations[0]
    brain.rumination = Rumination([])
    entered.clear(); release.clear()
    task = asyncio.create_task(p.ruminate(None))
    await entered.wait()
    p.memory.note_heard('w', {'at':'w','who':'Visitor','text':'LATER','cut':False})
    release.set()
    await task
    saved = PuppetMemory.load('Lucy', tmp_path)
    assert [e['text'] for e in saved.pending_experiences] == ['LATER']
    assert saved.heard == 1


async def test_english_requests_do_not_reintroduce_private_feelings():
    stub = _StubOpenAI('{"text":"Hello."}')
    brain = OpenAIBrain('test', client=stub)
    brain.language = 'en'
    from echo.brain import Decision
    await brain.compose(persona('Charlie','en'), 'Visitor: Hello.', Decision(True, feeling='SECRET', intent='PURPOSE'))
    call = stub.responses.calls[-1]
    assert catalog('en')['compose'] in call['input']
    assert 'SECRET' not in call['input'] and 'PURPOSE' not in call['input']


async def test_shutdown_dispatches_reflection_from_actual_dialogue(tmp_path):
    from echo.__main__ import bedtime
    clock = FakeClock()
    brain = FakeBrain(rumination=Rumination([]))
    _, puppets, *_ = build(clock, tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    p.memory.note_heard('w', {'at':'w','who':'Visitor','text':'A real experience','cut':False})
    assert not p.memory.thoughts and not p.memory.unspoken
    await bedtime([p])
    assert len(brain.ruminations) == 1
    assert '关机前整理' in brain.ruminations[0]
    assert p.memory.pending_experiences == []


@pytest.mark.parametrize('language', ['zh', 'en'])
async def test_main_initializes_reviewed_beliefs_without_api(tmp_path, monkeypatch, language):
    from echo.__main__ import main_async, Console
    async def end_console(self):
        return
    monkeypatch.setattr(Console, 'run', end_console)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    config = tmp_path / 'config.toml'
    config.write_text(f'[prompts]\nlanguage="{language}"\n[monitor]\nport=0\n')
    await main_async(config, fake=True)
    for name in ('Charlie','Lucy','Kaka'):
        m = PuppetMemory.load(name, tmp_path / 'state')
        assert m.beliefs == catalog(language)['personas'][name]['initial_beliefs']
