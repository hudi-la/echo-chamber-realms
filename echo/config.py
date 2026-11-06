"""Resolve a launch profile from parameters.toml; runtime state never writes configuration."""
import tomllib
from .settings import config_data, parameters, rule, freeze, active_configuration
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
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

    prompt_language: str = field(default_factory=lambda: parameters()["defaults"]["prompts"]["language"])
    brain_auth: str = field(default_factory=lambda: parameters()["defaults"]["model"]["auth"])
    subscription_profile: str = field(default_factory=lambda: parameters()["defaults"]["model"]["subscription_profile"])
    ears_pause_grace: float = field(default_factory=lambda: parameters()["defaults"]["ears"]["pause_grace"])
    ears_transcript_timeout: float = field(default_factory=lambda: parameters()["defaults"]["ears"]["transcript_timeout"])
    ears_activity_timeout: float = field(default_factory=lambda: parameters()["defaults"]["ears"]["activity_timeout"])
    turn_window: float = field(default_factory=lambda: parameters()["defaults"]["room"]["turn_window"])
    mouth_speed: float = field(default_factory=lambda: parameters()["defaults"]["mouth"]["playback_speed"])
    reset_on_start: bool = field(default_factory=lambda: parameters()["defaults"]["memory"]["reset_on_start"])

    def __post_init__(self):
        for name in ('voices', 'pitch', 'pan', 'instructions'):
            object.__setattr__(self, name, freeze(getattr(self, name)))

    @property
    def model(self) -> str:
        return self.alt_model if self.use_alt else self.puppet_model


def parse_config(text: str, base: Path) -> Config:
    d = config_data(tomllib.loads(text))
    m, r, mem = d["model"], d["room"], d["memory"]
    ears, mouth, motors = d["ears"], d["mouth"], d["motors"]
    provider, auth = m["provider"], m["auth"]
    if auth not in ("api", "subscription") or (auth == "subscription" and provider != "openai"):
        raise ValueError("model.auth must be api, or subscription with provider=openai")
    language = d["prompts"]["language"]
    if language not in ("zh", "en"):
        raise ValueError("prompts.language must be zh or en")
    import math
    speed = float(mouth["playback_speed"])
    low, high = rule('validation.minimum_playback_speed'), rule('validation.maximum_playback_speed')
    if not math.isfinite(speed) or not low <= speed <= high:
        raise ValueError(f"mouth.playback_speed must be between {low} and {high}")
    from .prompts import catalog
    return Config(
        mouth_speed=speed,
        reset_on_start=bool(mem["reset_on_start"]),
        prompt_language=language,
        ears_pause_grace=max(rule('validation.minimum_pause_grace'), float(ears["pause_grace"])),
        ears_transcript_timeout=max(rule('validation.minimum_transcript_timeout'), float(ears["transcript_timeout"])),
        ears_activity_timeout=max(rule('validation.minimum_activity_timeout'), float(ears["activity_timeout"])),
        turn_window=max(0.0, float(r["turn_window"])),
        brain_auth=auth,
        subscription_profile=str(m["subscription_profile"]),
        provider=provider,
        puppet_model=m["puppet"],
        puppet_effort=m["puppet_effort"],
        ruminate_model=m["ruminate"],
        alt_model=m["alt"],
        use_alt=bool(m["use_alt"]),
        window=int(r["window"]),
        quiet_interval_with_visitor=float(r["quiet_interval_with_visitor"]),
        quiet_interval_alone=float(r["quiet_interval_alone"]),
        visitor_timeout=float(r["visitor_timeout"]),
        visitor_hard_timeout=float(r["visitor_hard_timeout"]),
        ruminate_every=int(mem["ruminate_every"]),
        bedtime_min_heard=int(mem["bedtime_min_heard"]),
        belief_capacity=int(mem["belief_capacity"]),
        unspoken_keep=int(mem["unspoken_keep"]),
        ears=ears["mode"],
        ears_model=ears["model"],
        ears_language=ears["language"],
        ears_silence_ms=int(ears["silence_ms"]),
        ears_interrupt=ears["interrupt"],
        ears_device=ears["device"] or None,
        ears_min_chars=int(ears["min_chars"]),
        ears_vad_threshold=float(ears["vad_threshold"]),
        ears_gate_factor=float(ears["gate_factor"]),
        ears_gate_floor=float(ears["gate_floor"]),
        mouth=mouth["mode"],
        mouth_model=mouth["model"],
        voices=dict(mouth["voices"]),
        pitch={k: float(v) for k, v in mouth["pitch"].items()},
        pan={k: (float(v[0]), float(v[1])) for k, v in mouth["pan"].items()},
        instructions=dict(catalog(language)["voices"]),
        motors=motors["mode"],
        serial_port=motors["port"],
        serial_baud=int(motors["baud"]),
        monitor_port=int(d["monitor"]["port"]),
        audio_io=d["audio"]["io"],
        presence_source=d["presence"]["source"],
        persona_dir=base / d["persona"]["dir"],
        state_dir=base / d["state_dir"],
    )


class LiveConfig:
    """Legacy API name; reads once per instance and never hot-reloads."""
    def __init__(self, path: Path) -> None:
        self.path = path
        self._cfg: Config | None = None

    @property
    def current(self) -> Config:
        snapshot = active_configuration()
        if snapshot is not None and snapshot.config is not None:
            return snapshot.config
        # Compatibility name: this loader now retains its first immutable value.
        if self._cfg is None:
            self._cfg = parse_config(self.path.read_text(encoding="utf-8"), self.path.parent)
        return self._cfg
