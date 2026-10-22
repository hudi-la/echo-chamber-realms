"""组装与启动。python -m echo [--config config.toml] [--fake] [--reset NAME|all] [--seed]"""
import argparse
import asyncio
import logging
import os
import sys
from itertools import cycle
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from .brain import Decision, Rumination, make_brain
from .clock import Clock
from .config import LiveConfig
from .audio_io import BrowserMic, BrowserPlayer
from .console import Console
from .ears import Ears, PlaybackGate, RealtimeSource
from .events import Quiet
from .floor import Floor
from .memory import ChangeLog, Days, PuppetMemory, reset_memories
from .monitor import Monitor
from .motors import PrintMotors
from .mouth import OpenAISynth, PrintMouth, PygamePlayer, TtsMouth
from .puppet import Puppet
from .room import Room
from .transcript import Transcript

NAMES = ("Charlie", "Lucy", "Kaka")
ROOT = Path(__file__).resolve().parent.parent


def load_persona(name: str, persona_dir: Path = ROOT / "charactor_setting") -> str:
    return (persona_dir / f"{name}.txt").read_text(encoding="utf-8")


# ======================= 只给 --fake 用的假脑子 =======================

class ScriptedBrain:
    """--fake 用：轮流说几句固定台词，让人不花钱就能看到锁、打断、反刍在跑。真脑子在 brain.py。"""

    def __init__(self, name: str) -> None:
        lines = {
            "Charlie": ["这问题问得真荒谬。", "Lucy 你别理他。"],
            "Lucy": ["……我不知道。"],
            "Kaka": ["还用问吗，当然是我。", "你们看我的羽毛。", "哼。"],
        }[name]
        self._it = cycle([Decision(True, t) for t in lines])

    async def decide(self, system: str, situation: str) -> Decision:
        await asyncio.sleep(0.3)
        return next(self._it)

    async def compose(self, system: str, situation: str, decision: Decision) -> str:
        await asyncio.sleep(0.4)  # 模拟写台词的耗时
        return next(self._it).text

    async def ruminate(self, system: str, material: str, capacity: int) -> Rumination | None:
        return Rumination(changes=[], impression="有个人来过")

    async def seed(self, system: str, material: str):
        from .brain import Seed
        return Seed(["（假出厂信念）"])


# ======================= 组装 =======================
# 顺序：配置与 key 检查 → 记忆（重置 / 天数）→ 房间 → 嘴 → 木偶 → 监控台 → 出厂信念 → 开机 → 耳朵 → 键盘 → 关机整理

async def main_async(config_path: Path, fake: bool, reset: list[str] | None = None,
                     seed: bool = False) -> None:
    live = LiveConfig(config_path)
    c = live.current
    clock = Clock()
    need_openai = c.mouth == "tts" or c.ears == "realtime" or (not fake and c.provider == "openai" and c.brain_auth == "api")
    if need_openai and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("缺 OPENAI_API_KEY（嘴 / 耳朵 / 脑子要用）。终端里 export OPENAI_API_KEY=… 再跑，"
                         "或者 config.toml 里把 mouth.mode 设 off、ears.mode 设 console 先不用声音。")
    if not fake and c.provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("缺 ANTHROPIC_API_KEY（config 里 provider = anthropic）。")
    subscription_session = None
    if not fake and c.brain_auth == "subscription":
        from .subscription import SubscriptionError, SubscriptionSession
        subscription_session = SubscriptionSession(c.subscription_profile)
        try:
            await subscription_session.ensure_models([c.model, c.ruminate_model])
        except SubscriptionError as error:
            raise SystemExit(str(error)) from None
    c.state_dir.mkdir(parents=True, exist_ok=True)
    if c.reset_on_start:
        reset = ["all"]
    if reset:
        names = list(NAMES) if "all" in [r.lower() for r in reset] else [r.capitalize() for r in reset]
        moved = reset_memories(c.state_dir, names, clock.wall().replace(":", ""))
        print("重置记忆：" + ("、".join(names) if moved else "（没有可重置的文件）")
              + (f"，旧文件挪到 {moved[0].parent}" if moved else ""))
    day = Days(c.state_dir / "days.json").wake(clock.today())

    if c.presence_source != "none":
        raise SystemExit(f"presence.source = {c.presence_source!r} 还没有对应的硬件实现（见 echo/presence.py）")
    room = Room(clock, Transcript(c.state_dir / "transcript.jsonl"), Floor(c.turn_window, clock.sleep), lambda: live.current,
                presence_reliable=False)
    browser_audio = c.audio_io == "browser" and c.monitor_port > 0
    browser_mic = BrowserMic() if browser_audio else None
    pending_play: list[dict] = []  # 监控台还没建好之前的播放消息（正常不会有）
    player_send = lambda msg: pending_play.append(msg)  # noqa: E731 —— 下面 monitor 建好后替换

    if c.mouth == "tts":
        import openai
        synth = OpenAISynth(openai.AsyncOpenAI(), c.mouth_model, c.voices, c.pitch, c.instructions, playback_speed=c.mouth_speed)
        if any(c.pitch.values()):
            print("预热升调…", end="", flush=True)
            await asyncio.get_running_loop().run_in_executor(None, synth.warmup)
            print("好了。")
        player = BrowserPlayer(lambda msg: player_send(msg), log=print) if browser_audio else PygamePlayer()
        mouth = TtsMouth(synth, player, c.pan)
    else:
        mouth = PrintMouth(clock)
    from .performance import Performance, SerialStage
    stage = SerialStage(os.environ.get("ECR_SERIAL_PORT"), os.environ.get("ECR_RELAY_ACTIVE"))
    performance = Performance(stage)
    if isinstance(mouth, TtsMouth):
        mouth.performance = performance
    motors = PrintMotors()
    changelog = ChangeLog(c.state_dir / "changes.jsonl")
    sessions = c.state_dir / "sessions.jsonl"

    monitor: Monitor | None = None
    sinks = [print]

    def log(line: str) -> None:
        for sink in sinks:
            sink(line)

    stage.out = log
    from .prompts import catalog, persona
    puppets = []
    for name in NAMES:
        brain = ScriptedBrain(name) if fake else make_brain(
            c.provider, c.model, c.puppet_effort, c.ruminate_model,
            auth=c.brain_auth, subscription_session=subscription_session)
        puppets.append(Puppet(name, persona(name, c.prompt_language), PuppetMemory.load(name, c.state_dir),
                              brain, room, mouth, motors, clock, lambda: live.current,
                              changelog, sessions, log=log))
    if c.monitor_port:
        monitor = Monitor(room, puppets, port=c.monitor_port,
                          on_mic_frame=browser_mic.push if browser_mic else None)
        if browser_audio:
            monitor.on_playback = player.acknowledge if c.mouth == "tts" else None
            def audio_disconnected():
                browser_mic.disconnect()
                if c.mouth == "tts":
                    player.disconnect()
            monitor.on_audio_disconnect = audio_disconnected
        sinks.append(monitor.log)
        player_send = monitor.broadcast
        for msg in pending_play:
            monitor.broadcast(msg)

    brain_desc = "假脑子" if fake else f"{c.provider} / {c.model} / effort={c.puppet_effort} / 脑子授权={c.brain_auth}"
    mouth_desc = f"嘴={c.mouth_model}" if c.mouth == "tts" else "嘴=打印"
    ears_desc = f"耳朵={c.ears_model}" if c.ears == "realtime" else "耳朵=键盘"
    io_desc = "音频走浏览器（在监控台页面点「音频：开」）" if browser_audio else "音频走本机"
    print(f"第 {day} 天 · {brain_desc} · {mouth_desc} · {ears_desc} · {io_desc}。"
          "打字说话，回车发送；单独一个 . 表示先开口（打断）。Ctrl-C 退出。")
    # Reviewed initial beliefs are installed only for blank memories. Never overwrite existing beliefs.
    await asyncio.gather(*[p.seed_if_blank() for p in puppets if not p.memory.beliefs])
    # Serve the page first, but do not generate speech before its output is ready.
    if monitor is not None:
        monitor.waiting_for_audio = browser_audio and c.mouth == "tts"
    background = await monitor.start() if monitor is not None else []
    if monitor is not None and monitor.waiting_for_audio:
        log("[启动] 等待声音页面就绪；尚未开始生成或播放台词。")
        await monitor.audio_ready.wait()
        monitor.waiting_for_audio = False
    from .events import HumanStarted
    action_events = room.subscribe()
    async def stage_events():
        while True:
            stage.poll()
            while not action_events.empty():
                event = action_events.get_nowait()
                if isinstance(event, HumanStarted):
                    performance.stop()
            await asyncio.sleep(.03)
    background.append(asyncio.create_task(stage_events()))
    await room.wake(day)
    background += [asyncio.create_task(room.run())] + [asyncio.create_task(p.run()) for p in puppets]
    if monitor is not None and browser_audio and c.mouth == "tts":
        async def resume_after_audio_ready():
            # Let an old disconnected playback release its lock first.
            await asyncio.sleep(0.1)
            if monitor.audio_ready.is_set() and room.floor.free:
                log("[音频] 声音页面已恢复，继续接话。")
                await room.publish(Quiet(clock.now(), clock.now() - room.last_activity))
        monitor.on_audio_ready = lambda: asyncio.create_task(resume_after_audio_ready())
    if c.ears == "realtime":
        import openai
        source = RealtimeSource(openai.AsyncOpenAI(), lambda: mouth.recent.playing,
                                c.ears_model, c.ears_language, c.ears_silence_ms, c.ears_vad_threshold,
                                gate=None if browser_audio else PlaybackGate(factor=c.ears_gate_factor,
                                                                              floor=c.ears_gate_floor),
                                device=c.ears_device,
                                frames=browser_mic.frames if browser_mic else None, on_status=log)
        ears = Ears(room, lambda: mouth.recent.text(within=8.0), interrupt=c.ears_interrupt,
                    min_chars=c.ears_min_chars, log_line=log,
                    live=monitor.hearing if monitor is not None else None)
        ears.pause_grace = c.ears_pause_grace
        ears.transcript_timeout = c.ears_transcript_timeout
        ears.activity_timeout = c.ears_activity_timeout
        background.append(asyncio.create_task(ears.consume(source.events())))
    try:
        await Console(room).run()
    finally:
        await mouth.stop()
        performance.stop()
        stage.close()
        for name in NAMES:
            await motors.silent(name)
        for t in background:
            t.cancel()
        await asyncio.gather(*background, return_exceptions=True)
        if not fake:
            await bedtime(puppets)


async def bedtime(puppets) -> None:
    """关机前回顾尚未消化的实际对话（"夜里关机是暂停"——今天的事今天消化）。失败就算了，不挡退出。"""
    pending = [p for p in puppets if p.memory.pending_experiences]
    if not pending:
        return
    print(f"睡前整理：{'、'.join(p.name for p in pending)} 在反刍…", flush=True)
    try:
        await asyncio.wait_for(asyncio.gather(*[p.ruminate_if_pending() for p in pending]), timeout=25)
        print("整理好了。")
    except asyncio.TimeoutError:
        print("反刍超时，念头留到下次。")
    except Exception as e:
        print(f"反刍失败（{e}），念头留到下次。")


# ======================= 入口 =======================

def main() -> None:
    parser = argparse.ArgumentParser(prog="echo")
    parser.add_argument("--config", type=Path, default=ROOT / "config.toml")
    parser.add_argument("--fake", action="store_true", help="用脚本化的假脑子，不需要 key")
    parser.add_argument("--reset", nargs="+", metavar="NAME",
                        help="启动时把这几只木偶的记忆挪到一边、从人设重新长（Charlie Lucy Kaka 或 all）。改了人设就该重置")
    parser.add_argument("--seed", action="store_true",
                        help="兼容选项；空白信念在启动时自动采用审定预设，不调用模型生成")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")
    code = 0
    try:
        asyncio.run(main_async(args.config, args.fake, args.reset, args.seed))
        print("\n键盘输入结束了，关机（暂停，不是清空）。")
    except KeyboardInterrupt:
        print("\n关机（暂停，不是清空）。")
    except Exception:
        import traceback
        print("\n================ 引擎异常退出 ================", flush=True)
        traceback.print_exc()
        print("==============================================", flush=True)
        code = 1
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)  # 不等任何线程（stdin 读线程、音频线程），立刻退，端口立刻释放


if __name__ == "__main__":
    main()
