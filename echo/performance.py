"""Sparse sentence performance, clocked from confirmed playback. No delayed action queue."""
import os
import random
import time

NAMES = ('Kaka', 'Lucy', 'Charlie')  # audience left to right


def gaze(name, target):
    if target not in NAMES or target == name:
        return 0
    return 1 if NAMES.index(target) > NAMES.index(name) else 2


class SerialStage:
    def __init__(self, port=None, relay_active=None, out=print):
        self.out, self.serial = out, None
        self.enabled = relay_active in ('HIGH', 'LOW')
        self.ready = False
        self.last = time.monotonic()
        self.relay_active = relay_active
        if port:
            import serial
            self.serial = serial.Serial(port, 115200, timeout=0, write_timeout=0.2)
        self.buffer = b''

    def poll(self):
        if not self.serial:
            return
        try:
            self.buffer += self.serial.read(min(self.serial.in_waiting, 512))
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                reply = line.decode(errors='replace').strip()
                self.out('[Arduino] ' + reply)
                if reply == 'READY ECR1':
                    self.ready = True
                    if self.enabled:
                        self.send('CONFIG ' + self.relay_active)
            if len(self.buffer) > 1024:
                self.buffer = b''
            if self.ready and time.monotonic() - self.last > .5:
                self.send('PING')
        except (OSError, ValueError) as error:
            self.out('[动作] 串口断开: ' + str(error))
            self.serial.close()
            self.serial = None
            self.ready = False

    def send(self, line):
        if line != 'PING':
            self.out('[动作] ' + line)
        if self.serial and self.ready:
            try:
                self.serial.write((line + '\n').encode('ascii'))
                self.last = time.monotonic()
            except (OSError, ValueError) as error:
                self.out('[动作] 写入失败: ' + str(error))
                self.ready = False  # firmware watchdog releases relays

    def look(self, name, direction, blink=False, smooth=False):
        self.send(f'LOOK {NAMES.index(name)} {direction} {int(blink)} {int(smooth)}')

    def body(self, name, milliseconds):
        if self.enabled:
            self.send(f'BODY {NAMES.index(name)} {milliseconds}')
        else:
            self.out(f'[动作预览，身体未启用] {name}: {milliseconds}ms')

    def close(self):
        self.send('STOP')
        if self.serial:
            self.serial.close()


class Performance:
    def __init__(self, stage, now=time.monotonic, rng=None):
        self.stage, self.now, self.rng = stage, now, rng or random.Random()
        self.active = None

    def start(self, name, text, sentence, duration):
        self.stop()
        info = getattr(text, 'performance', {})
        target = info.get('target', 'audience')
        tone = info.get('tone', 'neutral')
        if target == name or target not in (*NAMES, 'audience'):
            target = 'audience'
        self.stage.poll()
        self.stage.out(f'[表演] {name} → {target} / {tone} / 第{sentence + 1}句')
        self.stage.look(name, gaze(name, target), self.rng.random() < .35,
                        tone == 'hesitant' and duration > 3)
        self.active = dict(name=name, at=self.now(), duration=duration, target=target,
                           tone=tone, listeners=False, shifted=False, returned=False)
        if sentence == 0 and info.get('body') is True:
            self.stage.body(name, min(1000, max(150, int(duration * 500))))

    def tick(self):
        self.stage.poll()
        a = self.active
        if not a:
            return
        elapsed = self.now() - a['at']
        if elapsed > .4 and not a['listeners']:
            a['listeners'] = True
            for listener in NAMES:
                if listener != a['name']:
                    self.stage.look(listener, gaze(listener, a['name']))
        # Only long hesitant lines avert and return, leaving time for each movement.
        if a['tone'] == 'hesitant' and a['duration'] > 7:
            if elapsed > 2.6 and not a['shifted']:
                a['shifted'] = True
                self.stage.look(a['name'], 0 if a['target'] != 'audience' else 1, True, True)
            if elapsed > a['duration'] - 2.4 and not a['returned']:
                a['returned'] = True
                self.stage.look(a['name'], gaze(a['name'], a['target']))

    def stop(self):
        if self.active:
            self.stage.send('STOP')
        self.active = None


if __name__ == '__main__':
    from .brain import PerformedLine
    stage = SerialStage(os.environ.get('ECR_SERIAL_PORT'), os.environ.get('ECR_RELAY_ACTIVE'))
    director = Performance(stage)
    try:
        # Opening USB resets Uno; poll for its ready handshake before the demonstration.
        deadline = time.monotonic() + 6
        while stage.serial and not stage.ready and time.monotonic() < deadline:
            stage.poll()
            time.sleep(.03)
        if stage.serial and not stage.ready:
            raise SystemExit('Arduino ECR1 firmware did not become ready')
        for name, text, info in [
            ('Charlie', 'Lucy，你真的相信他说的？', dict(target='Lucy', tone='curious', body=False)),
            ('Lucy', '我……也没有说他一定是对的。', dict(target='Charlie', tone='hesitant', body=False)),
            ('Kaka', '我早就告诉过你！', dict(target='audience', tone='excited', body=True)),
        ]:
            line = PerformedLine(text, info)
            stage.out(text)
            director.start(name, line, 0, 8 if name == 'Lucy' else 4)
            while director.now() - director.active['at'] < director.active['duration']:
                director.tick()
                time.sleep(.03)
            director.stop()
            time.sleep(.6)
    finally:
        director.stop()
        stage.close()
