import base64

import numpy as np

from echo.audio_io import BrowserMic, BrowserPlayer


async def test_browser_mic_queues_frames():
    mic = BrowserMic()
    assert not mic.connected
    mic.push(b"\x00\x01")
    mic.push(b"\x02\x03")
    assert mic.connected
    it = mic.frames()
    assert await it.__anext__() == b"\x00\x01"
    assert await it.__anext__() == b"\x02\x03"


def test_browser_player_sends_pcm_and_tracks_busy():
    sent, now = [], [100.0]
    p = BrowserPlayer(sent.append, now=lambda: now[0])
    p.play(np.zeros(24000, dtype=np.float32), 24000, (0.0, 1.0))   # 1 秒
    assert sent[0]["type"] == "play" and sent[0]["pan"] == [0.0, 1.0] and sent[0]["sr"] == 24000
    assert len(base64.b64decode(sent[0]["pcm"])) == 24000 * 2
    assert p.busy()
    now[0] = 100.9
    assert p.busy()
    now[0] = 101.1
    assert p.busy()  # 没有浏览器结束确认，不能猜成播放完成
    p.acknowledge({"type": "play_started", "id": 1})
    p.acknowledge({"type": "play_ended", "id": 1})
    assert not p.busy()
    p.play(np.zeros(2400, dtype=np.float32), 24000, (0.5, 0.5))
    assert p.busy()
    p.stop()
    assert not p.busy() and sent[-1] == {"type": "stop"}
