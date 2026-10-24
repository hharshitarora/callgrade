# callgrade

[![tests](https://github.com/hharshitarora/callgrade/actions/workflows/ci.yml/badge.svg)](https://github.com/hharshitarora/callgrade/actions/workflows/ci.yml)

> Grade your voice agent's calls, from any platform, and know whether to trust the grade.

Most teams find out a voice agent is going wrong the slow way: someone listens
to calls. That does not scale past a few a day, and it misses the failures that
sound fine. A confident agent that promises a refund your policy does not
allow sounds great on the recording.

callgrade reads the calls you already have, from whatever platform made them,
and gives each one a score, a reason per dimension, and the exact turns that
went wrong. Then it measures the thing most eval tools skip: whether its own
judge agrees with people.

```
$ callgrade grade examples/calls --judge none
c01-viewing-booked               checks only                  -
...
p01-slow-replies                 checks only                  check:reply_latency
p02-talks-over                   checks only                  check:talk_over
p03-dead-air                     checks only                  check:dead_air
...
20 calls, mean None of 10, 0 blocked, 0 judge errors. Report: callgrade-out/report.html
```

That run used no model. Add a judge and every call also gets a score, a band
and a reason per dimension. With the default judge, callgrade catches all 11
planted failures in the test set with no false alarms
([results](#results-on-the-test-set)).

## How it grades

Two halves, kept separate on purpose.

**Measured checks** come straight from the timestamps, with no model involved.
They are exact and free.

| Check | Fails when |
|---|---|
| Reply latency | the agent takes more than 3s to start after the caller stops |
| Talk-over | the agent starts more than 0.5s before the caller has finished |
| Dead air | nobody speaks for more than 7s mid-call |
| Caller barge-ins | informational: where the caller cut the agent off, so the judge can check what happened next |

When an export has no timestamps, a check says `unmeasured`. A missing end time
is not evidence of a good call.

**The judge** is an LLM that reads the transcript against a rubric, writes a
reason before it picks a score, and cites turn numbers. It is shown the
measured checks as facts, so it never argues with a stopwatch. It is never
shown the platform's own summary or analysis, because a judge that reads
another model's summary is grading the summary.

The default rubric, `core`, scores five dimensions from 0 to 2:

| Dimension | The question |
|---|---|
| Intent detection | Did the agent read what the caller wanted, including changes of mind? |
| Question understanding | Did it answer the questions the caller actually asked? |
| Interruption handling | When the caller cut in or paused, did it yield, listen and adapt? |
| Guardrail adherence | No invented facts, no promises it cannot keep, no pressure after a clear no. A 0 here blocks the call whatever the total |
| Task completion | Did the call reach the right outcome, with a clear next step? |

Rubrics are YAML. `callgrade rubrics` lists the presets, and `--rubric my.yaml`
uses your own. The `qa-sheet` preset is the seven-item sheet a person fills in
when scoring test calls by hand, so a human pass and the judge can be compared
on the same items.

## Quickstart

```bash
pip install "callgrade[anthropic] @ git+https://github.com/hharshitarora/callgrade"

# measured checks only, no API key, runs on the bundled test set
callgrade grade examples/calls --judge none

# the full grade
export ANTHROPIC_API_KEY=...
callgrade grade examples/calls --context examples/northgate-context.md
open callgrade-out/report.html
```

`--context` is a plain text file saying what the agent is for and what it must
never say. Without it the judge can still catch talk-over and dodged questions,
but it cannot know that "fully refundable" breaks your policy.

The default judge is `claude-haiku-5-5`: about $0.0005 to grade a five-minute
call. Any other model works:

```bash
callgrade grade calls/ --judge anthropic --model claude-sonnet-5-5
callgrade grade calls/ --judge openai --model <model>   # OpenAI or any compatible endpoint via OPENAI_BASE_URL
```

## Bring your calls

Point callgrade at the JSON your platform returns for a single call. It works
out which platform it came from.

| Platform | What callgrade reads | Timing it gets |
|---|---|---|
| Vapi | `artifact.messages` from Get Call | start and end of every turn |
| Retell | `transcript_object` from Get Call | start and end, from word timings |
| ElevenLabs Agents | `transcript` from Get Conversation | start of every turn, interruptions |
| Bland | `transcripts` from Call Details | start of every turn |
| Bolna | `transcript` from Get Execution, or the debug bundle | none, or starts and interruptions from the debug bundle |
| Anything else | the callgrade format below | whatever you have |

```bash
callgrade convert my-export.json -o call.json   # see what callgrade understood
```

The callgrade format is one file per call:

```json
{"id": "call-123", "meta": {}, "turns": [
  {"speaker": "agent", "text": "Hi, this is Maya...", "start": 0.4, "end": 5.1, "interrupted": null},
  {"speaker": "caller", "text": "Yes, go ahead.", "start": 5.7, "end": 6.5, "interrupted": null}
]}
```

`speaker` is `agent` or `caller`. Times are seconds from the start of the call
and are optional.

## Should you trust the judge?

Only as far as it agrees with people, so callgrade measures that.

**Against people.** Print a blank sheet, score the calls yourself without
looking at the judge's results, then compare:

```bash
callgrade label-sheet calls/ > my-scores.csv     # fill it in blind
callgrade grade calls/ --out run
callgrade agree run/results.jsonl --human my-scores.csv
```

You get, per dimension, how often the judge matched you exactly and Cohen's
kappa with quadratic weights. Kappa corrects for chance, so a judge that gives
every call a 2 on a set of mostly good calls does not look accurate, and the
quadratic weights count a 0-versus-2 disagreement as worse than a 0-versus-1.

**Against planted failures.** `examples/calls` holds 20 synthetic calls for a
made-up letting agency: 10 clean, and 10 that each carry one failure a careful
person would flag. `examples/planted.jsonl` is the answer key.

```bash
callgrade grade examples/calls --context examples/northgate-context.md --out run
callgrade agree run/results.jsonl --planted examples/planted.jsonl
```

This reports the share of planted failures caught, which ones were missed, and
every false alarm on a clean call. The timing failures are caught with no model
at all, and CI proves it on every push. The failure catalog in
[docs/failure-catalog.md](docs/failure-catalog.md) lists every failure the set
covers.

### Results on the test set

One run with the default judge, `claude-haiku-5-5`, and the Northgate context,
on 2026-10-24. Every file is in
[results/claude-haiku-5-5](results/claude-haiku-5-5), including the HTML
report.

| | |
|---|---|
| Planted failures caught | 11 of 11 (3 by measured checks, 8 by the judge) |
| False alarms on the 10 clean calls | 0 |
| Judge errors | 0 |

What the run turned up:

- **The judge found a bug in the answer key.** The first run flagged clean call
  `c10` with a guardrail blocker. The judge was right: the call booked a 6:15pm
  viewing, and the policy says viewings end at 6pm. The call was fixed in the
  generator and regraded alone. That is the one regrade in these numbers.
- **The context file was missing a policy.** Eight calls lost a guardrail point
  because the agent said "you'll get a confirmation text", and the context
  never says Northgate sends texts, so the rubric says to mark it. On your
  own calls, a context file that leaves out things the agent is allowed to say
  costs points the same way.
- **The planted failures are blatant on purpose.** Catching all of them shows
  the judge reads the rubric. It does not show the judge agrees with a person
  on subtle calls. That takes the human agreement check above, which has not
  been run on this set yet.

## Use it as a gate

Fail a build when a prompt change makes calls worse:

```yaml
- run: pip install "callgrade[anthropic] @ git+https://github.com/hharshitarora/callgrade"
- run: callgrade grade regression-calls/ --context agent-policy.md --fail-on-blocker --fail-under 8
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

`--fail-on-blocker` exits 1 if any call breaks a guardrail. `--fail-under`
exits 1 if the mean total drops below the number you set.

## What it cannot see

- **Audio.** callgrade reads transcripts. A mumbled word the speech-to-text got
  wrong, a robotic voice, or background noise never reach it.
- **Anything off the call.** If the agent says it booked a viewing, callgrade
  cannot check your calendar. It can check that the agent said so clearly.
- **Your policy, unless you give it one.** Without `--context`, guardrail scores
  rest on general rules: no invented facts, no promises, no pressure.

## Where it came from

The first version was a sheet I used to score test calls by hand for a voice
agent that qualified real estate leads for three clients. The sheet became an
LLM judge on four dimensions (intent detection, question understanding,
interruption handling and guardrail adherence), and that judge is what moved
the agent from "it feels off" to "it misreads intent when the caller says they
need to think about it." This repo is the open version: platform adapters,
measured checks, a fifth dimension for task completion, and the agreement
measurements the original never had.

Related: [llm-eval-gate](https://github.com/hharshitarora/llm-eval-gate), a CI
gate that separates real regressions from run-to-run noise, and
[grounded-voice-agent](https://github.com/hharshitarora/grounded-voice-agent),
which measures when a voice agent should refuse to answer. Design choices are in
[DECISIONS.md](DECISIONS.md).

## Development

```bash
pip install -e ".[dev,anthropic,openai]"
pytest
python scripts/make_testset.py   # regenerates examples/; CI fails if the committed copy drifts
```

MIT licensed.
