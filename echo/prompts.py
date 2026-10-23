"""All runtime prompt text is authored in the UTF-8 prompts.txt master file."""
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / 'prompts.txt'
NAMES = ('Charlie', 'Lucy', 'Kaka')
TEXT_KEYS = ('decide', 'compose', 'ruminate', 'impression', 'no_impression',
             'belief_heading', 'recent_heading', 'experience_heading',
             'context_heading', 'daily', 'end', 'bedtime', 'persona_template', 'performance')


def read_catalogs(path):
    """Parse named plain-text blocks; fail with the editable section on errors."""
    sections = {}
    current = None
    for number, line in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
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
        data = {key: take(key) for key in TEXT_KEYS}
        data['personas'] = {}
        data['voices'] = {}
        for name in NAMES:
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
            if len(beliefs) > 6:
                raise ValueError(f'{path}: [{language}.personas.{name}.initial_beliefs] exceeds 6 beliefs')
            role['initial_beliefs'] = beliefs
            data['personas'][name] = role
            data['voices'][name] = take(f'voices.{name}')
        try:
            data['persona_template'].format(**data['personas']['Charlie'])
            data['ruminate'].format(impression_ask=data['impression'], capacity=6)
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
def catalog(language="zh"):
    if language not in ("zh", "en"):
        raise ValueError("prompt language must be zh or en")
    return read_catalogs(PROMPT_FILE)[language]

def persona(name, language="zh"):
    data = catalog(language)
    return data["persona_template"].format(**data["personas"][name])


def trial_settings():
    return read_catalogs(PROMPT_FILE)['trial']

# Compatibility imports only; no shared decision instructions are attached to backgrounds.
NEUTRAL = ""
COMPOSE_ASK = catalog()["compose"]
RUMINATE_ASK = catalog()["ruminate"]
IMPRESSION_ASK = catalog()["impression"]
NO_IMPRESSION = catalog()["no_impression"]
SEED_ASK = ""  # Initialization uses reviewed beliefs, never model-generated biography.
