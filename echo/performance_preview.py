"""Prepare three TTS clips, then play a countdown-led hardware preview without the room."""
import argparse
import asyncio
from pathlib import Path

from .brain import PerformedLine
from .config import LiveConfig
from .mouth import OpenAISynth, PygamePlayer, TtsMouth
from .performance import Performance, SerialStage

ROOT = Path(__file__).resolve().parent.parent
LINES = [
    ('Charlie', 'Lucy，你真的相信他说的？', dict(target='Lucy', tone='curious'),
     'Ask Lucy with curious disbelief; emphasize the question without shouting.'),
    ('Lucy', '我……也没有说他一定是对的。', dict(target='Charlie', tone='hesitant'),
     'Sound hesitant and defensive, with a natural thoughtful pause after 我.'),
    ('Kaka', '我早就告诉过你！', dict(target='audience', tone='excited'),
     'Sound excited and smug, with a brief emphatic delivery.'),
]


async def prepare(directory):
    import openai
    import soundfile as sf
    c = LiveConfig(ROOT / 'config.toml').current
    directory.mkdir(parents=True, exist_ok=True)
    async with openai.AsyncOpenAI() as client:
        for name, text, info, delivery in LINES:
            instructions = dict(c.instructions)
            instructions[name] = instructions.get(name, '') + '\n' + delivery
            synth = OpenAISynth(client, c.mouth_model, c.voices, c.pitch, instructions,
                                playback_speed=c.mouth_speed)
            audio = await asyncio.wait_for(synth(name, text), timeout=60)
            if audio is None:
                raise RuntimeError(f'{name} TTS failed')
            pcm, sr = audio
            sf.write(directory / f'{name}.wav', pcm, sr)
            print(f'{name}: {text} ({len(pcm)/sr:.2f}s)', flush=True)


async def play(directory, port, relay_active, countdown):
    import soundfile as sf
    import pygame
    # Validate every clip and initialize audio before opening hardware.
    clips = {name: sf.read(directory / f'{name}.wav', dtype='float32') for name, *_ in LINES}
    player = PygamePlayer()
    player._ensure(clips['Charlie'][1])
    stage = SerialStage(port, relay_active)
    director = Performance(stage)
    async def cached(name, text): return clips[name]
    mouth = TtsMouth(cached, player, {name: (0.8, 0.8) for name, *_ in LINES})
    mouth.performance = director
    try:
        deadline = asyncio.get_running_loop().time() + 6
        while not stage.ready and asyncio.get_running_loop().time() < deadline:
            stage.poll()
            await asyncio.sleep(.03)
        if not stage.ready:
            raise RuntimeError('Arduino READY ECR2 handshake timed out')
        stage.poll()
        for remaining in range(countdown, 0, -1):
            print(f'{remaining} 秒后开始', flush=True)
            for _ in range(20):
                stage.poll()
                await asyncio.sleep(.05)
        for name, text, info, _ in LINES:
            print(f'现在：{name} — {text}', flush=True)
            spoken, completed = await mouth.say(name, PerformedLine(text, info))
            if not completed:
                raise RuntimeError('Playback interrupted')
            for _ in range(30):
                stage.poll()
                await asyncio.sleep(.05)
    finally:
        await mouth.stop()
        director.stop()
        stage.close()
        pygame.mixer.quit()
    print('演示结束，身体已停止。', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--port', default='/dev/cu.usbmodem1401')
    parser.add_argument('--relay-active', choices=['HIGH', 'LOW'], default='HIGH')
    parser.add_argument('--countdown', type=int, default=10)
    parser.add_argument('--directory', type=Path, default=ROOT / 'work' / 'performance-audio')
    args = parser.parse_args()
    asyncio.run(prepare(args.directory) if args.prepare else
                play(args.directory, args.port, args.relay_active, args.countdown))


if __name__ == '__main__':
    main()
