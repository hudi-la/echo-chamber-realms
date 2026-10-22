"""独立声音试听：python -m echo.voice_preview --output /tmp/echo-voices。

只生成 WAV 与试听页面，不启动房间，不读取或修改木偶记忆。
"""
import argparse
import asyncio
import html
from pathlib import Path

from .config import LiveConfig
from .mouth import OpenAISynth

LINES = {
    'Charlie': '好狗狗当然最聪明啦。排名？谁发明了这么荒谬的游戏？',
    'Lucy': '……我可以问一个问题吗？安静一点，也没有错吧？',
    'Kaka': '还用问吗？当然是我。你看我的羽毛，多么漂亮。',
}
COMMON = '你好，我在听。你刚才说的，我还想再问一句。'


async def preview(config: Path, output: Path):
    import os
    import openai
    import soundfile as sf
    if not os.environ.get('OPENAI_API_KEY'):
        raise SystemExit('请先在本机终端配置 OPENAI_API_KEY；不要将密钥发送到聊天。')
    c = LiveConfig(config).current
    output.mkdir(parents=True, exist_ok=True)
    cards = []
    async with openai.AsyncOpenAI() as client:
        synth = OpenAISynth(client, c.mouth_model, c.voices, c.pitch, c.instructions, playback_speed=c.mouth_speed)
        for name, text in LINES.items():
            for kind, sentence in [('common', COMMON), ('character', text)]:
                audio = await asyncio.wait_for(synth(name, sentence), timeout=30)
                if audio is None:
                    raise RuntimeError(f'{name} 合成失败')
                pcm, sr = audio
                filename = f'{name}-{kind}.wav'
                sf.write(output / filename, pcm, sr)
                cards.append(f'<h2>{name} · {kind}</h2><p>{html.escape(sentence)}</p>'
                             f'<audio controls src="{filename}"></audio>')
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>回音室声音试听</title><h1>回音室 · AI 合成角色声音</h1>'
        '<p>先听相同文本辨别音色，再听角色台词判断人设。检查中文清晰度、刺耳度、音量与疲劳感。</p>'
        + ''.join(cards), encoding='utf-8')
    print(f'试听文件已生成：{output.resolve() / "index.html"}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=Path(__file__).resolve().parent.parent / 'config.toml')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(preview(args.config, args.output))


if __name__ == '__main__':
    main()
