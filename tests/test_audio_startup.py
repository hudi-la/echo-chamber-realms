import asyncio
from types import SimpleNamespace as NS
from echo.__main__ import main_async


async def test_browser_startup_serves_page_but_waits_for_audio_before_wake(tmp_path, monkeypatch):
    import echo.__main__ as app
    started, console_entered, finish = asyncio.Event(), asyncio.Event(), asyncio.Event()
    instances = []
    class Monitor:
        def __init__(self, room, puppets, **kwargs):
            self.room, self.audio_ready = room, asyncio.Event()
            instances.append(self)
        def log(self, line): pass
        def broadcast(self, msg): pass
        async def start(self): started.set(); return []
    class Console:
        def __init__(self, room): pass
        async def run(self): console_entered.set(); await finish.wait()
    monkeypatch.setattr(app, 'Monitor', Monitor)
    monkeypatch.setattr(app, 'Console', Console)
    monkeypatch.setenv('OPENAI_API_KEY', 'fake-test-key')
    monkeypatch.setattr(app, 'OpenAISynth', lambda *args, **kwargs: NS())
    config = tmp_path / 'config.toml'
    config.write_text('state_dir="state"\n[audio]\nio="browser"\n[mouth]\nmode="tts"\n[mouth.pitch]\nCharlie=0\nLucy=0\nKaka=0\n[monitor]\nport=18765\n')
    task = asyncio.create_task(main_async(config, fake=True))
    try:
        await asyncio.wait_for(started.wait(), 2)
        monitor = instances[0]
        assert monitor.waiting_for_audio
        assert monitor.room.day == 0
        assert not console_entered.is_set()
        assert not any(e.kind == 'woke' for e in monitor.room.transcript.entries)
        monitor.audio_ready.set()
        await asyncio.wait_for(console_entered.wait(), 2)
        assert not monitor.waiting_for_audio
        assert monitor.room.day == 1
        opening = [e for e in monitor.room.transcript.entries
                   if e.kind == 'said' and e.who == '新朋友']
        assert [e.text for e in opening] == ['你们为什么不出去？']
        # Audio reconnection must not replay the startup question.
        monitor.on_audio_ready()
        await asyncio.sleep(0)
        assert len([e for e in monitor.room.transcript.entries
                    if e.kind == 'said' and e.who == '新朋友']) == 1
        finish.set()
        await asyncio.wait_for(task, 2)
    finally:
        if not task.done(): task.cancel()
        await asyncio.gather(task, return_exceptions=True)
