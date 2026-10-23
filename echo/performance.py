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
        self.eye_busy = {}

    def poll(self):
        if not self.serial:
            return
        try:
            self.buffer += self.serial.read(min(self.serial.in_waiting, 512))
            while b'\n' in self.buffer:
                line, self.buffer = self.buffer.split(b'\n', 1)
                reply = line.decode(errors='replace').strip()
                self.out('[Arduino] ' + reply)
                if reply == 'READY ECR2':
                    self.eye_busy.clear()
                    self.ready = True
                    if self.enabled:
                        self.send('CONFIG ' + self.relay_active)
                if reply.startswith('IDLE '):
                    self.eye_busy.pop(int(reply.split()[1]), None)
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

    def can_look(self, name):
        return time.monotonic() >= self.eye_busy.get(NAMES.index(name), 0)

    def look(self, name, direction, blink=False, smooth=False):
        if not self.can_look(name):
            return False
        self.eye_busy[NAMES.index(name)] = time.monotonic() + 3.0
        self.send(f'LOOK {NAMES.index(name)} {direction} {int(blink)} {int(smooth)}')
        return True

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
    """Only the speaker moves. Eye timing survives sentence boundaries and audio gaps."""
    def __init__(self, stage, now=time.monotonic, rng=None):
        self.stage, self.now, self.rng = stage, now, rng or random.Random()
        self.active = None
        self.turn = None

    def _look(self, direction, initial=False):
        t = self.turn
        if not getattr(self.stage, 'can_look', lambda name: True)(t['name']):
            return False
        result = self.stage.look(t['name'], direction,
                                 False if initial else self.rng.random() < .35,
                                 t['tone'] == 'hesitant')
        if result is False:
            return False
        t['current'] = direction
        t['wait'] = self.rng.uniform(3.2, 4.8)
        t['initial'] = False
        return True

    def start(self, name, text, sentence, duration):
        self.pause()
        if sentence == 0 or self.turn is None or self.turn['name'] != name:
            info = getattr(text, 'performance', {})
            target = info.get('target', 'audience')
            if target == name or target not in (*NAMES, 'audience'):
                target = 'audience'
            self.turn = dict(name=name, target=target, tone=info.get('tone', 'neutral'),
                             main=gaze(name, target), current=None, wait=0, initial=True)
        t = self.turn
        self.stage.poll()
        self.stage.out(f"[表演] {name} → {t['target']} / {t['tone']} / 第{sentence + 1}句")
        now = self.now()
        self.active = dict(name=name, at=now, duration=duration, last=now, body_at=now)
        if t['initial']:
            self._look(t['main'], initial=True)
        # Renewable lease: stay on throughout playback; loss of updates turns it off.
        self.stage.body(name, 1200)

    def tick(self):
        self.stage.poll()
        a, t = self.active, self.turn
        if not a:
            return
        now = self.now()
        t['wait'] -= max(0, now - a['last'])
        a['last'] = now
        if now - a['body_at'] >= .4:
            self.stage.body(a['name'], 1200)
            a['body_at'] = now
        if t['initial']:
            self._look(t['main'], initial=True)
        elif t['wait'] <= 0:
            # Alternate brief aversion and returning to the intended interlocutor.
            direction = (t['main'] if t['current'] != t['main'] else
                         self.rng.choice([d for d in (0, 1, 2) if d != t['main']]))
            self._look(direction)

    def pause(self):
        if self.active:
            self.stage.send('STOP')
        self.active = None

    def stop(self):
        self.pause()
        self.turn = None


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
            ('Charlie', 'Lucy，你真的相信他说的？', dict(target='Lucy', tone='curious')),
            ('Lucy', '我……也没有说他一定是对的。', dict(target='Charlie', tone='hesitant')),
            ('Kaka', '我早就告诉过你！', dict(target='audience', tone='excited')),
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
