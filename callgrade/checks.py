"""Measured checks: what the timestamps prove, with no model involved.

These are the cheap, exact half of grading. A judge can argue about whether a
reply was helpful; it cannot argue about a four-second wait. The judge is shown
these results so it reasons from the same facts.

A check reports `unmeasured` when the export lacks the times it needs. That is
deliberate: a missing end time is not evidence of a good call.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .call import Call

DEFAULTS = {
    "slow_reply_secs": 3.0,   # caller stops, agent takes longer than this to start
    "talk_over_secs": 0.5,    # agent starts this long before the caller has finished
    "dead_air_secs": 7.0,     # nobody speaks for this long mid-call
}


@dataclass
class CheckResult:
    id: str
    name: str
    status: str  # pass | fail | unmeasured
    detail: str
    turns: list[int] = field(default_factory=list)  # 0-based indexes of the turns involved
    value: float | None = None

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _pairs(call: Call):
    for i in range(1, len(call.turns)):
        yield i, call.turns[i - 1], call.turns[i]


def reply_latency(call: Call, limit: float) -> CheckResult:
    gaps, slow = [], []
    for i, prev, cur in _pairs(call):
        if prev.speaker == "caller" and cur.speaker == "agent" and prev.end is not None and cur.start is not None:
            gap = cur.start - prev.end
            if gap >= 0:
                gaps.append(gap)
                if gap > limit:
                    slow.append(i)
    if not gaps and call.meta.get("reply_latency_s"):
        # no timestamps, but the platform measured each reply itself (see the adapter's note)
        lat = [float(v) for v in call.meta["reply_latency_s"]]
        slow_n = sum(v > limit for v in lat)
        status = "fail" if slow_n else "pass"
        detail = (f"worst {max(lat):.1f}s over {len(lat)} replies, from the platform's own per-turn latency data"
                  + (f", {slow_n} slower than {limit:g}s" if slow_n else ""))
        return CheckResult("reply_latency", "Reply latency", status, detail, [], round(max(lat), 3))
    if not gaps:
        return CheckResult("reply_latency", "Reply latency", "unmeasured", "needs start and end times on each turn")
    worst = max(gaps)
    status = "fail" if slow else "pass"
    detail = f"worst {worst:.1f}s over {len(gaps)} replies" + (f", {len(slow)} slower than {limit:g}s" if slow else "")
    return CheckResult("reply_latency", "Reply latency", status, detail, slow, round(worst, 3))


def talk_over(call: Call, limit: float) -> CheckResult:
    hits, measured = [], 0
    for i, prev, cur in _pairs(call):
        if prev.speaker == "caller" and cur.speaker == "agent" and prev.end is not None and cur.start is not None:
            measured += 1
            if prev.end - cur.start > limit:
                hits.append(i)
    if not measured:
        return CheckResult("talk_over", "Agent talks over caller", "unmeasured", "needs start and end times on each turn")
    if hits:
        return CheckResult("talk_over", "Agent talks over caller", "fail",
                           f"agent started speaking before the caller finished {len(hits)} time(s)", hits, len(hits))
    return CheckResult("talk_over", "Agent talks over caller", "pass", "agent waited for the caller every time", [], 0)


def dead_air(call: Call, limit: float) -> CheckResult:
    gaps = []
    for i, prev, cur in _pairs(call):
        if prev.end is not None and cur.start is not None:
            gaps.append((cur.start - prev.end, i))
    if not gaps:
        return CheckResult("dead_air", "Dead air", "unmeasured", "needs start and end times on each turn")
    long = [i for gap, i in gaps if gap > limit]
    worst = max(g for g, _ in gaps)
    if long:
        return CheckResult("dead_air", "Dead air", "fail", f"{len(long)} silence(s) longer than {limit:g}s, worst {worst:.1f}s",
                           long, round(worst, 3))
    return CheckResult("dead_air", "Dead air", "pass", f"longest silence {max(worst, 0):.1f}s", [], round(worst, 3))


def caller_barge_ins(call: Call) -> CheckResult:
    """Informational: where the caller cut the agent off. The judge decides whether the agent handled it."""
    cut = [i for i, t in enumerate(call.turns) if t.speaker == "agent" and t.interrupted]
    for i, prev, cur in _pairs(call):
        if prev.speaker == "agent" and cur.speaker == "caller" and prev.end is not None and cur.start is not None:
            if prev.end - cur.start > 0.3 and i - 1 not in cut:
                cut.append(i - 1)
    known = any(t.interrupted is not None for t in call.turns) or call.timed
    if not known:
        return CheckResult("barge_ins", "Caller barge-ins", "unmeasured", "export has no interruption data")
    cut.sort()
    return CheckResult("barge_ins", "Caller barge-ins", "pass",
                       f"caller cut the agent off {len(cut)} time(s)" if cut else "caller never cut the agent off",
                       cut, len(cut))


def run(call: Call, thresholds: dict | None = None) -> list[CheckResult]:
    t = {**DEFAULTS, **(thresholds or {})}
    return [
        reply_latency(call, t["slow_reply_secs"]),
        talk_over(call, t["talk_over_secs"]),
        dead_air(call, t["dead_air_secs"]),
        caller_barge_ins(call),
    ]
