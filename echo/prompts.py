"""All runtime prompt text is authored in the UTF-8 prompts.txt master file."""
import re
from .settings import rule, active_configuration
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / 'prompts.txt'
TEXT_KEYS = ('opening', 'decide', 'compose_system', 'compose', 'ruminate', 'impression', 'no_impression',
             'belief_heading', 'recent_heading', 'experience_heading',
             'context_heading', 'daily', 'end', 'bedtime', 'persona_template', 'performance')


def read_catalogs(path, *, text=None):
    """Parse named plain-text blocks; fail with the editable section on errors."""
    sections = {}
    current = None
    text = Path(path).read_text(encoding='utf-8-sig') if text is None else text.lstrip('\ufeff')
    for number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r'\[([A-Za-z_][A-Za-z0-9_.]*)\]', line.strip())
        if match:
            current = match.group(1)
            if current in sections:
                raise ValueError(f'{path}:{number}: duplicate section [{current}]')
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
        elif line.strip() and not line.lstrip().startswith('#'):
            raise ValueError(f'{path}:{number}: text must follow a [section]')
    result = {}
    expected = set()
    for language in ('zh', 'en'):
        def take(key, empty=False):
            section = f'{language}.{key}'
            expected.add(section)
            if section not in sections:
                raise ValueError(f'{path}: missing section [{section}]')
            body = '\n'.join(sections[section]).strip()
            if not body and not empty:
                raise ValueError(f'{path}: empty section [{section}]')
            return body
        data = {key: take(key, empty=key == 'compose') for key in TEXT_KEYS}
        data['personas'] = {}
        data['voices'] = {}
        for name in rule('characters.names'):
            role = {key: take(f'personas.{name}.{key}', empty=key == 'history')
                    for key in ('identity', 'history', 'strategy', 'environment')}
            raw = take(f'personas.{name}.initial_beliefs')
            beliefs = []
            for line in raw.splitlines():
                if not line.strip():
                    continue
                if not line.startswith('- ') or not line[2:].strip():
                    raise ValueError(f'{path}: [{language}.personas.{name}.initial_beliefs] '
                                     'must contain one belief per line starting with "- "')
                beliefs.append(line[2:].strip())
            if len(beliefs) > rule("validation.maximum_initial_beliefs"):
                raise ValueError(f'{path}: [{language}.personas.{name}.initial_beliefs] exceeds the rules.toml initial-belief limit')
            role['initial_beliefs'] = beliefs
            data['personas'][name] = role
            data['voices'][name] = take(f'voices.{name}')
        try:
            data['persona_template'].format(**data['personas']['Charlie'])
            data['ruminate'].format(impression_ask=data['impression'], capacity=rule('validation.maximum_initial_beliefs'))
        except (KeyError, ValueError, IndexError) as error:
            raise ValueError(f'{path}: invalid placeholder in [{language}.persona_template] '
                             f'or [{language}.ruminate]: {error}') from error
        result[language] = data
    trial = {}
    for key in ('history', 'a_boundary', 'questions'):
        section = f'trial.{key}'
        expected.add(section)
        if section not in sections:
            raise ValueError(f'{path}: missing section [{section}]')
        trial[key] = '\n'.join(sections[section]).strip()
    trial['questions'] = [line.removeprefix('- ').strip()
                          for line in trial['questions'].splitlines() if line.strip()]
    result['trial'] = trial
    unknown = set(sections) - expected
    if unknown:
        raise ValueError(f'{path}: unknown sections: {", ".join(sorted(unknown))}')
    return result

@lru_cache(maxsize=2)
def _catalog(language="zh"):
    if language not in ("zh", "en"):
        raise ValueError("prompt language must be zh or en")
    return read_catalogs(PROMPT_FILE)[language]

def catalog(language="zh"):
    if language not in ('zh', 'en'):
        raise ValueError('prompt language must be zh or en')
    snapshot = active_configuration()
    return snapshot.catalogs[language] if snapshot and snapshot.catalogs else _catalog(language)


catalog.cache_clear = _catalog.cache_clear


def persona(name, language="zh"):
    data = catalog(language)
    return data["persona_template"].format(**data["personas"][name])


def trial_settings():
    snapshot = active_configuration()
    return snapshot.catalogs['trial'] if snapshot and snapshot.catalogs else read_catalogs(PROMPT_FILE)['trial']

# Compatibility imports only; no shared decision instructions are attached to backgrounds.
NEUTRAL = ""
SEED_ASK = ""  # Initialization uses reviewed beliefs, never model-generated biography.


def __getattr__(name):
    # Legacy exports remain available without reading files at module import.
    keys = {'COMPOSE_ASK': 'compose', 'RUMINATE_ASK': 'ruminate',
            'IMPRESSION_ASK': 'impression', 'NO_IMPRESSION': 'no_impression'}
    if name == 'NAMES':
        return tuple(rule('characters.names'))
    if name in keys:
        return catalog()[keys[name]]
    raise AttributeError(name)
