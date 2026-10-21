"""Runtime prompts and reviewed bilingual documentation share prompts/{zh,en}.json."""
import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

@lru_cache(maxsize=2)
def catalog(language="zh"):
    if language not in ("zh", "en"):
        raise ValueError("prompt language must be zh or en")
    return json.loads((ROOT / "prompts" / f"{language}.json").read_text(encoding="utf-8"))

def persona(name, language="zh"):
    data = catalog(language)
    return data["persona_template"].format(**data["personas"][name])

# Compatibility imports only; no shared decision instructions are attached to backgrounds.
NEUTRAL = ""
COMPOSE_ASK = catalog()["compose"]
RUMINATE_ASK = catalog()["ruminate"]
IMPRESSION_ASK = catalog()["impression"]
NO_IMPRESSION = catalog()["no_impression"]
SEED_ASK = ""  # Initialization uses reviewed beliefs, never model-generated biography.
