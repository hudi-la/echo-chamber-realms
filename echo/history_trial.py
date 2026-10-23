"""Isolated, text-only prompt trial using the production compose and transcript paths.

python -m echo.history_trial --output work/history-a-results.json
No microphone, speech synthesis, motors, reflection, or exhibition memory writes.
"""
import argparse
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

from .brain import Decision, make_brain
from .config import parse_config
from .prompts import ROOT, catalog, trial_settings
from .transcript import Transcript


def trial_system(name, variant, data=None):
    data = catalog('zh') if data is None else data
    character = deepcopy(data['personas'][name])
    character['history'] = variant['history']
    character['environment'] += '\n' + variant['environment_append']
    return (data['persona_template'].format(**character) + '\n\n' +
            data['belief_heading'] + '\n' +
            '\n'.join(f'- {belief}' for belief in character['initial_beliefs']))


async def conversation(brain, name, system, questions, window):
    transcript = Transcript()  # In memory only; each repetition starts fresh.
    records = []
    last_spoke = None
    for turn, question in enumerate(questions):
        now = float(turn * 10)
        transcript.add(now, '', 'said', '新朋友', question)
        situation = catalog('zh')['recent_heading'] + '\n' + transcript.render(
            now=now, me=name, speaker=None, last_spoke_at=last_spoke,
            quiet_for=0, window=window, language='zh')
        text = await brain.compose(system, situation, Decision(True))
        if not text or not text.strip():
            raise RuntimeError(f'{name} turn {turn + 1}: generation failed; no synthetic replacement')
        transcript.add(now + 1, '', 'said', name, str(text))
        last_spoke = now + 1
        records.append({'question': question, 'text': str(text), 'situation': situation,
                        'performance': getattr(text, 'performance', {})})
        print(f'{name} / {turn + 1}: {text}', flush=True)
    return records


async def run(args):
    config_path = args.config.resolve()
    cfg = parse_config(config_path.read_text(), config_path.parent)
    trial = trial_settings()
    variant = {'name': args.direction, 'history': trial['history'],
               'environment_append': trial['a_boundary'] if args.direction == 'A' else '',
               'questions': trial['questions']}
    systems = {name: trial_system(name, variant) for name in args.characters}
    result = {'variant': variant, 'systems': systems, 'config': str(config_path),
              'model': cfg.model, 'effort': cfg.puppet_effort, 'auth': cfg.brain_auth,
              'started_at': datetime.now(timezone.utc).isoformat(),
              'conditions': 'Fresh reviewed beliefs; independent three-turn conversations; '
                            'production compose/schema/transcript; no reflection, audio, motors or state writes. '
                            'Existing strategies, environment and beliefs retained as controlled confounds.',
              'conversations': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    def save():
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    save()
    session = None
    if cfg.brain_auth == 'subscription':
        from .subscription import SubscriptionSession
        session = SubscriptionSession(profile=cfg.subscription_profile)
    brain = make_brain(cfg.provider, cfg.model, cfg.puppet_effort, cfg.ruminate_model,
                       auth=cfg.brain_auth, subscription_session=session)
    brain.language = 'zh'
    try:
        for name in args.characters:
            for repetition in range(1, args.repetitions + 1):
                print(f'--- {name}, repetition {repetition} ---', flush=True)
                turns = await conversation(brain, name, systems[name], variant['questions'], cfg.window)
                result['conversations'].append({'character': name, 'repetition': repetition, 'turns': turns})
                save()
    except Exception as error:
        result['failure'] = type(error).__name__
        save()
        raise
    if hasattr(brain, 'token_usage'):
        result['usage'] = brain.token_usage.snapshot()
    result['completed_at'] = datetime.now(timezone.utc).isoformat()
    save()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config.toml')
    parser.add_argument('--direction', choices=['A', 'B'], default='A')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--characters', nargs='+', choices=['Charlie', 'Lucy', 'Kaka'],
                        default=['Charlie', 'Lucy', 'Kaka'])
    parser.add_argument('--repetitions', type=int, default=3)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('--repetitions must be positive')
    asyncio.run(run(args))


if __name__ == '__main__':
    main()
