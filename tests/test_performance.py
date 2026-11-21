from echo.performance import Performance, gaze
from echo.brain import PerformedLine, parse_line


def test_serial_handshake_gates_eyes_and_body_configuration(monkeypatch):
    import serial
    from echo.performance import SerialStage

    class Port:
        incoming = b''
        def __init__(self, *args, **kwargs): self.writes = []
        @property
        def in_waiting(self): return len(self.incoming)
        def read(self, n):
            data, self.incoming = self.incoming[:n], self.incoming[n:]
            return data
        def write(self, data): self.writes.append(data)
        def close(self): pass

    monkeypatch.setattr(serial, 'Serial', Port)
    stage = SerialStage('test', 'HIGH', out=lambda _: None)
    assert not stage.look('Charlie', 0)
    stage.body('Charlie', 200)
    assert not stage.serial.writes
    stage.serial.incoming = b'READY ECR2\n'
    stage.poll()
    assert stage.serial.writes == [b'CONFIG HIGH\n']
    stage.body('Charlie', 200)
    assert stage.serial.writes == [b'CONFIG HIGH\n']
    stage.serial.incoming = b'ERR COMMAND\n'
    stage.config_sent_at = 0
    stage.poll()
    assert stage.serial.writes == [b'CONFIG HIGH\n', b'CONFIG HIGH\n']
    assert not stage.configured
    stage.serial.incoming = b'OK CONFIG\n'
    stage.poll()
    stage.body('Charlie', 200)
    assert stage.serial.writes[-1] == b'BODY 2 200\n'
    assert stage.look('Charlie', 0)
    assert not stage.look('Charlie', 1)
    stage.serial.incoming = b'IDLE 2\n'
    stage.poll()
    assert stage.look('Charlie', 1)
    stage.serial.incoming = b'READY ECR2\n'
    stage.poll()
    assert not stage.configured
    assert stage.can_look('Charlie')


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
    director.start('Lucy', PerformedLine('我不知道', dict(target='Charlie', tone='hesitant')), 0, 0.4)
    assert ('look', 'Lucy', 1, True, True) in stage.commands
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


def test_only_speaker_moves_and_body_is_renewed_during_playback():
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
    assert len(bodies) == 3
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


def test_long_neutral_speech_blinks_then_randomizes_gaze_without_moving_listeners():
    import random
    clock = [0.]
    stage = Stage()
    director = Performance(stage, now=lambda: clock[0], rng=random.Random(1))
    director.start('Charlie', PerformedLine('很长的一段话', dict(target='Lucy', tone='neutral')), 0, 20)
    for second in range(1, 16):
        clock[0] = second
        director.tick()
    looks = [c for c in stage.commands if isinstance(c, tuple) and c[0] == 'look']
    assert len(looks) >= 4
    assert all(c[1] == 'Charlie' for c in looks)
    assert looks[0] == ('look', 'Charlie', 2, True, False)
    directions = [look[2] for look in looks]
    assert set(directions) == set(range(9))
    assert directions[2] != directions[0]  # No mandatory return to the addressee.
    assert all(previous != current for previous, current in zip(directions, directions[1:]))


def test_pause_stops_body_freezes_eye_timing_and_preserves_turn():
    import random
    clock = [0.]
    stage = Stage()
    director = Performance(stage, now=lambda: clock[0], rng=random.Random(1))
    line = PerformedLine('一句。另一句。', dict(target='Lucy', tone='neutral'))
    director.start('Charlie', line, 0, 2)
    clock[0] = 0.25
    director.tick()
    director.pause()
    before = list(stage.commands)
    remaining = director.turn['wait']
    clock[0] = 30
    director.tick()
    assert stage.commands == before
    director.start('Charlie', line, 1, 3)
    assert director.turn['wait'] == remaining
    looks = [c for c in stage.commands if isinstance(c, tuple) and c[0] == 'look']
    assert len(looks) == 1  # next sentence does not restart the initial gaze
    director.stop()
    assert director.turn is None


async def test_tts_recenters_only_after_last_sentence():
    import numpy as np
    from echo.mouth import TtsMouth

    stage = Stage()

    class Player:
        def play(self, *args):
            self.playing = True
            stage.commands.append('play')
        def busy(self):
            playing, self.playing = self.playing, False
            return playing

    async def synth(*args):
        return np.zeros(2400), 24000

    mouth = TtsMouth(synth, Player(), {})
    mouth.performance = Performance(stage)
    line = PerformedLine('你好呀。再见啦。', dict(target='Charlie'))
    assert await mouth.say('Lucy', line) == (line, True)
    assert stage.commands.count('play') == 2
    assert [command for command in stage.commands if command[0] == 'look'] == [
        ('look', 'Lucy', 1, True, False),
        ('look', 'Lucy', 0, False, True),
    ]
    assert stage.commands[-2:] == ['STOP', ('look', 'Lucy', 0, False, True)]


def test_recenter_waits_until_the_eye_is_idle():
    stage = Stage()
    director = Performance(stage)
    line = PerformedLine('你好', dict(target='Charlie'))
    director.start('Lucy', line, 0, 1)
    original_look = stage.look
    stage.look = lambda *args: False
    director.finish()
    assert stage.commands[-1] == 'STOP'
    stage.look = original_look
    director.poll()
    director.poll()
    center = ('look', 'Lucy', 0, False, True)
    assert stage.commands[-1] == center
    assert stage.commands.count(center) == 1


def test_busy_eyes_are_not_sent_another_command_but_body_keeps_running():
    clock = [0.]
    stage = Stage()
    stage.can_look = lambda name: clock[0] < 1 or clock[0] > 10
    director = Performance(stage, now=lambda: clock[0])
    director.start('Lucy', PerformedLine('长句', dict(target='Charlie')), 0, 20)
    clock[0] = 9
    director.tick()
    assert len([c for c in stage.commands if isinstance(c, tuple) and c[0]=='look']) == 1
    assert len([c for c in stage.commands if isinstance(c, tuple) and c[0]=='body']) == 2
    clock[0] = 11
    director.tick()
    assert len([c for c in stage.commands if isinstance(c, tuple) and c[0]=='look']) == 2


def test_prompt_and_schema_request_only_used_performance_fields():
    from echo.brain import LINE_SCHEMA
    from echo.prompts import catalog
    schema = LINE_SCHEMA['properties']['performance']
    assert set(schema['properties']) == set(schema['required']) == {'target', 'tone'}
    for language in ('zh', 'en'):
        prompt = catalog(language)['performance']
        assert 'body' not in prompt
        assert 'target' in prompt and 'tone' in prompt
