"""Read-only control tables. Runtime state must never write these source files."""
from copy import deepcopy
from functools import lru_cache
import math
from pathlib import Path
import tomllib
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, fields, is_dataclass, replace
from types import MappingProxyType


def freeze(value):
    """Recursively freeze configuration; runtime memory is deliberately separate."""
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    return value


def plain(value):
    if is_dataclass(value):
        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    return value


@dataclass(frozen=True)
class RunConfiguration:
    parameters: Mapping
    rules: Mapping
    sources: Mapping
    overrides: Mapping
    catalogs: Mapping | None = None
    config: object = None


_ACTIVE = ContextVar('echo_run_configuration', default=None)


def active_configuration():
    return _ACTIVE.get()


@contextmanager
def runtime_configuration(config_path, prompt_file=None):
    """Read each input once, validate, then bind one immutable snapshot to the run.

    Async tasks inherit this context. No runtime accessor checks source files.
    """
    import hashlib
    import os
    from . import prompts
    from .config import parse_config
    config_path = Path(config_path)
    prompt_file = Path(prompt_file) if prompt_file else prompts.PROMPT_FILE
    inputs = (PARAMETERS_FILE, RULES_FILE, prompt_file, config_path)
    contents = [path.read_text(encoding='utf-8') for path in inputs]
    sources = {path.name: {'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest()}
               for path, content in zip(inputs, contents)}
    snapshot = RunConfiguration(
        freeze(tomllib.loads(contents[0])), freeze(tomllib.loads(contents[1])),
        freeze(sources), freeze({key: os.environ[key] for key in
                                ('ECR_SERIAL_PORT', 'ECR_RELAY_ACTIVE') if key in os.environ}))
    token = _ACTIVE.set(snapshot)
    try:
        validate_controls()
        catalogs = freeze(prompts.read_catalogs(prompt_file, text=contents[2]))
        snapshot = replace(snapshot, catalogs=catalogs)
        _ACTIVE.set(snapshot)
        config = parse_config(contents[3], config_path.parent)
        validate_run_config(config)
        snapshot = replace(snapshot, config=config)
        _ACTIVE.set(snapshot)
        yield snapshot
    finally:
        _ACTIVE.reset(token)


ROOT = Path(__file__).resolve().parent.parent
PARAMETERS_FILE = ROOT / 'parameters.toml'
RULES_FILE = ROOT / 'rules.toml'

@lru_cache(maxsize=8)
def _read(path, mtime, size):
    return tomllib.loads(Path(path).read_text(encoding='utf-8'))

def table(path):
    path = Path(path)
    stat = path.stat()
    return deepcopy(_read(str(path), stat.st_mtime_ns, stat.st_size))

def parameters():
    snapshot = active_configuration()
    return snapshot.parameters if snapshot else table(PARAMETERS_FILE)

def rules():
    snapshot = active_configuration()
    data = snapshot.rules if snapshot else table(RULES_FILE)
    if data['conversation']['selection'] not in ('random', 'first'):
        raise ValueError('rules.toml: conversation.selection must be random or first')
    names = data['characters']['names']
    if set(names) != {'Charlie', 'Lucy', 'Kaka'} or len(names) != 3:
        raise ValueError('rules.toml: character identities must match the implemented three puppets')
    order = data['characters']['stage_left_to_right']
    if sorted(order) != sorted(names):
        raise ValueError('rules.toml: stage order must contain each character exactly once')
    return data

def _value(data, path):
    for part in path.split('.'):
        data = data[part]
    return data

def parameter(path):
    value = _value(parameters()['system'], path)
    if isinstance(value, (int, float)) and (not math.isfinite(value) or value < 0):
        raise ValueError(f'parameters.toml: system.{path} must be finite and nonnegative')
    return value

def rule(path):
    return _value(rules(), path)

def merge_settings(base, override):
    """Tables merge, while scalar/list values replace; character maps replace as a unit."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict) and key not in ('voices','pitch','pan'):
            result[key] = merge_settings(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result

def config_data(overrides):
    master = plain(parameters())
    profile = overrides.get('profile')
    if profile is not None and profile not in master['profiles']:
        raise ValueError(f'Unknown parameters.toml profile: {profile}')
    def resolve(name, seen=()):
        if name in seen:
            raise ValueError('parameters.toml: circular profile inheritance')
        if name not in master['profiles']:
            raise ValueError(f'Unknown parameters.toml profile: {name}')
        entry = deepcopy(master['profiles'][name])
        parent = entry.pop('extends', None)
        return merge_settings(resolve(parent, (*seen, name)), entry) if parent else entry
    selected = merge_settings(resolve(profile), overrides) if profile else deepcopy(overrides)
    provider = selected.get('model', {}).get('provider', master['defaults']['model']['provider'])
    if provider not in master['providers']:
        raise ValueError(f'Unknown model provider: {provider}')
    data = merge_settings(master['defaults'], selected)
    for key, value in master['providers'][provider].items():
        if key not in selected.get('model', {}):
            data['model'][key] = value
    if 'ruminate' not in selected.get('model', {}):
        data['model']['ruminate'] = data['model']['puppet']
    if 'language' not in selected.get('ears', {}):
        data['ears']['language'] = data['prompts']['language']
    return data

def validate_controls():
    """Reject unusable control values before starting model/audio/hardware services."""
    data = plain(parameters()['system'])
    def walk(node, prefix=''):
        for key, value in node.items():
            path = f'{prefix}.{key}' if prefix else key
            if isinstance(value, dict):
                walk(value, path)
            elif isinstance(value, (int, float)) and (not math.isfinite(value) or value < 0):
                raise ValueError(f'parameters.toml: system.{path} must be finite and nonnegative')
    walk(data)
    if not 0 <= data['eyes']['blink_probability'] <= 1:
        raise ValueError('parameters.toml: eyes.blink_probability must be between 0 and 1')
    if not 0 < data['eyes']['wait_min_seconds'] <= data['eyes']['wait_max_seconds']:
        raise ValueError('parameters.toml: invalid eye wait range')
    lease, renew = data['body']['lease_ms'], data['body']['renew_seconds']
    # ECR2 firmware accepts at most 1200ms. This is a protocol bound, not a preference.
    if not isinstance(lease, int) or not 0 < lease <= 1200 or not 0 < renew < lease / 1000:
        raise ValueError('parameters.toml: body lease must be 1..1200ms, with renewal earlier than expiry')
    for path in ('room.tick_seconds', 'speech.playback_poll_seconds', 'serial.heartbeat_seconds',
                 'model.compose_timeout', 'model.subscription_timeout', 'speech.tts_timeout'):
        if _value(data, path) <= 0:
            raise ValueError(f'parameters.toml: system.{path} must be positive')
    policy = rules()
    if set(policy['hardware_ids']) != set(policy['characters']['names']) or sorted(policy['hardware_ids'].values()) != [0, 1, 2]:
        raise ValueError('rules.toml: hardware_ids must map the three characters to 0, 1, 2')
    names = set(policy['characters']['names'])
    if set(policy['aliases']) != names or any(not values or any(not isinstance(v, str) or not v for v in values) for values in policy['aliases'].values()):
        raise ValueError('rules.toml: aliases must define nonempty names for each character')
    tones = policy['performance']['tones']
    if not tones or len(set(tones)) != len(tones) or any(not isinstance(t, str) or not t for t in tones):
        raise ValueError('rules.toml: performance.tones must contain unique nonempty strings')
    if not set(policy['performance']['smooth_tones']) <= set(tones):
        raise ValueError('rules.toml: smooth_tones must be included in tones')
    audience = policy['performance']['audience_target']
    if not isinstance(audience, str) or not audience or audience in names:
        raise ValueError('rules.toml: audience_target must be distinct from characters')
    for path in ('monitor.history_entries', 'serial.read_chunk_bytes', 'serial.buffer_limit_bytes',
                 'ears.max_upload_queue_chunks', 'model.subscription_max_reply_chars'):
        value = _value(data, path)
        if type(value) is not int or value <= 0:
            raise ValueError(f'parameters.toml: system.{path} must be a positive integer')
    for section, keys in {
        'conversation': ('prefer_named_character', 'avoid_repeat_speaker', 'ignore_own_speech_event'),
        'memory': ('reflection_enabled', 'allow_belief_changes', 'require_change_reason', 'save_companion_observations', 'save_visitor_impressions'),
        'performance': ('body_during_speech', 'move_eyes', 'avert_and_return'),
    }.items():
        for key in keys:
            if not isinstance(policy[section][key], bool):
                raise ValueError(f'rules.toml: {section}.{key} must be true or false')


def validate_run_config(config):
    """Validate the resolved values before any state, model, audio or hardware I/O."""
    positive = ('window', 'ruminate_every', 'belief_capacity', 'unspoken_keep',
                'quiet_interval_with_visitor', 'quiet_interval_alone', 'visitor_timeout',
                'visitor_hard_timeout', 'ears_silence_ms', 'ears_min_chars',
                'ears_gate_factor', 'serial_baud')
    nonnegative = ('bedtime_min_heard', 'ears_gate_floor', 'turn_window')
    for name in (*positive, *nonnegative):
        value = getattr(config, name)
        if not math.isfinite(value) or value < 0 or (name in positive and value == 0):
            raise ValueError(f'configuration: {name} must be finite and {"positive" if name in positive else "nonnegative"}')
    if not 0 <= config.ears_vad_threshold <= 1:
        raise ValueError('configuration: ears_vad_threshold must be between 0 and 1')
    if not 0 <= config.monitor_port <= 65535:
        raise ValueError('configuration: monitor_port must be 0..65535')
    for name, options in {'ears': ('console', 'realtime'), 'mouth': ('off', 'tts'),
                          'motors': ('off', 'serial'), 'audio_io': ('local', 'browser'),
                          'ears_interrupt': ('confirm', 'immediate'), 'presence_source': ('none',)}.items():
        if getattr(config, name) not in options:
            raise ValueError(f'configuration: unsupported {name}: {getattr(config, name)!r}')
    names = set(rule('characters.names'))
    for name in ('voices', 'pitch', 'pan', 'instructions'):
        if set(getattr(config, name)) != names:
            raise ValueError(f'configuration: {name} must define every character')
    if any(not math.isfinite(value) for value in config.pitch.values()):
        raise ValueError('configuration: pitch must be finite')
    if any(not math.isfinite(value) or not 0 <= value <= 1 for pair in config.pan.values() for value in pair):
        raise ValueError('configuration: pan volume must be between 0 and 1')
    relay = active_configuration().overrides.get('ECR_RELAY_ACTIVE', parameter('serial.relay_active'))
    if relay not in ('', 'HIGH', 'LOW'):
        raise ValueError('configuration: serial relay_active must be empty, HIGH or LOW')


def capture_run_configuration(state_dir, config, prompt_file=None):
    """Write a record beside runtime data; never overwrite a source control table."""
    from datetime import datetime, timezone
    import hashlib
    import json
    import os
    import uuid
    path = Path(state_dir) / 'runs' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
    path.mkdir(parents=True, exist_ok=False)
    prompt_file = Path(prompt_file) if prompt_file else ROOT / 'prompts.txt'
    snapshot = active_configuration()
    sources = plain(snapshot.sources) if snapshot else {}
    if not snapshot:
        for source in (PARAMETERS_FILE, RULES_FILE, prompt_file):
            contents = source.read_text(encoding='utf-8')
            sources[source.name] = {'sha256': hashlib.sha256(contents.encode()).hexdigest(), 'content': contents}
    record = {
        'effective_config': plain(config), 'sources': sources,
        'startup_overrides': plain(snapshot.overrides) if snapshot else {key: os.environ[key] for key in ('ECR_SERIAL_PORT', 'ECR_RELAY_ACTIVE') if key in os.environ},
    }
    (path / 'configuration.json').write_text(json.dumps(record, default=str, ensure_ascii=False, indent=2) + '\n')
    return path
