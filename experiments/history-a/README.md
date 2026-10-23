# History trial A

Baseline commit: `ed06de7`.
Baseline tag: `checkpoint-before-history-experiments-20261022`.
Experiment branch: `experiment/history-a-explicit-boundaries`.

This is an isolated text trial, not a replacement of the exhibition prompts.
`variant.json` adds one provisional shared history and one explicit behavioral
instruction to the existing persona template. Identities, strategies,
environment descriptions, initial beliefs, compose task, performance schema,
and transcript rendering remain the production versions. The full system
inputs are saved in `results.json`, along with the actual model and effort.

The shared history is experimental material, not an approved biography.
There are no author judgments about the creator's psychology, no instruction
to express puzzlement about knowledge, and no claim that textual history is
equivalent to a lived experience.

Run from the repository root with a Python 3.12 environment containing the
project's model dependencies:

```sh
python -m echo.history_trial --output experiments/history-a/results.json
```

The default is three independent repetitions per character, with three fixed
visitor questions per repetition. Replies within each conversation are fed
into subsequent turns. Each repetition begins with the reviewed initial
beliefs, not saved exhibition memory. Uses the model/auth configuration from
`config.toml` and the production `Brain.compose` method. There is no audio,
hardware, speaker competition, reflection or persistent character memory.
It therefore tests the dialogue prompts, not the complete live installation.
No fallback model or fabricated replacement is used on failure.

Existing social beliefs and environmental descriptions deliberately remain
as controlled confounds for a later B comparison. This small exploratory
sample does not establish a model's internal knowledge or ignorance.

The local test interpreter, if needed, is
`work/history-trial-venv/bin/python`. That environment is ignored by Git.
