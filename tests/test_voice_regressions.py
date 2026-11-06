import asyncio
import pytest
from echo.clock import FakeClock
from echo.brain import Rumination
from echo.mouth import TtsMouth
from echo.audio_io import BrowserMic
from tests.test_puppet import build, settle
from tests.fakes import FakeBrain
from echo.events import HumanSaid

class Player:
    def play(self, *args): pass
    def busy(self): return False
    def stop(self): pass

async def test_stop_during_blocked_synthesis():
    entered, release = asyncio.Event(), asyncio.Event()
    async def synth(*args):
        entered.set()
        await release.wait()
        return ([0.0], 24000)
    mouth = TtsMouth(synth, Player(), {}, out=lambda _: None)
    saying = asyncio.create_task(mouth.say('Kaka', '你好。'))
    await entered.wait()
    stopping = asyncio.create_task(mouth.stop())
    try:
        done, _ = await asyncio.wait({stopping}, timeout=0.2)
        assert stopping in done, 'stop() still waiting for blocked synthesis after 200ms'
    finally:
        release.set()
        await asyncio.gather(saying, stopping, return_exceptions=True)

async def test_playback_error_releases_floor_and_stops_motors(tmp_path):
    clock = FakeClock()
    room, puppets, _, motors, _ = build(clock, tmp_path, [('Kaka', FakeBrain())])
    puppet = puppets['Kaka']
    class BrokenMouth:
        async def say(self, *args): raise RuntimeError('simulated playback failure')
        async def stop(self): return ''
    puppet.mouth = BrokenMouth()
    assert room.floor.try_acquire('Kaka', puppet.mouth.stop)
    await puppet.speak('你好')
    assert (room.floor.free, motors.log[-1]) == (True, ('silent', 'Kaka'))

async def test_rumination_preserves_new_thoughts(tmp_path):
    clock = FakeClock()
    entered, release = asyncio.Event(), asyncio.Event()
    class SlowBrain(FakeBrain):
        async def ruminate(self, *args):
            entered.set()
            await release.wait()
            return Rumination([])
    _, puppets, *_ = build(clock, tmp_path, [('Lucy', SlowBrain())])
    p = puppets['Lucy']
    p.memory.add_thought('旧感受', '旧想法', None, clock.wall(), 8)
    pending = asyncio.create_task(p.ruminate(None))
    await entered.wait()
    p.memory.add_thought('新感受', '新想法', None, clock.wall(), 8)
    p.memory.note_heard(clock.wall())
    release.set()
    await pending
    assert ([t['feeling'] for t in p.memory.thoughts], p.memory.heard) == (['新感受'], 1)

async def test_burst_events_count_all_heard_lines(tmp_path):
    clock = FakeClock()
    room, puppets, *_ = build(clock, tmp_path, [('Lucy', FakeBrain())])
    p = puppets['Lucy']
    for i in range(2):
        await room.publish(HumanSaid(clock.now(), f'第{i}句'))
    task = asyncio.create_task(p.run())
    try:
        await settle(clock)
        assert p.memory.heard == 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

def test_mic_buffer_is_bounded():
    mic = BrowserMic()
    frame = bytes(4800)  # 100 ms @ 24kHz int16 mono
    for _ in range(600): mic.push(frame)
    assert mic._queue.qsize() <= 50, f'buffer holds {mic._queue.qsize()/10:.0f} seconds of stale audio'
