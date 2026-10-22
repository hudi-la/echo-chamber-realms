from echo.performance import Performance, gaze
from echo.brain import PerformedLine, parse_line


class Stage:
    def __init__(self): self.commands = []
    def out(self, text): pass
    def poll(self): pass
    def send(self, line): self.commands.append(line)
    def look(self, *args): self.commands.append(('look', *args))
    def body(self, *args): self.commands.append(('body', *args))


def test_character_relative_directions():
    assert gaze('Kaka', 'Lucy') == 1
    assert gaze('Charlie', 'Lucy') == 2
    assert gaze('Lucy', 'Kaka') == 2
    assert gaze('Lucy', 'Charlie') == 1
    assert gaze('Lucy', 'audience') == 0


def test_interruption_discards_future_cues():
    clock = [0.]
    stage = Stage()
    director = Performance(stage, now=lambda: clock[0])
    director.start('Lucy', PerformedLine('我不知道', dict(target='Charlie', tone='hesitant')), 0, 9)
    director.stop()
    before = list(stage.commands)
    clock[0] = 8
    director.tick()
    assert stage.commands == before
    assert before[-1] == 'STOP'


def test_metadata_is_not_spoken_and_legacy_text_works():
    line = parse_line('{"text":"你好", "performance":{"target":"Lucy","tone":"curious","body":false}}')
    assert line == '你好'
    assert line.performance['target'] == 'Lucy'
    assert parse_line('{"text":"旧台词"}') == '旧台词'


def test_only_speaker_moves_and_each_sentence_has_body_cue():
    clock = [0.]
    stage = Stage()
    director = Performance(stage, now=lambda: clock[0])
    line = PerformedLine('你好', dict(target='Lucy', tone='excited', body=True))
    director.start('Charlie', line, 0, 4)
    assert len([c for c in stage.commands if isinstance(c, tuple) and c[0]=='look']) == 1
    clock[0] = .5
    director.tick()
    looks = [c for c in stage.commands if isinstance(c, tuple) and c[0]=='look']
    assert len(looks) == 1
    assert all(c[1] == 'Charlie' for c in looks)
    director.start('Charlie', line, 1, 4)
    bodies = [c for c in stage.commands if isinstance(c, tuple) and c[0]=='body']
    assert len(bodies) == 2
    assert all(c[1] == 'Charlie' for c in bodies)


async def test_audio_ack_gates_actions_and_failure_clears_them():
    import asyncio
    import numpy as np
    from echo.mouth import TtsMouth

    class Player:
        playback_started = False
        active = True
        failure = False
        def play(self, *args): pass
        def busy(self):
            if self.failure: raise RuntimeError('disconnected')
            return self.active
        def stop(self): self.active = False

    async def synth(*args): return np.zeros(2400), 24000
    player = Player()
    stage = Stage()
    mouth = TtsMouth(synth, player, {})
    mouth.performance = Performance(stage)
    task = asyncio.create_task(mouth.say('Charlie', PerformedLine('你好。')))
    await asyncio.sleep(.07)
    assert not stage.commands
    player.playback_started = True
    await asyncio.sleep(.07)
    assert mouth.performance.active is not None
    player.failure = True
    import pytest
    with pytest.raises(RuntimeError, match='disconnected'):
        await task
    assert mouth.performance.active is None
    assert stage.commands[-1] == 'STOP'
