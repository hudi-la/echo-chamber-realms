from echo.brain import Change, Rumination
from echo.memory import PuppetMemory, ChangeLog
from tests.test_puppet import build
from tests.fakes import FakeBrain
from echo.clock import FakeClock


async def test_reflection_is_never_called_when_disabled(tmp_path):
    brain = FakeBrain(rumination=Rumination([], ''))
    _, puppets, *_ = build(FakeClock(), tmp_path, [('Lucy', brain)])
    p = puppets['Lucy']
    p.memory.note_heard('now', {'at': 'now', 'who': '新朋友', 'text': '你好', 'cut': False})
    await p.ruminate('visit')
    assert not await p.ruminate_if_pending()
    assert brain.ruminations == []


def test_disabled_belief_changes_cannot_modify_saved_beliefs(tmp_path):
    memory = PuppetMemory('Lucy', tmp_path / 'lucy.json')
    memory.beliefs = ['原来的信念']
    accepted = memory.apply_changes([Change('belief', '', '原来的信念', '新信念', '一次聊天')], '', None,
                                    'now', 6, ChangeLog(tmp_path / 'changes.jsonl'))
    assert accepted == []
    assert memory.beliefs == ['原来的信念']
