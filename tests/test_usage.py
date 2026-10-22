from types import SimpleNamespace as NS
from echo.usage import TokenUsage
from echo.brain import SubscriptionBrain
from tests.test_subscription import FakeStream, Client, FakeSession


def test_usage_subsets_are_not_double_counted_and_snapshots_are_isolated():
    usage = TokenUsage()
    data = {'input_tokens': 100, 'output_tokens': 30, 'total_tokens': 130,
            'input_tokens_details': {'cached_tokens': 80},
            'output_tokens_details': {'reasoning_tokens': 20}}
    usage.record(data, 'model', 'line')
    snapshot = usage.snapshot()
    assert snapshot['totals'] == {'input': 100, 'output': 30, 'total': 130, 'cached': 80, 'reasoning': 20}
    snapshot['totals']['total'] = -1
    assert usage.snapshot()['totals']['total'] == 130


def test_missing_usage_and_optional_details_remain_unknown():
    usage = TokenUsage()
    usage.record(None, 'model', 'line')
    assert usage.snapshot() == {'reports': 0, 'missing': 1, 'totals': {}, 'recent': []}
    usage.record(NS(input_tokens=10, output_tokens=2), 'model', 'rumination')
    result = usage.snapshot()
    assert result['totals'] == {'input': 10, 'output': 2, 'total': 12}
    assert result['recent'][0]['cached'] is None
    assert result['recent'][0]['reasoning'] is None


def test_recent_usage_is_bounded_but_totals_keep_accumulating():
    usage = TokenUsage()
    for _ in range(12):
        usage.record(NS(input_tokens=10, output_tokens=2), 'model', 'line')
    assert len(usage.recent) == 8
    assert usage.snapshot()['reports'] == 12
    assert usage.snapshot()['totals']['total'] == 144


async def test_subscription_completion_records_report_once_with_streamed_text():
    response = NS(usage=NS(input_tokens=40, output_tokens=9, total_tokens=49))
    stream = FakeStream([NS(type='response.output_text.delta', delta='{"text":"你好"}'),
                         NS(type='response.completed', response=response)])
    client = Client(stream)
    brain = SubscriptionBrain('gpt-6.1-sol', effort='low', session=FakeSession(), client_factory=lambda _: client)
    assert await brain.compose('role', 'scene', None) == '你好'
    result = brain.token_usage.snapshot()
    assert result['reports'] == 1 and result['totals']['total'] == 49
    assert result['recent'][0]['task'] == 'line'
