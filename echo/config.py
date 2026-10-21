"""旋钮。改 config.toml 里的数字，下一轮生效，不用重启（LiveConfig 按文件改动时间重读）。
字段按 config.toml 的段分组；标了"阶段 N"的是还没接上的硬件/功能，现在不起作用。"""
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Config:
    # [model] 脑子
    provider: str            # openai | anthropic
    puppet_model: str
    puppet_effort: str       # 思考量：none | low | medium | high
    ruminate_model: str
    alt_model: str           # 对照档
    use_alt: bool

    # [room] 房间节奏
    window: int                        # 木偶看到的现场记录条数
    quiet_interval_with_visitor: float # 秒。有人时，安静多久算"安静"
    quiet_interval_alone: float        # 秒。没人时 —— 自聊的节奏
    visitor_timeout: float             # 秒。真正安静累计多久算人走了
    visitor_hard_timeout: float        # 秒。保底：这么久没人声就算走了

    # [memory] 记忆
    ruminate_every: int      # 每听到几句反思一次（计数存盘）
    bedtime_min_heard: int   # 关机前的睡前整理至少要听够这么多句
    belief_capacity: int     # 信念上限
    unspoken_keep: int       # 念头 / 没说出口的话各保留几条

    # [ears] 耳朵（Realtime 转写）
    ears: str                # console | realtime
    ears_model: str
    ears_language: str
    ears_silence_ms: int     # 人声停多少毫秒算说完
    ears_interrupt: str      # confirm | immediate
    ears_device: str | int | None   # 本机麦克风设备（io = local 才用）
    ears_min_chars: int      # 转写少于几个字当噪音
    ears_vad_threshold: float
    ears_gate_factor: float  # 播放期响度闸门（io = local 才用）
    ears_gate_floor: float   # 同上

    # [mouth] 嘴（TTS）
    mouth: str               # off | tts
    mouth_model: str
    voices: dict[str, str]
    pitch: dict[str, float]
    pan: dict[str, tuple[float, float]]
    instructions: dict[str, str]   # 可选：用文字描述声音代替升调

    # [motors] 木偶机构 —— 阶段 4，还没接 Arduino
    motors: str              # off | serial
    serial_port: str
    serial_baud: int

    # [monitor] 作者监控台
    monitor_port: int        # 0 = 关闭

    # [audio] 音频进出走哪儿
    audio_io: str            # browser（带回声消除）| local

    # [presence] "有没有人"的来源 —— 还没接硬件，只能是 none
    presence_source: str

    # [persona] 人设文件夹；state_dir 记忆目录（相对 config 文件所在目录）
    persona_dir: Path
    state_dir: Path

    prompt_language: str = "zh"
    brain_auth: str = "api"
    subscription_profile: str = "default"
    ears_pause_grace: float = 1.2
    ears_transcript_timeout: float = 8.0
    ears_activity_timeout: float = 12.0
    turn_window: float = 0.0
    mouth_speed: float = 1.0
    reset_on_start: bool = False

    @property
    def model(self) -> str:
        return self.alt_model if self.use_alt else self.puppet_model


def parse_config(text: str, base: Path) -> Config:
    d = tomllib.loads(text)
    m, r, mem = d.get("model", {}), d.get("room", {}), d.get("memory", {})
    ears, mouth, motors = d.get("ears", {}), d.get("mouth", {}), d.get("motors", {})
    provider = m.get("provider", "anthropic")
    auth = m.get("auth", "api")
    if auth not in ("api", "subscription") or (auth == "subscription" and provider != "openai"):
        raise ValueError("model.auth must be api, or subscription with provider=openai")
    puppet = m.get("puppet", "gpt-5.5" if provider == "openai" else "claude-opus-5")
    language = d.get("prompts", {}).get("language", "zh")
    if language not in ("zh", "en"):
        raise ValueError("prompts.language must be zh or en")
    import math
    speed = float(mouth.get("playback_speed", 1.0))
    if not math.isfinite(speed) or not 0.5 <= speed <= 2.0:
        raise ValueError("mouth.playback_speed must be between 0.5 and 2.0")
    from .prompts import catalog
    return Config(
        mouth_speed=speed,
        reset_on_start=bool(mem.get("reset_on_start", False)),
        prompt_language=language,
        ears_pause_grace=max(0.1, float(ears.get("pause_grace", 1.2))),
        ears_transcript_timeout=max(1.0, float(ears.get("transcript_timeout", 8))),
        ears_activity_timeout=max(2.0, float(ears.get("activity_timeout", 12))),
        turn_window=max(0.0, float(r.get("turn_window", 0.0))),
        brain_auth=auth,
        subscription_profile=str(m.get("subscription_profile", "default")),
        provider=provider,
        puppet_model=puppet,
        puppet_effort=m.get("puppet_effort", "none"),
        ruminate_model=m.get("ruminate", puppet),
        alt_model=m.get("alt", "gpt-5-mini" if provider == "openai" else "claude-haiku-4-5"),
        use_alt=bool(m.get("use_alt", False)),
        window=int(r.get("window", 24)),
        quiet_interval_with_visitor=float(r.get("quiet_interval_with_visitor", 8)),
        quiet_interval_alone=float(r.get("quiet_interval_alone", 120)),
        visitor_timeout=float(r.get("visitor_timeout", 75)),
        visitor_hard_timeout=float(r.get("visitor_hard_timeout", 300)),
        ruminate_every=int(mem.get("ruminate_every", 30)),
        bedtime_min_heard=int(mem.get("bedtime_min_heard", 8)),
        belief_capacity=int(mem.get("belief_capacity", 6)),
        unspoken_keep=int(mem.get("unspoken_keep", 8)),
        ears=ears.get("mode", "console"),
        ears_model=ears.get("model", "gpt-4o-transcribe"),
        ears_language=ears.get("language", language),
        ears_silence_ms=int(ears.get("silence_ms", 600)),
        ears_interrupt=ears.get("interrupt", "confirm"),
        ears_device=ears.get("device") or None,
        ears_min_chars=int(ears.get("min_chars", 2)),
        ears_vad_threshold=float(ears.get("vad_threshold", 0.7)),
        ears_gate_factor=float(ears.get("gate_factor", 3.0)),
        ears_gate_floor=float(ears.get("gate_floor", 400)),
        mouth=mouth.get("mode", "off"),
        mouth_model=mouth.get("model", "gpt-4o-mini-tts"),
        voices=dict(mouth.get("voices", {"Charlie": "nova", "Kaka": "onyx", "Lucy": "shimmer"})),
        pitch={k: float(v) for k, v in mouth.get("pitch", {"Charlie": 6, "Kaka": 6, "Lucy": 7}).items()},
        pan={k: (float(v[0]), float(v[1])) for k, v in
             mouth.get("pan", {"Charlie": [1.0, 0.0], "Kaka": [0.0, 1.0], "Lucy": [0.5, 0.5]}).items()},
        instructions=dict(catalog(language)["voices"]),
        motors=motors.get("mode", "off"),
        serial_port=motors.get("port", "/dev/cu.usbserial-1130"),
        serial_baud=int(motors.get("baud", 9600)),
        monitor_port=int(d.get("monitor", {}).get("port", 8765)),
        audio_io=d.get("audio", {}).get("io", "local"),
        presence_source=d.get("presence", {}).get("source", "none"),
        persona_dir=base / d.get("persona", {}).get("dir", "charactor_setting"),
        state_dir=base / d.get("state_dir", "state"),
    )


class LiveConfig:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._cfg: Config | None = None

    @property
    def current(self) -> Config:
        mtime = self.path.stat().st_mtime
        if self._cfg is None or mtime != self._mtime:
            self._cfg = parse_config(self.path.read_text(encoding="utf-8"), self.path.parent)
            self._mtime = mtime
        return self._cfg
