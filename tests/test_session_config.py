import os
from pathlib import Path

from echo.config import LiveConfig, parse_config
from echo.session import VisitorTracker

MINIMAL = """
[model]
puppet = "claude-opus-5"
[room]
quiet_interval_alone = 120
"""


def test_visitor_tracker_counts_only_true_silence():
    v = VisitorTracker()
    assert v.saw_human(10.0, "w10") is True
    assert v.present and v.session_id == "w10"
    assert v.saw_human(20.0, "w20") is False
    # 木偶说了 100 秒：钟不走
    for _ in range(100):
        v.tick(1.0, room_silent=False)
    assert v.check_left(120.0, timeout=75, hard_timeout=300) is None
    # 然后真正安静 74 秒：还没到
    for _ in range(74):
        v.tick(1.0, room_silent=True)
    assert v.check_left(194.0, timeout=75, hard_timeout=300) is None
    v.tick(1.0, room_silent=True)
    assert v.check_left(195.0, timeout=75, hard_timeout=300) == "w10"
    assert not v.present and v.session_id is None and v.silence == 0.0
    assert v.saw_human(200.0, "w200") is True


def test_visitor_tracker_hard_timeout_even_if_puppets_never_stop():
    v = VisitorTracker()
    v.saw_human(0.0, "w0")
    for _ in range(299):
        v.tick(1.0, room_silent=False)
    assert v.check_left(299.0, timeout=75, hard_timeout=300) is None
    assert v.check_left(300.0, timeout=75, hard_timeout=300) == "w0"


def test_human_speech_resets_silence_clock():
    v = VisitorTracker()
    v.saw_human(0.0, "w0")
    for _ in range(70):
        v.tick(1.0, room_silent=True)
    v.saw_human(70.0, "w70")
    assert v.silence == 0.0
    for _ in range(10):
        v.tick(1.0, room_silent=True)
    assert v.check_left(80.0, timeout=75, hard_timeout=300) is None


def test_parse_config_defaults_and_overrides(tmp_path):
    c = parse_config(MINIMAL, base=tmp_path)
    assert c.puppet_model == "claude-opus-5"
    assert c.puppet_effort == "none"
    assert c.quiet_interval_alone == 120
    assert c.quiet_interval_with_visitor == 8
    assert c.visitor_timeout == 75
    assert c.visitor_hard_timeout == 300
    assert c.window == 24
    assert c.ruminate_every == 30 and c.bedtime_min_heard == 8
    assert c.belief_capacity == 6
    assert c.unspoken_keep == 8
    assert c.ears == "console" and c.mouth == "off" and c.motors == "off"
    assert c.state_dir == tmp_path / "state"
    assert c.model == "claude-opus-5"


def test_use_alt_switches_model(tmp_path):
    c = parse_config('[model]\npuppet = "claude-opus-5"\nalt = "claude-haiku-4-5"\nuse_alt = true\n', base=tmp_path)
    assert c.model == "claude-haiku-4-5"


def test_config_loader_keeps_first_value_until_new_instance(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(MINIMAL, encoding="utf-8")
    live = LiveConfig(p)
    assert live.current.quiet_interval_alone == 120
    p.write_text(MINIMAL.replace("120", "30"), encoding="utf-8")
    os.utime(p, (p.stat().st_atime, p.stat().st_mtime + 5))
    assert live.current.quiet_interval_alone == 120
    assert LiveConfig(p).current.quiet_interval_alone == 30


def test_provider_defaults(tmp_path):
    c = parse_config("", base=tmp_path)
    assert c.provider == "anthropic" and c.model == "claude-opus-5"
    c = parse_config('[model]\nprovider = "openai"\n', base=tmp_path)
    assert c.provider == "openai" and c.model == "gpt-5.5" and c.alt_model == "gpt-5-mini"


def test_mouth_config_defaults_and_tables(tmp_path):
    c = parse_config("", base=tmp_path)
    assert c.mouth_model == "gpt-4o-mini-tts"
    assert c.voices == {"Charlie": "nova", "Kaka": "onyx", "Lucy": "shimmer"}
    assert c.pitch["Lucy"] == 7.0 and c.pan["Charlie"] == (1.0, 0.0) and "普通话" in c.instructions["Lucy"]
    c = parse_config('[mouth]\nmode="tts"\n[mouth.pan]\nLucy=[0.3,0.7]\n[mouth.instructions]\nLucy="小老鼠"\n', base=tmp_path)
    assert c.mouth == "tts" and c.pan == {"Lucy": (0.3, 0.7)} and "普通话" in c.instructions["Lucy"]


def test_monitor_port(tmp_path):
    assert parse_config("", base=tmp_path).monitor_port == 8765
    assert parse_config("[monitor]\nport = 0\n", base=tmp_path).monitor_port == 0


def test_presence_source_default(tmp_path):
    assert parse_config("", base=tmp_path).presence_source == "none"
    assert parse_config('[presence]\nsource = "mat"\n', base=tmp_path).presence_source == "mat"


def test_ears_config_defaults(tmp_path):
    c = parse_config("", base=tmp_path)
    assert c.ears == "console" and c.ears_model == "gpt-4o-transcribe" and c.ears_language == "zh"
    assert c.ears_silence_ms == 600 and c.ears_interrupt == "confirm" and c.ears_device is None
    c = parse_config('[ears]\nmode="realtime"\ninterrupt="confirm"\ndevice="USB Mic"\nsilence_ms=900\n', base=tmp_path)
    assert c.ears == "realtime" and c.ears_interrupt == "confirm" and c.ears_device == "USB Mic" and c.ears_silence_ms == 900


def test_ears_gate_config(tmp_path):
    c = parse_config("", base=tmp_path)
    assert c.ears_min_chars == 2 and c.ears_vad_threshold == 0.7 and c.ears_gate_factor == 3.0 and c.ears_gate_floor == 400


def test_audio_io_config(tmp_path):
    assert parse_config("", base=tmp_path).audio_io == "local"
    assert parse_config('[audio]\nio = "browser"\n', base=tmp_path).audio_io == "browser"


def test_persona_dir(tmp_path):
    assert parse_config("", base=tmp_path).persona_dir == tmp_path / "charactor_setting"
    assert parse_config('[persona]\ndir = "charactor_setting/v2"\n', base=tmp_path).persona_dir == tmp_path / "charactor_setting/v2"
