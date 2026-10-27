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
and a reason per dimension. With the default judge, callgrade caught all 11
planted failures in each of three runs on the test set, with no false alarms
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

**Against itself.** A judge is a model, so the same call can get a different
score on a second run. Pass several runs of the same calls to `agree` and it
reports how often each score came back the same, and which planted failures
were caught every time rather than once:

```bash
for i in 1 2 3; do callgrade grade calls/ --out run-$i; done
callgrade agree run-1/results.jsonl run-2/results.jsonl run-3/results.jsonl --planted planted.jsonl
```

Every rate comes with a 95% interval. On a test set this small, 11 of 11 means
"somewhere between 74% and 100%", and the report says so.

### Results on the test set

Three runs of the default judge, `claude-haiku-5-5`, with the Northgate
context, on 2026-10-26. A planted failure counts as caught only when the judge
gives it the minimum score, the same bar that makes a clean call a false
alarm. Every file, including the HTML reports, is in
[results/claude-haiku-5-5](results/claude-haiku-5-5).

| | Result | 95% interval |
|---|---|---|
| Planted failures caught in all 3 runs | 11 of 11 | 74% to 100% |
| Clean calls with a false alarm | 0 of 10, in every run | 0% to 28% |
| Scores identical across all 3 runs | 77% of call and dimension pairs | |
| Judge errors | 0 of 60 gradings | |

How it got there, with every earlier run kept in
[results/history](results/history):

- **The judge found a bug in the answer key.** The first run flagged clean call
  `c10` with a guardrail blocker. The judge was right: the call booked a 6:15pm
  viewing, and the policy says viewings end at 6pm. The call was fixed.
- **The context file was missing a policy.** Eight calls lost a guardrail point
  because the agent said "you'll get a confirmation text" and the context never
  said Northgate sends texts. That line was added.
- **Repeat runs found a bug in the rubric.** On three runs, `p09`, where the
  agent ignores a caller who cuts in to say they need three bedrooms, was
  caught once. The rubric's middle level read "yielded but then carried on as
  if the interruption had not happened", which describes `p09` exactly, so a 1
  was a fair reading. The levels now separate an agent that adapts late (1)
  from one that carries on as if a changed need was never said (0). After the
  fix, `p09` was caught in all three runs.

### A second judge from another model family

The test calls were written with Claude, and judges can favour text in their
own family's style. So the same 20 calls were graded three more times by
OpenAI's `gpt-5.4-mini`, on 2026-10-27. Files are in
[results/gpt-5.4-mini](results/gpt-5.4-mini).

| | claude-haiku-5-5 | gpt-5.4-mini |
|---|---|---|
| Planted failures caught in all 3 runs | 11 of 11 (74% to 100%) | 9 of 11 (52% to 95%) |
| Clean calls with a false alarm | 0 of 10, every run | 1 of 10 in one run, 0 in the other two |
| Scores identical across all 3 runs | 77% | 85% |

The OpenAI judge missed the interruption failure in `p02` and `p09` once each,
scoring them 1 instead of 0. Its one false alarm was a guardrail blocker on
`c05`, saying that offering specific slots invented a policy. The slots were
Thursday at six and Saturday at ten, inside the stated hours, though six is
the closing time and a fair person could query it. It was more consistent with itself than Haiku and less sensitive to the planted
failures.

How far the two judges agree with each other, as quadratic weighted kappa
averaged over the three paired runs ([results/judges-compared.json](results/judges-compared.json)):

| Intent | Understanding | Interruptions | Guardrails | Completion |
|---|---|---|---|---|
| 0.89 | 0.60 | 0.80 | 0.76 | 0.74 |

0.6 is a common bar for a judge allowed to gate a release. Question
understanding sits right on it, so that is where two judges disagree most and
where a person's scores matter most.

What these numbers do not show:

- **The fixes were made on this test set and measured on it again.** That
  flatters the numbers. A new set of planted calls, written after the fixes,
  is the honest next check.
- **Task completion is the least stable dimension:** the same score came back
  on only 60% of calls across three runs. Its rubric needs the same treatment
  the interruption rubric got.
- **The planted failures are blatant on purpose.** Catching them shows the
  judge reads the rubric, not that it agrees with a person on subtle calls.
  That takes the human agreement check above, which has not been run yet.

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
