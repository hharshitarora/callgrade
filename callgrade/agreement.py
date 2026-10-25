"""Does the judge agree with people? The number that decides whether anyone should trust it.

Two measurements:

1. Agreement with human scores, per dimension: exact match rate and Cohen's
   kappa with quadratic weights. Quadratic weights count a 0-vs-2 disagreement
   as worse than a 0-vs-1, which is how a person reads a three-level scale.
   Kappa also corrects for chance, so a judge that gives everyone a 2 on a set
   where most calls are good does not look accurate.

2. Planted failures: for a test set where failures were put in on purpose,
   the share of them the harness flagged. A dimension counts as flagged when it
   scored below the top level; a check counts when it failed.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path


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
    false_alarms = []
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
    graded = len(caught) + len(missed)
    return {
        "planted": graded + len(unscored),
        "caught": len(caught),
        "missed": missed,
        "missed_but_marked_down": marked_down,
        "not_graded": unscored,
        "detection_rate": round(len(caught) / graded, 3) if graded else None,
        "false_alarms_on_clean_calls": false_alarms,
    }
