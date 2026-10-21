import asyncio

import numpy as np
import pytest

from echo.audio_io import BrowserMic, BrowserPlayer
from echo.brain import Decision
from echo.ears import Ears
from echo.events import PuppetSaid
from echo.floor import Floor, HUMAN
from tests.fakes import FakeBrain
from tests.test_ears import RoomSpy
from tests.test_puppet import build, settle


class Stream:
    def __init__(self):
        self.q = asyncio.Queue()

    def send(self, *event):
        self.q.put_nowait(event)

    async def events(self):
        while True:
            yield await self.q.get()


async def drain():
    for _ in range(15):
        await asyncio.sleep(0)


async def test_pause_resume_and_out_of_order_transcripts():
    room, t, stream = RoomSpy(), [0.0], Stream()
    ears = Ears(room, lambda: None, now=lambda: t[0], log_line=lambda _: None)
    task = asyncio.create_task(ears.consume(stream.events()))
    try:
        stream.send('started', 'a')
        stream.send('stopped', 'a')
        t[0] = 0.7
        stream.send('started', 'b')
        stream.send('said', '第二段', 'b')
        stream.send('said', '第一段', 'a')
        await drain()
        assert room.floor.holder == HUMAN
        assert room.calls == ['started']
        stream.send('stopped', 'b')
        await drain()
        t[0] = 3
        await ears._check_turn()
        assert room.calls == ['started', ('said', '第一段第二段')]
        assert room.floor.free
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('failure', ['failed', 'missing', 'disconnected'])
async def test_transcription_failure_cannot_hold_floor(failure):
    room, t, stream = RoomSpy(), [0.0], Stream()
    ears = Ears(room, lambda: None, now=lambda: t[0], log_line=lambda _: None)
    task = asyncio.create_task(ears.consume(stream.events()))
    try:
        stream.send('started', 'a')
        stream.send('stopped', 'a')
        if failure == 'failed':
            stream.send('failed', 'a')
        elif failure == 'disconnected':
            stream.send('disconnected')
        await drain()
        t[0] = 9
        await ears._check_turn()
        assert room.floor.free
        assert not any(isinstance(c, tuple) for c in room.calls)
        stream.send('said', '迟到的转写', 'a')
        await drain()
        assert room.floor.free
        assert not ears._segments
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_long_active_speech_has_no_absolute_duration_limit():
    room, t, stream = RoomSpy(), [0.0], Stream()
    ears = Ears(room, lambda: None, now=lambda: t[0], log_line=lambda _: None)
    task = asyncio.create_task(ears.consume(stream.events()))
    try:
        stream.send('started', 'a')
        await drain()
        for seconds in range(5, 301, 5):
            t[0] = seconds
            stream.send('activity')
            await drain()
            await ears._check_turn()
            assert room.floor.holder == HUMAN
        t[0] += 13
        await ears._check_turn()
        assert room.floor.free
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_three_candidates_can_choose_slower_response(monkeypatch):
    # All three choose independently; selecting the last candidate demonstrates
    # that the first completed API request does not automatically win.
    monkeypatch.setattr('echo.floor.random.choice', lambda names: names[-1])
    floor = Floor(window=0.03)
    async def stop(): return ''
    tasks = []
    for name in ('Charlie', 'Lucy', 'Kaka'):
        tasks.append(asyncio.create_task(floor.request(name, stop)))
        await asyncio.sleep(0.005)
    assert await asyncio.gather(*tasks) == [False, False, True]
    assert floor.holder == 'Kaka'
    floor.release('Kaka')
    tasks = [asyncio.create_task(floor.request(n, stop)) for n in ('Lucy', 'Kaka')]
    assert await asyncio.gather(*tasks) == [True, False]


async def test_human_invalidates_pending_candidates():
    floor = Floor(window=0.02)
    async def stop(): return ''
    task = asyncio.create_task(floor.request('Lucy', stop))
    await asyncio.sleep(0)
    await floor.seize_by_human()
    floor.release_human()
    assert not await task
    assert floor.free


async def test_three_puppets_select_only_one_composer_and_yield(clock, tmp_path, monkeypatch):
    monkeypatch.setattr('echo.floor.random.choice', lambda names: names[-1])
    brains = [(name, FakeBrain([Decision(True, name + '的台词', intent=name + '的想法')]))
              for name in ('Charlie', 'Lucy', 'Kaka')]
    room, puppets, _, _, _ = build(clock, tmp_path, brains)
    room.floor = Floor(window=0.1, sleep=clock.sleep)
    tasks = [asyncio.create_task(p.run()) for p in puppets.values()]
    try:
        await room.human_said('大家怎么看？')
        await settle(clock, 0.2)
        await settle(clock, 1)
        assert dict(brains)['Kaka'].calls
        assert dict(brains)['Charlie'].calls == []
        assert dict(brains)['Lucy'].calls == []
        lines = [e for e in room.transcript.entries if e.who == 'Kaka']
        assert lines and lines[0].text == 'Kaka的台词'
        assert puppets['Charlie'].memory.unspoken == []
        assert puppets['Lucy'].memory.unspoken == []
    finally:
        for t in tasks: t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def test_browser_no_ack_is_failure_and_stale_ack_is_ignored():
    t, sent = [0], []
    player = BrowserPlayer(sent.append, now=lambda: t[0])
    player.play(np.zeros(24000), 24000, (1, 0))
    player.acknowledge({'type': 'play_ended', 'id': 999})
    assert player.busy()
    assert player.progress() == 0
    t[0] = 4
    with pytest.raises(RuntimeError, match='acknowledgement'):
        player.busy()
    assert sent[-1] == {'type': 'stop'}


def test_browser_disconnect_and_buffer_reset():
    mic = BrowserMic()
    for _ in range(600): mic.push(bytes(4800))
    assert mic._queued_bytes <= 48000
    assert mic.dropped_bytes == 590 * 4800
    mic.disconnect()
    assert not mic.connected and mic._queue.empty()
    player = BrowserPlayer(lambda _: None)
    player.play(np.zeros(2400), 24000, (1, 0))
    player.disconnect()
    with pytest.raises(RuntimeError, match='disconnected'):
        player.busy()


async def test_explicit_single_character_stop_interrupts_partial():
    room = RoomSpy()
    async def stop(): return ''
    room.floor.try_acquire('Kaka', stop)
    ears = Ears(room, lambda: '我的羽毛多美丽', log_line=lambda _: None)
    await ears.on_started()
    await ears.on_partial('停')
    assert room.floor.holder == HUMAN


async def test_monitor_has_single_audio_owner():
    from aiohttp import web, ClientSession
    from aiohttp.test_utils import TestServer
    from echo.monitor import Monitor
    class Room(RoomSpy):
        def subscribe(self): return asyncio.Queue()
    monitor = Monitor(Room(), [], on_mic_frame=lambda f: frames.append(f))
    monitor.snapshot = lambda: {'type': 'status'}
    frames, ack, disconnects = [], [], []
    monitor.on_playback = ack.append
    monitor.on_audio_disconnect = lambda: disconnects.append(True)
    app = web.Application()
    app.router.add_get('/ws', monitor._ws)
    async with TestServer(app) as server, ClientSession() as client:
        async with client.ws_connect(server.make_url('/ws')) as a, client.ws_connect(server.make_url('/ws')) as b:
            await a.receive_json(); await b.receive_json()
            await a.send_json({'type': 'audio_ready'})
            await a.send_bytes(b'first')
            await b.send_json({'type': 'audio_ready'})
            assert (await b.receive_json())['type'] == 'audio_rejected'
            await b.send_bytes(b'wrong microphone')
            await a.send_json({'type': 'play_started', 'id': 1})
            await a.send_json({'type': 'say', 'text': '同步屏障'})
            await asyncio.sleep(0.02)
            monitor.broadcast({'type': 'play', 'id': 1})
            assert (await a.receive_json())['type'] == 'play'
            assert frames == [b'first']
            assert ack == [{'type': 'play_started', 'id': 1}]
        await asyncio.sleep(0.02)
        assert disconnects == [True]


async def test_realtime_source_maps_sdk_events_and_disconnects():
    from contextlib import asynccontextmanager
    from types import SimpleNamespace as NS
    from echo.ears import RealtimeSource
    class Connection:
        session = NS(update=None)
        input_audio_buffer = NS(append=None)
        def __init__(self):
            async def update(**kwargs): pass
            async def append(**kwargs): pass
            self.session = NS(update=update)
            self.input_audio_buffer = NS(append=append)
        async def __aiter__(self):
            for event in [NS(type='input_audio_buffer.speech_started', item_id='a'),
                          NS(type='conversation.item.input_audio_transcription.delta', item_id='a', delta='你好'),
                          NS(type='input_audio_buffer.speech_stopped', item_id='a'),
                          NS(type='conversation.item.input_audio_transcription.completed', item_id='a', transcript='你好')]:
                yield event
    @asynccontextmanager
    async def connect(**kwargs):
        yield Connection()
    async def frames():
        await asyncio.Event().wait()
        yield b''
    source = RealtimeSource(NS(realtime=NS(connect=connect)), lambda: False,
                            frames=frames, on_status=lambda _: None)
    result = []
    events = source.events()
    try:
        for _ in range(5):
            result.append(await asyncio.wait_for(anext(events), 1))
    finally:
        await events.aclose()
    assert result == [('started', 'a'), ('partial', '你好'), ('stopped', 'a'),
                      ('said', '你好', 'a'), ('disconnected',)]


async def test_offline_app_assembly_and_shutdown(tmp_path, monkeypatch):
    from echo.__main__ import main_async
    from echo.console import Console
    personas = tmp_path / 'personas'
    personas.mkdir()
    for name in ('Charlie', 'Lucy', 'Kaka'):
        (personas / f'{name}.txt').write_text(f'你是{name}')
    config = tmp_path / 'offline.toml'
    config.write_text('''state_dir = "temporary-state"
[persona]
dir = "personas"
[room]
turn_window = 0.01
[mouth]
mode = "off"
[ears]
mode = "console"
[monitor]
port = 0
''')
    async def conversation(console):
        await console.room.human_said('大家好')
        await asyncio.sleep(0.85)
        assert console.room.floor.holder in ('Charlie', 'Lucy', 'Kaka')
        await console.room.human_started()
        assert console.room.floor.holder == HUMAN
        await console.room.human_said('我还在说')
    monkeypatch.setattr(Console, 'run', conversation)
    await main_async(config, fake=True)
    assert (tmp_path / 'temporary-state' / 'transcript.jsonl').exists()
    await drain()
    assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]

@pytest.mark.parametrize('text', ['再见', '嗯?', '我不。'])
async def test_short_false_transcripts_during_playback_do_not_interrupt_or_commit(text):
    room = RoomSpy()
    async def stop(): return ''
    room.floor.try_acquire('Lucy', stop)
    ears = Ears(room, lambda: '我叫Lucy，可以等我说完吗？', log_line=lambda _: None)
    await ears.consume(gen_guarded_turn(text))
    assert room.calls == []
    assert room.floor.holder == 'Lucy'

async def gen_guarded_turn(text):
    yield ('started', 'a')
    yield ('partial', text)
    yield ('said', text, 'a')
    yield ('stopped', 'a')

async def test_real_question_and_stop_still_interrupt_during_playback():
    for text in ('耗子怎么不说话', '停', '等一下'):
        room = RoomSpy()
        async def stop(): return ''
        room.floor.try_acquire('Charlie', stop)
        ears = Ears(room, lambda: '我们去酒吧街散步', log_line=lambda _: None)
        await ears.consume(gen_guarded_turn(text))
        assert room.calls == ['started', ('said', text)]
        assert room.floor.free

async def test_guard_survives_interruption_until_final_transcript():
    room = RoomSpy()
    async def stop(): return ''
    room.floor.try_acquire('Charlie', stop)
    ears = Ears(room, lambda: '我们去酒吧街散步', log_line=lambda _: None)
    await ears.on_started()
    await ears.on_partial('一个临时识别句子')
    assert room.floor.holder == HUMAN
    await ears.on_said('嗯?')
    assert room.calls == ['started']
    assert room.floor.free

async def test_quiet_reminders_do_not_restart_selected_composition(clock, tmp_path):
    from echo.events import Quiet
    entered, finish = asyncio.Event(), asyncio.Event()
    class SlowBrain(FakeBrain):
        attempts = 0
        async def decide(self, *args):
            raise AssertionError('Direct selection must never request decide')
        async def compose(self, *args):
            self.attempts += 1
            entered.set()
            await finish.wait()
            return ''
    brain = SlowBrain()
    room, puppets, *_ = build(clock, tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    task = asyncio.create_task(p.run())
    try:
        await room.human_said('你们好')
        await entered.wait()
        original = p._speech_task
        for _ in range(3):
            await room.publish(Quiet(clock.now(), 3))
            await drain()
        assert brain.attempts == 1
        assert p._speech_task is original and not original.cancelled()
        finish.set()
        await drain()
        assert original.done()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

@pytest.mark.parametrize('text, expected', [('Lucy，你为什么不说话？', 'Lucy'), ('小耗子怎么不说话', 'Lucy'),
    ('Charlie, hello!', 'Charlie'), ('鸵鸟，你好', 'Kaka'), ('Charlie和Lucy，你们好', None),
    ('你觉得Charlie怎么样', None), ('Lucydog hello', None), ('大家好', None)])
def test_explicit_opening_address(text, expected):
    from echo.floor import addressed_character
    assert addressed_character(text) == expected

async def test_address_overrides_previous_speaker_and_never_calls_decide(clock, tmp_path, monkeypatch):
    monkeypatch.setattr('echo.floor.random.choice', lambda names: names[-1])
    class DirectBrain(FakeBrain):
        async def decide(self, *args): raise AssertionError('decide must not run')
    brains = [(name, DirectBrain([Decision(True, '你好')])) for name in ('Charlie', 'Lucy', 'Kaka')]
    room, puppets, *_ = build(clock, tmp_path, brains)
    room.floor._last_winner = 'Lucy'
    tasks = [asyncio.create_task(p.run()) for p in puppets.values()]
    try:
        await room.human_said('Lucy，你好')
        await settle(clock)
        assert room.floor.holder == 'Lucy'
        assert len(dict(brains)['Lucy'].calls) == 1
        assert dict(brains)['Charlie'].calls == dict(brains)['Kaka'].calls == []
    finally:
        for task in tasks: task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

@pytest.mark.parametrize('line', ['', ' \n ', '……', '（轻轻点头）'])
async def test_selected_empty_or_unspoken_output_is_failure_not_chosen_silence(clock, tmp_path, line):
    from echo.events import PuppetStarted
    class InvalidLineBrain(FakeBrain):
        async def decide(self, *args): raise AssertionError('No speak decision is allowed')
        async def compose(self, *args): return line
    room, puppets, _, motors, logs = build(clock, tmp_path, [('Lucy', InvalidLineBrain())])
    watcher = room.subscribe()
    task = asyncio.create_task(puppets['Lucy'].run())
    try:
        await room.human_said('Lucy，你好')
        await settle(clock, 1)
        assert room.floor.free
        assert not motors.log
        assert not any(isinstance(event, PuppetStarted) for event in list(watcher._queue))
        assert any('台词生成失败' in log for log in logs)
        assert not any('选择沉默' in log for log in logs)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

async def test_audio_readiness_tracks_owner_and_reconnects_only_once():
    from aiohttp import web, ClientSession
    from aiohttp.test_utils import TestServer
    from echo.monitor import Monitor
    class Room(RoomSpy):
        def subscribe(self): return asyncio.Queue()
    monitor = Monitor(Room(), [])
    monitor.snapshot = lambda: {'type': 'status'}
    readies = []
    monitor.on_audio_ready = lambda: readies.append(True)
    app = web.Application()
    app.router.add_get('/ws', monitor._ws)
    async with TestServer(app) as server, ClientSession() as client:
        async with client.ws_connect(server.make_url('/ws')) as ws:
            await ws.receive_json()
            assert not monitor.audio_ready.is_set()
            await ws.send_json({'type': 'audio_ready'})
            await ws.send_json({'type': 'audio_ready'})
            await asyncio.sleep(0.02)
            assert monitor.audio_ready.is_set() and len(readies) == 1
            await ws.send_json({'type': 'audio_off'})
            await asyncio.sleep(0.02)
            assert not monitor.audio_ready.is_set()
            await ws.send_json({'type': 'audio_ready'})
            await asyncio.sleep(0.02)
            assert monitor.audio_ready.is_set() and len(readies) == 2
        await asyncio.sleep(0.02)
        assert not monitor.audio_ready.is_set()
