import asyncio

from echo.motors import PrintMotors
from echo.mouth import PrintMouth


async def test_print_mouth_finishes(clock):
    lines = []
    mouth = PrintMouth(clock, chars_per_second=10, out=lines.append)
    task = asyncio.create_task(mouth.say("Kaka", "一二三四五六七八九十"))  # 10 字 = 1 秒
    await asyncio.sleep(0)
    await clock.advance(1.5)
    assert await task == ("一二三四五六七八九十", True)
    assert lines == ["@Kaka: 一二三四五六七八九十"]
    assert await mouth.stop() == ""  # 已经说完，没什么可停


async def test_print_mouth_stopped_midway(clock):
    lines = []
    mouth = PrintMouth(clock, chars_per_second=10, out=lines.append)
    task = asyncio.create_task(mouth.say("Kaka", "一二三四五六七八九十"))
    await asyncio.sleep(0)
    await clock.advance(0.4)
    prefix = await mouth.stop()
    assert prefix == "一二三四"
    assert await task == ("一二三四", False)
    assert lines[-1] == "@Kaka: …（被打断）"


async def test_print_motors_logs():
    out = []
    m = PrintMotors(out=out.append)
    await m.speaking("Lucy")
    await m.restless("Kaka")
    await m.silent("Lucy")
    assert m.log == [("speaking", "Lucy"), ("restless", "Kaka"), ("silent", "Lucy")]
    assert len(out) == 3


# ---------- TtsMouth ----------

from echo.mouth import TtsMouth, speakable, split_sentences


def test_split_sentences_and_stage_directions():
    assert split_sentences("当然是我。你看我这羽毛！还用问吗？") == ["当然是我。", "你看我这羽毛！", "还用问吗？"]
    assert split_sentences("……我不知道。") == ["……我不知道。"]
    assert split_sentences("没有标点的一句") == ["没有标点的一句"]
    assert speakable("（沉默了一会儿）算了。") == "算了。"
    assert speakable("（只有动作）") == ""


class FakePlayer:
    def __init__(self):
        self.played, self._busy, self.stopped = [], False, 0

    def play(self, pcm, sr, pan):
        self.played.append((len(pcm), sr, pan))
        self._busy = True

    def busy(self):
        return self._busy

    def finish(self):
        self._busy = False

    def stop(self):
        self._busy = False
        self.stopped += 1


def make_synth(calls):
    async def synth(name, text):
        calls.append((name, text))
        return ([0.0] * 2400, 24000)  # 0.1 秒
    return synth


async def test_tts_mouth_plays_sentence_by_sentence_with_pan():
    calls, player, out = [], FakePlayer(), []
    mouth = TtsMouth(make_synth(calls), player, {"Kaka": (0.0, 1.0)}, out=out.append)
    task = asyncio.create_task(mouth.say("Kaka", "当然是我。（挺胸）你看我这羽毛！"))
    for _ in range(2):
        while not player.busy():
            await asyncio.sleep(0.01)
        player.finish()
    assert await task == ("当然是我。（挺胸）你看我这羽毛！", True)
    assert calls == [("Kaka", "当然是我。"), ("Kaka", "你看我这羽毛！")]  # 舞台提示不念
    assert [p[2] for p in player.played] == [(0.0, 1.0), (0.0, 1.0)]
    assert out[0] == "@Kaka: 当然是我。（挺胸）你看我这羽毛！"
    assert await mouth.stop() == ""


async def test_tts_mouth_stop_returns_completed_sentences(clock):
    calls, player, out = [], FakePlayer(), []
    mouth = TtsMouth(make_synth(calls), player, {}, out=out.append)
    task = asyncio.create_task(mouth.say("Kaka", "第一句。第二句很长很长很长。第三句。"))
    while not player.busy():
        await asyncio.sleep(0.01)
    player.finish()                      # 第一句播完
    while len(player.played) < 2:
        await asyncio.sleep(0.01)        # 第二句开始播
    prefix = await mouth.stop()
    assert prefix.startswith("第一句。")
    assert "第三句" not in prefix
    assert await task == (prefix, False)
    assert player.stopped >= 1
    assert out[-1] == "@Kaka: …（被打断）"
