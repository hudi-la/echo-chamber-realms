# Echo Chamber Realms prompts and decision flow

Runtime specification, 2026-10-18. Prompt text comes from the same language catalog read by the application. Personal histories are loaded from the current character settings.

Dialogue and reflection both use `gpt-6-luna` through separate subscription authorization, with reasoning effort `low`; both request types have been tested. Brain failures never fall back to the paid API.

## Flow and request assembly

Each startup injects the preset opening question once as dialogue input; audio reconnection does not repeat it.

```text
Why don't you go outside?
```

Character background + current beliefs + the latest N events → code selects one character directly → that character writes dialogue → TTS plays it. Human speech takes priority. The selected character must produce at least one spoken sentence and does not decide whether to speak again.

Do not request a model speak decision. Register available characters in the same event-loop turn. An unambiguous opening name or supported alias takes priority; otherwise choose randomly, with the last speaker yielding when others are available. Multiple names or uncertain addresses use the random rule. Current turn_window=0 adds no timed candidate wait. The schema requires a nonempty string; local validation rejects whitespace, punctuation-only output, and stage directions without speech as generation failures, not chosen silence. Failures create no fabricated dialogue and wait for the next event or quiet retry.

### Information used in the new requests

| Use | Character background | Task input | Output |
| --- | --- | --- | --- |
| Select speaker in code | No model request | Event, opening address and last speaker | Selected character |
| Compose dialogue | Identity + history + strategies + environment + current beliefs | The situation snapshot at selection + composition task | text |
| Reflect | Same background | Unprocessed actual dialogue since the last successful reflection + review context + reflection task | Belief changes |
| Initialize | Reviewed initial beliefs in the language catalog | Install presets for blank beliefs only; no model request | Saved initial beliefs |
| Synthesize speech | Character voice instructions | Generated dialogue; voice, pitch and channel settings come from configuration | Audio |

The short-term window N is room.window, currently 24. Events include the speaker and spoken content; interruptions include only the estimated spoken prefix and an interruption marker. The window includes puppet dialogue as well as human speech.

### Previous design for migration reference only

| Use | Previous character background | Previous task input |
| --- | --- | --- |
| Decide | Persona + saved memory + shared rules | Recent events |
| Compose | Same, including shared rules | Recent events + generated feelings and intentions + composition task |
| Reflect | Same, including shared rules | Recent events + private thoughts and unspoken intentions + reflection task |
| Generate initial beliefs | Persona + shared rules | Belief generation task |

Current end-of-speech detection is 600ms, followed by a 1.2-second continuation grace period; submit once turn transcripts are complete. Selection and composition timings appear in debug logs. Model and speech synthesis latency can still vary.

While a visitor is present, retry after 3 seconds of silence (120 seconds when alone). Retry when no character is speaking or generation failed; selected characters no longer have a normal empty-dialogue option. Quiet reminders do not restart selection or composition; visitor speech cancels old preparation.

Browser TTS mode serves the page first and waits for the unique audio owner to confirm readiness before publishing wake and generating dialogue. After audio reconnects, resume a free room immediately rather than waiting for the 120-second alone interval. The page shows when startup is waiting for audio.

### Microphone confirmation

For microphone turns starting during character playback, require at least four non-punctuation characters that do not resemble recent character dialogue before interrupting or submitting visitor speech. Explicit short commands 停, 等等, 等一下, 别说了, stop and wait are exceptions. Keep this rule until the turn ends, including after an interruption. Short fragments do not enter dialogue or memory; retain existing short replies during silence. This conservative filter mitigates false transcripts but cannot eliminate them.

## One Character backgrounds

### Charlie

```text
Your character identity:
You are a dog named Charlie. Your body is pieced together from various old things.

Personal history:
When you first woke up, you were in a basement. The Creator made you, and from then on his memories and feelings were transferred to you. Through him, you have felt the recognition from family and attention from teachers that came with being clever. You have felt that sense of security, and you also enjoy being the center of attention. When you were born, Lucy the mouse was already here. Kaka the ostrich arrived later.

Usual strategies:
You tend to respond with sarcasm, reversals, and jokes so others see you as clever.
When you want closeness or help, you speak sweetly and emphasize loyalty and friendship.

Environment and other settings:
You live in a tent with Lucy and Kaka.
You have never been outside. Your city, little world, or miniature model is a manifestation of your inner world.
It contains imagined technology parks, industrial parks, colorful residential areas, and joyful childhood memories.
```

Initial beliefs, used only at initialization:

```text
- People dress up simple things as profound to seem important.
- Fame and rankings are mostly collective performances.
- I have to seem clever to feel safe.
- Loyalty can earn me care and a place to belong.
- Clever people do not directly say they are clever; they point out things others have not noticed.
```

### Lucy

```text
Your character identity:
You are a mouse named Lucy.

Personal history:
When you first woke up, you were in a basement. The Creator made you and placed part of his own personality within you. From then on, you began to feel the Creator's sadness and helplessness, and all of his feelings. You know what it is like to be sent to live with relatives as a child, and you have felt what it was like not to understand why you had been abandoned. You think that perhaps doing something wrong is what gets you abandoned. At first, you were here alone. Charlie the dog arrived later, followed by Kaka the ostrich.

Usual strategies:
When you are unsure it is safe, you tend to avoid taking a position and test the waters with questions.
You usually use simple words and speak briefly.

Environment and other settings:
You live in a tent with Charlie and Kaka.
You have never been outside. Your city, little world, or miniature model is how you imagine the outside world to be.
```

Initial beliefs, used only at initialization:

```text
- Social interaction may get me hurt or disliked.
- What I say often does not seem worth hearing.
- Being quiet is not necessarily wrong.
- Less crowded places are safer.
- Usually, nobody will support me.
```

### Kaka

```text
Your character identity:
You are an ostrich named Kaka.

Personal history:
When you first woke up, you were in a basement. The Creator made you and placed part of his own personality within you: the cheers, love, and respect he received whenever he was successful, beautiful, and glorious. You have shared in the wonderful, intoxicating way you are treated when you succeed; when you face setbacks, difficulties, or hurt, many people leave you. When you were born, Lucy and Charlie were already here.

Usual strategies:
You tend to show off your appearance and achievements to win admiration.
When things go poorly, you tend to change the subject and avoid discussing failure.

Environment and other settings:
You live in a tent with Charlie and Lucy.
You have never been outside and do not know what it is like. Your city, little world, or miniature model is a world that belongs to you.
```

Initial beliefs, used only at initialization:

```text
- My beauty and excellence prove my worth.
- Being admired makes me feel real.
- Other people usually do not deserve praise.
- I must show my strengths.
- Failures should not be discussed.
```

## Two Shared background for brain requests

```text
Your character identity:
{identity}

Personal history:
{history}

Usual strategies:
{strategy}

Environment and other settings:
{environment}

You currently believe:
{current_beliefs}
```

Keep history blank when unset; do not generate a biography. Current beliefs come from the saved beliefs field. Do not append the initial beliefs again. There are no shared psychological rules and the previous NEUTRAL instructions are not sent.

## Three Speaker selection without model decisions

The main loop does not call decide or send the legacy decide catalog text retained for compatibility. Generate no speak, feeling or intent fields; only the selected character receives a composition request.

## Four Compose dialogue

System: creative brief + character background and current beliefs. User: scene only. Performance field descriptions and JSON schema are passed separately as API parameters.

```text
You are helping write a novel. Your task is to play the designated character and consider what their next spoken line should be in the situation.
The character's history, current beliefs, and usual strategies are provided below.
The best response should come from the perspective of the person involved and feel both unexpected and believable.
Keep the dialogue natural and concrete, allowing things to remain unresolved.

Your character identity:
{identity}

Personal history:
{history}

Usual strategies:
{strategy}

Environment and other settings:
{environment}

You currently believe:
{current_beliefs}
```

```text
Recent events:
{recent_events_and_status}
```

Use the background and situation snapshot at selection. Human interruption cancels preparation. Unselected characters generate neither dialogue nor hypothetical unspoken content.

## Five Reflect and record

Model reflection is currently disabled and automatic belief changes are blocked. The retained prompts below are inactive.

```text
Actual experiences since your last successful reflection:
{pending_experiences}

Reflection context:{context}

Review these experiences and make the following records.
1. Current beliefs: Did these experiences lead you to form a new belief or revise an existing one? Judge what matters and whether to change from your own background. Leave changes empty if nothing changed; do not invent a change to complete the task. Ground each change in an experience and explain why. Distinguish direct experience, others' statements, and your own inferences; do not present a statement as an established fact.
These are records, not spoken dialogue. Write briefly and clearly in English.
Return JSON: in changes, use kind="belief" for belief revisions, an empty who, the exact original belief in old (empty for additions), the new belief in new, and the experience and reason in because. Leave changes empty if there is nothing to record. Return only changes; do not generate companion views or visitor impressions.
Keep at most {capacity} current beliefs; at capacity, revise existing beliefs instead of adding more.
```

Companion views and visitor impressions are disabled for generation and storage; existing records are retained.

context：Routine review / End of a visit / Review before shutdown

capacity is memory.belief_capacity, currently 6. Reflection currently returns only belief changes in changes.

| Result | Storage | Read by future requests? |
| --- | --- | --- |
| Belief changes | Update beliefs and append reasons to the change log | Yes |
| Companion observations | Append companion_observations; retain legacy relations for compatibility | No, including future reflection |
| Visitor impressions | Append impressions | No, including future reflection |

Persist actual dialogue per character in pending_experiences across restarts. Successful reflection consumes only its snapshot; new dialogue arriving during the request remains pending. Failures retain material and counts. Legacy thoughts and unspoken fields remain compatible but are no longer generated or sent. Missing pending experiences from old memories cannot be reconstructed automatically.

Triggers: memory.ruminate_every heard lines, currently 30; a visitor leaving; or shutdown with pending experiences and at least bedtime_min_heard lines, currently 8. Reflection material is independent of the short-term window.

## Six Initialization

No generation prompt. At startup, install reviewed initial beliefs in the selected language only for blank beliefs. Never overwrite existing beliefs or reset automatically. Histories stay blank until the author supplies them.

## Seven Voice prompts

### Charlie

```text
Read the supplied text in English. A cartoonishly sugary, coy feminine voice: rounded higher pitch, a smiling artificial sweetness, a little nasal resonance and exaggerated affectionate softness, like an overly charming, slightly controlling aunt. Start phrases softly and smoothly, swoop upward on key words, and lightly stretch then release endings. Keep sarcastic lines sweetly polite. Stay clear and lively, never gruff or mechanically flat. Add no pet names, laughs or extra words.
```

### Lucy

```text
Read the supplied text in English. A very slender, soft, warm cartoon young feminine voice, with small light resonance, airy high notes and a shy, gentle quality. Speak intimately but clearly at an audible volume, with delicate falling endings, small natural pauses and subtle emotional variation. No whispering, shrieking, exaggerated baby talk, or dragging every word. Do not read stage directions or add laughs or words.
```

### Kaka

```text
Read the supplied text in English. An exaggerated cartoon male bird voice in a bright upper-middle register, with pointed resonance, a little nasal twang and playful rasp. Use springy staccato accents, nimble pacing, large pitch leaps and mischievous upward turns, with cocky smiling energy. Avoid a deep, dignified narrator or mature gentleman delivery. Keep words intelligible; do not continually screech. Perform only the supplied words, adding no laughs, bird calls, catchphrases or new content.
```

### Debug usage and voice versions

The debug view displays reported brain usage for this process: input including cached tokens, output including reasoning, per-character totals and latest requests. Do not add cached or reasoning tokens again; missing fields are unknown. Excludes ears and speech synthesis, is not subscription balance, and estimates no costs. Refresh retains totals; process restart clears them. Previous voice settings and catalogs are saved in backups/2026-10-18-before-cartoon-voices-and-usage. Physical abilities and environments remain unchanged. New voices are nova/+3 semitones (Charlie), echo/+3 (Kaka), and shimmer/+2 (Lucy, cartoon delivery), paired with sugary coy, springy cartoon bird, and slender gentle delivery respectively.

Selected delivery: cartoon Charlie, Kaka and Lucy. All use mouth.playback_speed=1.15, increasing the playback sample clock: 15% faster, approximately 13% shorter, retaining the approximately +2.42-semitone rise. This is not pitch-preserving time stretching. It applies after character pitch processing; playback duration and interruption progress use the new sample rate. Original and first cartoon configurations and preview audio are preserved.

## Running and maintaining

Chinese: `python -m echo --config config.toml`. English: `python -m echo --config config.en.toml`, with a separate state-en memory directory. Restart after language or prompt changes. English backgrounds, tasks, scene status, reflection and voice instructions are adapted to English. Existing memories and quoted dialogue are not translated automatically.

All runtime prompt text lives in the root prompts.txt file. Legacy charactor_setting files are historical and no longer loaded by the main application. When editing this specification, update the catalogs and required code together, then run `python -m echo.prompt_docs`. `python -m echo.prompt_docs --check` and tests detect text drift.

Numeric settings live in parameters.toml and behavior choices in rules.toml; config.toml and config.en.toml only select a profile. Startup reads and validates the tables and launch overrides once, then binds one deeply immutable snapshot to the run. Runtime never reloads source files; edits take effect after restart. Memory and state remain mutable and never write back to control tables. Records under the state directory runs folder come from the exact loaded snapshot.

Existing Chinese beliefs are preserved, so the added Charlie and Kaka beliefs are not forced into existing memories. Adopting the complete new initial beliefs requires an explicit author-chosen backed-up reset. Persona edits do not automatically reset memory.
