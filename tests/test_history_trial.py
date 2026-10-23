import json

from echo.brain import PerformedLine
from echo.history_trial import conversation, trial_system
from echo.prompts import ROOT, catalog


def test_trial_keeps_original_beliefs_and_does_not_mutate_catalog():
    variant = json.loads((ROOT / 'experiments/history-a/variant.json').read_text())
    original = json.dumps(catalog('zh'), ensure_ascii=False)
    system = trial_system('Charlie', variant)
    assert variant['history'] in system
    assert variant['environment_append'] in system
    for belief in catalog('zh')['personas']['Charlie']['initial_beliefs']:
        assert belief in system
    assert json.dumps(catalog('zh'), ensure_ascii=False) == original


async def test_repetitions_keep_continuity_within_but_not_between_conversations():
    class Brain:
        def __init__(self):
            self.inputs = []

        async def compose(self, system, situation, decision):
            self.inputs.append(situation)
            return PerformedLine('ONLY_GENERATED_REPLY')

    brain = Brain()
    await conversation(brain, 'Charlie', 'SYSTEM', ['FIRST', 'SECOND'], 24)
    await conversation(brain, 'Charlie', 'SYSTEM', ['FRESH'], 24)
    assert 'ONLY_GENERATED_REPLY' in brain.inputs[1]
    assert 'FIRST' in brain.inputs[1]
    assert 'ONLY_GENERATED_REPLY' not in brain.inputs[2]
    assert 'FIRST' not in brain.inputs[2]
