import pytest

from echo import prompts
from echo.brain import Decision, OpenAIBrain
from tests.test_brain import _StubOpenAI


def test_master_supplies_both_runtime_languages():
    parsed = prompts.read_catalogs(prompts.PROMPT_FILE)
    for language in ('zh', 'en'):
        assert set(parsed[language]['personas']) == set(prompts.NAMES)
        assert set(parsed[language]['voices']) == set(prompts.NAMES)
        assert parsed[language]['performance']


@pytest.mark.parametrize('operation, expected', [
    ('duplicate', 'duplicate section'),
    ('missing', 'missing section'),
    ('typo', 'unknown sections'),
    ('placeholder', 'invalid placeholder'),
])
def test_editor_errors_report_the_problem(tmp_path, operation, expected):
    text = prompts.PROMPT_FILE.read_text()
    if operation == 'duplicate':
        text += '\n[zh.compose]\nDuplicate\n'
    elif operation == 'missing':
        text = text.replace('[zh.compose]', '[zh.misspelled_compose]')
    elif operation == 'typo':
        text += '\n[zh.typo]\nUnknown\n'
    else:
        text = text.replace('{identity}', '{identitty}')
    path = tmp_path / 'prompts.txt'
    path.write_text(text)
    with pytest.raises(ValueError, match=expected):
        prompts.read_catalogs(path)


async def test_edited_master_supplies_persona_tasks_beliefs_and_voice(tmp_path, monkeypatch):
    text = prompts.PROMPT_FILE.read_text()
    original = prompts.catalog('zh')
    text = text.replace('[zh.personas.Lucy.history]\n', '[zh.personas.Lucy.history]\nEDITED_HISTORY\n')
    text = text.replace(original['compose'], 'EDITED_COMPOSE', 1)
    text = text.replace(original['performance'], 'EDITED_PERFORMANCE', 1)
    text = text.replace(original['voices']['Lucy'], 'EDITED_VOICE', 1)
    text = text.replace(original['personas']['Lucy']['initial_beliefs'][0], 'EDITED_BELIEF', 1)
    path = tmp_path / 'prompts.txt'
    path.write_text(text)
    monkeypatch.setattr(prompts, 'PROMPT_FILE', path)
    prompts.catalog.cache_clear()
    try:
        assert 'EDITED_HISTORY' in prompts.persona('Lucy')
        assert prompts.catalog()['personas']['Lucy']['initial_beliefs'][0] == 'EDITED_BELIEF'
        from echo.config import parse_config
        assert parse_config('', tmp_path).instructions['Lucy'] == 'EDITED_VOICE'
        stub = _StubOpenAI('{"text":"Hello."}')
        brain = OpenAIBrain('test', client=stub)
        await brain.compose(prompts.persona('Lucy'), 'SCENE', Decision(True))
        call = stub.responses.calls[-1]
        assert 'EDITED_HISTORY' in call['instructions']
        assert 'EDITED_COMPOSE' in call['input']
        assert 'EDITED_PERFORMANCE' in call['input']
    finally:
        prompts.catalog.cache_clear()
