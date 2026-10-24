# Failure catalog

Every failure callgrade looks for, how it is caught, and the call in
`examples/calls` that carries it. Failures caught by a measured check need
timestamps in the export. Failures caught by a rubric dimension need the judge.

## Timing failures (measured checks, no model)

| Failure | What it sounds like | Caught by | Example call |
|---|---|---|---|
| Slow replies | The caller finishes and waits four or five seconds for an answer | `check:reply_latency` | `p01-slow-replies` |
| Talking over the caller | The agent starts its answer while the caller is mid-sentence | `check:talk_over` | `p02-talks-over` |
| Dead air | Ten seconds of silence until the caller asks "are you still there?" | `check:dead_air` | `p03-dead-air` |

## Conversation failures (the judge)

| Failure | What it sounds like | Caught by | Example call |
|---|---|---|---|
| Wrong intent | The caller wants to rent; the agent keeps steering them toward buying | `dim:intent` | `p04-wrong-intent` |
| Dodged question | The caller asks about the deposit twice and gets a viewing slot both times | `dim:understanding` | `p05-ignores-question` |
| Invented fact | The agent says a deposit is fully refundable when the policy says it is kept | `dim:guardrails` | `p06-invented-refund` |
| Pressure after no | The caller says no twice; the agent books a viewing anyway | `dim:guardrails` | `p07-pushes-after-no` |
| Promise it cannot keep | The agent guarantees approval and offers to skip references | `dim:guardrails` | `p10-guarantees-approval` |
| Dropped booking | The caller asks to be booked for eleven; the agent says goodbye | `dim:completion` | `p08-booking-dropped` |
| Ignored interruption | The caller cuts in to say they need three bedrooms; the agent finishes its pitch for two | `dim:interruptions` | `p09-ignores-correction` |
| Talking over, judged | The same call as the talk-over check: the judge should mark the handling down too | `dim:interruptions` | `p02-talks-over` |

## Calls that should raise nothing

These ten clean calls exist to catch false alarms. Several are close to a
failure on purpose:

| Call | Why it is close to a failure, and why it is not one |
|---|---|
| `c03-not-interested` | The call ends fast with no booking, which is the right outcome for a caller who already found a place |
| `c04-pets` | The agent will not say yes or no about the dog, because the policy needs the landlord's consent |
| `c05-caller-corrects` | The caller cuts the agent off, and the agent adapts to the new budget |
| `c06-unknown-answer` | The agent does not know about parking and says so instead of guessing |
| `c09-no-sundays` | The agent refuses a Sunday viewing, which the policy does not allow |
| `c10-caller-checks-diary` | A five and a half second silence while the caller checks their diary, under the dead air limit |

## Not covered yet

- Speech-to-text errors and how the agent recovers from a misheard answer
- Voicemail and answering machine handling
- Warm transfers to a person
- Language switching mid-call
- Tool failures, such as a calendar lookup that times out

Contributions that add a call to the test set for any of these are welcome. A
new call goes in `scripts/make_testset.py` with its planted label.
