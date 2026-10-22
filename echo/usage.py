"""Per-process reported brain token usage. No prompts, credentials or cost guesses."""
from copy import deepcopy

def _get(value, key, default=None):
    return value.get(key, default) if isinstance(value, dict) else getattr(value, key, default)

def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None

class TokenUsage:
    def __init__(self):
        self.reports = 0
        self.missing = 0
        self.totals = {}
        self.recent = []

    def record(self, usage, model, task):
        incoming = _count(_get(usage, 'input_tokens'))
        outgoing = _count(_get(usage, 'output_tokens'))
        if incoming is None or outgoing is None:
            self.missing += 1
            return
        values = {'input': incoming, 'output': outgoing,
                  'total': _count(_get(usage, 'total_tokens')),
                  'cached': _count(_get(_get(usage, 'input_tokens_details'), 'cached_tokens')),
                  'reasoning': _count(_get(_get(usage, 'output_tokens_details'), 'reasoning_tokens'))}
        if values['total'] is None:
            values['total'] = incoming + outgoing
        self.reports += 1
        for key, value in values.items():
            if value is not None:
                self.totals[key] = self.totals.get(key, 0) + value
        self.recent.append({'model': model, 'task': task, **values})
        del self.recent[:-8]

    def snapshot(self):
        return deepcopy({'reports': self.reports, 'missing': self.missing,
                         'totals': self.totals, 'recent': self.recent})

def record_usage(brain, usage, model, task):
    if not hasattr(brain, 'token_usage'):
        brain.token_usage = TokenUsage()
    brain.token_usage.record(usage, model, task)
