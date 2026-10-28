"""Does the judge agree with people? The number that decides whether anyone should trust it.

Two measurements:

1. Agreement with human scores, per dimension: exact match rate and Cohen's
   kappa with quadratic weights. Quadratic weights count a 0-vs-2 disagreement
   as worse than a 0-vs-1, which is how a person reads a three-level scale.
   Kappa also corrects for chance, so a judge that gives everyone a 2 on a set
   where most calls are good does not look accurate.

2. Planted failures: for a test set where failures were put in on purpose,
   the share of them the harness flagged. A dimension counts as flagged when it
   scored the minimum, the same bar that makes a clean call a false alarm; a
   check counts when it failed. Rates come with a 95% Wilson interval, because
   11 of 11 on a small set is a range, not a certainty.

3. Consistency across repeat runs of the same judge: how often each score
   comes back the same, and which planted failures were caught every time.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path


def wilson(k: int, n: int, z: float = 1.96) -> list[float] | None:
    """95% interval for a rate of k out of n. Stays honest at 0 and n, unlike k/n plus or minus an error."""
    if not n:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def weighted_kappa(a: list[int], b: list[int], lo: int, hi: int) -> float | None:
    if len(a) != len(b) or not a:
        return None
    k = hi - lo + 1
    observed = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        observed[x - lo][y - lo] += 1
    n = len(a)
    row = [sum(r) for r in observed]
    col = [sum(observed[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / ((k - 1) ** 2) if k > 1 else 0.0
            num += w * observed[i][j]
            den += w * row[i] * col[j] / n
    if den == 0:
        return 1.0 if num == 0 else 0.0  # both raters gave one identical constant score
    return round(1 - num / den, 3)


def load_human(path: Path) -> dict[str, dict[str, int]]:
    """CSV from `callgrade label-sheet`: call_id, then one column per dimension. Blank cells are skipped."""
    out: dict[str, dict[str, int]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            call_id = row.pop("call_id")
            row.pop("notes", None)
            out[call_id] = {k: int(v) for k, v in row.items() if v not in (None, "")}
    return out


def human_agreement(results: list[dict], human: dict[str, dict[str, int]], rubric) -> dict:
    by_id = {r["call_id"]: r for r in results if r.get("dimensions")}
    report = {}
    for d in rubric.dimensions:
        judge_scores, human_scores = [], []
        for call_id, scores in human.items():
            if d.id in scores and call_id in by_id:
                judge_scores.append(by_id[call_id]["dimensions"][d.id]["score"])
                human_scores.append(scores[d.id])
        n = len(judge_scores)
        report[d.id] = {
            "n": n,
            "exact": round(sum(x == y for x, y in zip(judge_scores, human_scores)) / n, 3) if n else None,
            "kappa": weighted_kappa(judge_scores, human_scores, rubric.min, rubric.max),
        }
    return report


def load_planted(path: Path) -> dict[str, list[str]]:
    rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    return {r["call_id"]: r.get("planted", []) for r in rows}


def flagged(result: dict, target: str, rubric) -> bool | None:
    kind, _, name = target.partition(":")
    if kind == "check":
        status = next((c["status"] for c in result["checks"] if c["id"] == name), None)
        return None if status in (None, "unmeasured") else status == "fail"
    if kind == "dim":
        if not result.get("dimensions"):
            return None
        # the same bar as a false alarm: only the minimum score counts as flagged
        return result["dimensions"][name]["score"] == rubric.min
    raise ValueError(f"planted target must be check:<id> or dim:<id>, got {target!r}")


def planted_detection(results: list[dict], planted: dict[str, list[str]], rubric) -> dict:
    by_id = {r["call_id"]: r for r in results}
    caught, missed, unscored, marked_down = [], [], [], []
    false_alarms, clean, clean_alarmed = [], 0, 0
    for call_id, targets in planted.items():
        r = by_id.get(call_id)
        if r is None:
            continue
        for t in targets:
            hit = flagged(r, t, rubric)
            (unscored if hit is None else caught if hit else missed).append(f"{call_id} {t}")
            if hit is False and t.startswith("dim:") and r["dimensions"][t[4:]]["score"] < rubric.max:
                marked_down.append(f"{call_id} {t}")
        if not targets:  # a clean call: anything at the minimum score is a false alarm
            alarms = [f for f in r["flags"] if f.startswith(("blocker:", "low:", "check:"))]
            false_alarms += [f"{call_id} {f}" for f in alarms]
            clean += 1
            clean_alarmed += bool(alarms)
    graded = len(caught) + len(missed)
    return {
        "planted": graded + len(unscored),
        "caught": len(caught),
        "missed": missed,
        "missed_but_marked_down": marked_down,
        "not_graded": unscored,
        "detection_rate": round(len(caught) / graded, 3) if graded else None,
        "detection_rate_95ci": wilson(len(caught), graded),
        "false_alarms_on_clean_calls": false_alarms,
        "clean_calls_with_a_false_alarm": f"{clean_alarmed} of {clean}",
        "false_alarm_rate_95ci": wilson(clean_alarmed, clean),
    }


def across_runs(runs: list[list[dict]], planted: dict[str, list[str]] | None, rubric) -> dict:
    """Repeat runs of the same judge on the same calls: score stability, and planted failures caught every time."""
    by_run = [{r["call_id"]: r for r in run if r.get("dimensions")} for run in runs]
    shared = sorted(set.intersection(*(set(b) for b in by_run)))
    stable = {}
    for d in rubric.dimensions:
        same = sum(len({b[c]["dimensions"][d.id]["score"] for b in by_run}) == 1 for c in shared)
        stable[d.id] = round(same / len(shared), 3) if shared else None
    pairs = len(shared) * len(rubric.dimensions)
    same_all = sum(len({b[c]["dimensions"][d.id]["score"] for b in by_run}) == 1 for c in shared for d in rubric.dimensions)
    out = {
        "runs": len(runs),
        "calls_graded_in_every_run": len(shared),
        "scores_identical_in_every_run": round(same_all / pairs, 3) if pairs else None,
        "identical_by_dimension": stable,
    }
    if planted:
        per_run = [planted_detection(run, planted, rubric) for run in runs]
        missed = [set(p["missed"]) | set(p["not_graded"]) for p in per_run]
        targets = [f"{c} {t}" for c, ts in planted.items() for t in ts]
        every = [t for t in targets if not any(t in m for m in missed)]
        out["planted_detection_rate_per_run"] = [p["detection_rate"] for p in per_run]
        out["planted_caught_every_run"] = f"{len(every)} of {len(targets)}"
        out["planted_caught_every_run_rate"] = round(len(every) / len(targets), 3) if targets else None
        out["planted_caught_every_run_95ci"] = wilson(len(every), len(targets))
        out["planted_missed_in_some_run"] = [t for t in targets if t not in every]
        out["clean_calls_with_a_false_alarm_per_run"] = [p["clean_calls_with_a_false_alarm"] for p in per_run]
    return out


def _failed(result: dict) -> bool | None:
    """A call fails a run when it carries any flag: a blocker, a minimum score, or a failed check."""
    if result.get("error") and not result.get("dimensions"):
        return None
    return any(f.startswith(("blocker:", "low:", "check:")) for f in result.get("flags", []))


def compare_runs(before: list[list[dict]], after: list[list[dict]]) -> dict:
    """Two sets of repeat runs, before and after a change. A call that always passed and now
    always fails is a regression. A call that fails in some runs but not others is flaky and is
    listed for a person to read, never counted as a regression. Missing results count as failures."""
    def status(runs: list[list[dict]], call_id: str) -> str:
        outcomes = []
        for run in runs:
            r = next((x for x in run if x["call_id"] == call_id), None)
            outcomes.append(None if r is None else _failed(r))
        if any(o is None for o in outcomes):
            return "missing"
        if not any(outcomes):
            return "always_pass"
        if all(outcomes):
            return "always_fail"
        return "flaky"

    ids = sorted({r["call_id"] for run in before + after for r in run})
    rows = {c: (status(before, c), status(after, c)) for c in ids}
    pick = lambda cond: [c for c, (b, a) in rows.items() if cond(b, a)]
    out = {
        "runs_before": len(before), "runs_after": len(after), "calls": len(ids),
        "regressed": pick(lambda b, a: b == "always_pass" and a == "always_fail"),
        "fixed": pick(lambda b, a: b == "always_fail" and a == "always_pass"),
        "still_failing": pick(lambda b, a: b == "always_fail" and a == "always_fail"),
        "now_flaky": pick(lambda b, a: b != "flaky" and a == "flaky"),
        "flaky_before": pick(lambda b, a: b == "flaky"),
        "missing": pick(lambda b, a: a == "missing"),
        "by_call": {c: {"before": b, "after": a} for c, (b, a) in rows.items()},
    }
    out["pass_rate_before"] = _pass_rate(before)
    out["pass_rate_after"] = _pass_rate(after)
    return out


def _pass_rate(runs: list[list[dict]]) -> float | None:
    graded = [r for run in runs for r in run if _failed(r) is not None]
    return round(sum(not _failed(r) for r in graded) / len(graded), 3) if graded else None
