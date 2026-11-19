"""Independent private-state requests: isolation, persistence, backpressure, cancellation."""
import asyncio
import json
import pytest

from echo.brain import OpenAIBrain, ClaudeBrain, SubscriptionBrain, PrivateThought, parse_thought
from echo.clock import FakeClock
from echo.events import PuppetStarted, HumanSaid
from echo.memory import PuppetMemory
from echo.settings import parameter, validate_controls
from tests.fakes import FakeBrain
from tests.test_puppet import build


class ThinkingBrain(FakeBrain):
    def __init__(self):
        super().__init__()
        self.entered = asyncio.Event()
        self.release = asyncio.Event()
        self.inputs = []
        self.cancelled = False

    async def think(self, system, situation):
        self.inputs.append((system, situation))
        self.entered.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled = True
            raise
        return PrivateThought('I feel uncertain.', 'I want to listen.')


async def cleanup(p):
    if p._thought_task:
        p._thought_task.cancel()
        await asyncio.gather(p._thought_task, return_exceptions=True)


def test_private_history_is_bounded_persisted_and_isolated(tmp_path):
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', FakeBrain()), ('Kaka', FakeBrain())])
    lucy, kaka = puppets['Lucy'], puppets['Kaka']
    kaka.memory.add_private_thought('KAKA_SECRET', 'KAKA_INTENT', 'w', 'c')
    for i in range(12):
        lucy.memory.add_private_thought(f'LUCY_{i}', 'x'*500, str(i), 'c')
    saved = PuppetMemory.load('Lucy', tmp_path)
    assert len(saved.private_thoughts) == parameter('thoughts.history_keep')
    assert len(saved.private_thoughts[-1]['intent']) == parameter('thoughts.max_chars')
    situation = lucy.situation()
    assert 'LUCY_11' in situation and 'LUCY_8' not in situation
    assert 'KAKA_SECRET' not in situation and 'KAKA_INTENT' not in situation
    assert 'LUCY_11' not in kaka.situation()
    assert not lucy.room.transcript.entries
    assert not saved.thoughts  # Legacy decision memory stays separate.


async def test_blocked_thought_does_not_block_composition(tmp_path):
    brain = ThinkingBrain()
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    brain.compose = _compose_capture(brain)
    p.request_thought()
    try:
        await asyncio.wait_for(brain.entered.wait(), 1)
        await asyncio.wait_for(p.consider(), .2)
        await asyncio.wait_for(p._speech_task, .2)  # Empty test line completes immediately.
        assert brain.calls and not p.memory.private_thoughts
        brain.release.set()
        await asyncio.wait_for(p._thought_task, 1)
        assert p.memory.private_thoughts[-1]['feeling'] == 'I feel uncertain.'
        assert 'I feel uncertain.' in p.situation()
        assert 'I feel uncertain.' not in brain.calls[0][1]  # No retroactive mutation.
    finally:
        await cleanup(p)


def _compose_capture(brain):
    async def compose(system, situation, decision):
        brain.calls.append((system, situation))
        return ''
    return compose


async def test_new_events_coalesce_without_concurrent_or_lost_updates(tmp_path):
    brain = ThinkingBrain()
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    p.request_thought()
    try:
        await asyncio.wait_for(brain.entered.wait(), 1)
        for i in range(20):
            p.room.transcript.add(i, str(i), 'said', 'Kaka', f'NEW_{i}')
            p.request_thought()
        assert len(brain.inputs) == 1
        brain.release.set()
        await asyncio.wait_for(p._thought_task, 2)
        assert len(brain.inputs) == 2
        assert 'NEW_19' in brain.inputs[-1][1]
        assert len(p.memory.private_thoughts) == 2
    finally:
        await cleanup(p)


async def test_listeners_and_speaker_think_without_receiving_unheard_full_line(tmp_path):
    brain = ThinkingBrain()
    room, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    run = asyncio.create_task(p.run())
    try:
        await room.publish(PuppetStarted(0, 'Kaka', 'UNHEARD_FULL_TEXT'))
        await asyncio.wait_for(brain.entered.wait(), 1)
        assert 'UNHEARD_FULL_TEXT' not in brain.inputs[0][1]
        p.speaking = True  # Private updates continue even while this character speaks.
        await room.publish(HumanSaid(1, 'COMPLETED_PUBLIC_LINE'))
        for _ in range(10): await asyncio.sleep(0)
        assert p._thought_pending
        brain.release.set()
        await asyncio.wait_for(p._thought_task, 2)
        assert 'COMPLETED_PUBLIC_LINE' in brain.inputs[-1][1]
    finally:
        run.cancel()
        await asyncio.gather(run, return_exceptions=True)
    assert p._thought_task.done()


async def test_shutdown_cancels_inflight_thought(tmp_path):
    brain = ThinkingBrain()
    room, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']; run = asyncio.create_task(p.run())
    await room.publish(PuppetStarted(0, 'Lucy', 'hello'))
    await asyncio.wait_for(brain.entered.wait(), 1)
    run.cancel(); await asyncio.wait_for(asyncio.gather(run, return_exceptions=True), .2)
    assert brain.cancelled and not p.memory.private_thoughts


async def test_failed_thought_does_not_retry_or_replace_memory(tmp_path):
    class Broken(FakeBrain):
        async def think(self, *args): raise RuntimeError('offline')
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', Broken())])
    p = puppets['Lucy']; p.memory.add_private_thought('previous', 'listen', 'w', 'c')
    p.request_thought(); await asyncio.wait_for(p._thought_task, 1)
    assert len(p.memory.private_thoughts) == 1
    assert p.memory.private_thoughts[0]['feeling'] == 'previous'
    assert not p._thought_pending


async def test_timeout_is_bounded(monkeypatch, tmp_path):
    import echo.puppet as module
    original = module.parameter
    monkeypatch.setattr(module, 'parameter', lambda key: .01 if key == 'model.thought_timeout' else original(key))
    brain = ThinkingBrain()
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']; p.request_thought()
    await asyncio.wait_for(p._thought_task, 1)
    assert brain.cancelled and not p.memory.private_thoughts


@pytest.mark.parametrize('provider', [OpenAIBrain, ClaudeBrain, SubscriptionBrain])
async def test_think_uses_separate_schema_and_transport(provider):
    brain = object.__new__(provider); brain.model = 'test'; brain.language = 'en'
    calls = []
    async def transport(*args):
        calls.append(args)
        return json.dumps({'feeling':'a little wary', 'intent':'listen'})
    brain._json = transport
    thought = await brain.think('CHARACTER_ONLY', 'PUBLIC_AND_OWN')
    assert thought == PrivateThought('a little wary', 'listen')
    assert calls[0][0] == 'test' and calls[0][2] == 'PUBLIC_AND_OWN'
    assert 'CHARACTER_ONLY' in calls[0][1]
    assert set(calls[0][3]['properties']) == {'feeling', 'intent'}


def test_thought_parser_and_controls():
    validate_controls()
    assert parse_thought('{"feeling":"", "intent":""}') is None
    with pytest.raises(ValueError): parse_thought('{"feeling":false,"intent":"x"}')


async def test_monitor_serves_live_text_and_renderer_without_public_transcript_leak(tmp_path):
    from aiohttp import web
    from aiohttp.test_utils import TestClient, TestServer
    from echo.monitor import Monitor, PAGE
    room, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', FakeBrain())])
    p = puppets['Lucy']
    p.memory.add_private_thought('PRIVATE_FOR_VISUALS', 'listen', 'w', 'c')
    monitor = Monitor(room, [p])
    app = web.Application()
    app.router.add_get('/', monitor._index)
    app.router.add_get('/ws', monitor._ws)
    app.router.add_static('/static/', PAGE.parent / 'static')
    async with TestClient(TestServer(app)) as client:
        response = await client.get('/')
        assert response.status == 200 and '/static/thought-field.js' in await response.text()
        response = await client.get('/static/thought-field.js')
        assert response.status == 200 and 'TextFlock3D' in await response.text()
        async with client.ws_connect('/ws') as ws:
            snapshot = await ws.receive_json(timeout=1)
            assert snapshot['puppets']['Lucy']['private_thoughts'][0]['feeling'] == 'PRIVATE_FOR_VISUALS'
            assert 'inner_state' not in snapshot['puppets']['Lucy']
    assert not room.transcript.entries


async def test_speech_publishes_delivery_metadata_without_private_states(tmp_path):
    from types import SimpleNamespace
    from echo.brain import PerformedLine
    room, puppets, *_ = build(FakeClock(), tmp_path, [('Charlie', FakeBrain())])
    p = puppets['Charlie']
    p.memory.add_private_thought('NOT_PUBLIC', 'PRIVATE_INTENT', 'w', 'c')
    async def say(name, text): return str(text), True
    p.mouth = SimpleNamespace(say=say)
    inbox = room.subscribe()
    await p.speak(PerformedLine('Lucy?', {'target':'Lucy','tone':'curious'}))
    ev = inbox.get_nowait()
    assert isinstance(ev, PuppetStarted)
    assert ev.performance == {'target':'Lucy','tone':'curious'}
    assert 'NOT_PUBLIC' not in str(ev) and 'PRIVATE_INTENT' not in str(ev)
