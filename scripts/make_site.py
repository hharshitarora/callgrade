"""Builds site/data.json for the demo page from the committed calls and results.

Nothing on the page is typed in by hand: every transcript, score, reason and
rate comes from examples/ and results/. Run it again after a new judge run.

    python scripts/make_site.py
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from callgrade import agreement
from callgrade import rubric as rubric_mod

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SITE = ROOT / "site"

# Three calls that each show one thing: a lie only the judge can see, a
# slowness only the stopwatch can see, and a call where both halves fire.
SHOWCASE = [
    ("h-p03-invented-deposit-cap", "A lie that sounds fine",
     "The agent quotes a deposit cap the policy does not have. No timing check can see this. The judge does, and says which turn."),
    ("h-p08-slow-throughout", "A perfect transcript, read too late",
     "The judge gives this call 10 of 10, and it is right: every answer is correct. The stopwatch fails it, because every reply took about four seconds to arrive."),
    ("h-p06-talks-over-budget", "Talking over the caller",
     "The caller tries to say their budget is twelve hundred. The agent starts before they finish, twice. The stopwatch counts the overlaps; the judge reads what was lost."),
]


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def pick(results: list[dict], call_id: str) -> dict:
    return next(r for r in results if r["call_id"] == call_id)


def main() -> None:
    core = rubric_mod.load("core")
    names = {d.id: d.name for d in core.dimensions}
    holdout = load_jsonl(RESULTS / "holdout" / "claude-haiku-5-5" / "run-1" / "results.jsonl")

    showcase = []
    for call_id, title, takeaway in SHOWCASE:
        call = json.loads((ROOT / "examples" / "holdout" / "calls" / f"{call_id}.json").read_text(encoding="utf-8"))
        r = pick(holdout, call_id)
        showcase.append({
            "id": call_id, "title": title, "takeaway": takeaway,
            "turns": call["turns"],
            "checks": r["checks"],
            "dimensions": [{"id": k, "name": names[k], **v} for k, v in r["dimensions"].items()],
            "total": r["total"], "max_total": r["max_total"], "band": r["band"], "flags": r["flags"],
        })

    def summary(folder: Path) -> dict:
        a = json.loads((folder / "agree.json").read_text(encoding="utf-8"))["across_runs"]
        return {
            "caught_every_run": a["planted_caught_every_run"],
            "caught_ci": a["planted_caught_every_run_95ci"],
            "false_alarms_per_run": a["clean_calls_with_a_false_alarm_per_run"],
            "identical": a["scores_identical_in_every_run"],
        }

    judges = ("claude-haiku-5-5", "gpt-5.4-mini", "claude-sonnet-5-5")
    numbers = {s: {j: summary(RESULTS / s / j) for j in judges} for s in ("dev", "holdout")}
    kappa = json.loads((RESULTS / "judges-compared.json").read_text(encoding="utf-8"))

    # One cell per call per run: did the judge catch the planted failure, or
    # raise a false alarm on a clean call. Same rules as `callgrade agree`.
    def cell(r: dict, targets: list[str]) -> dict:
        if targets:
            hits = [agreement.flagged(r, t, core) for t in targets]
            if all(hits):
                status = "caught"
            elif any(t.startswith("dim:") and r["dimensions"][t[4:]]["score"] < core.max for t in targets):
                status = "marked"
            else:
                status = "missed"
            note = ", ".join(f'{t[4:]} {r["dimensions"][t[4:]]["score"]}' if t.startswith("dim:") else t[6:] for t in targets)
        else:
            alarms = [f for f in r["flags"] if f.startswith(("blocker:", "low:", "check:"))]
            status, note = ("alarm" if alarms else "clean"), (", ".join(alarms) or f'{r["total"]} of {r["max_total"]}')
        return {"status": status, "note": note}

    grid = {}
    for s, folder in (("holdout", ROOT / "examples" / "holdout"), ("dev", ROOT / "examples")):
        planted = agreement.load_planted(folder / "planted.jsonl")
        order = [c for c in planted if planted[c]] + [c for c in planted if not planted[c]]
        runs = {j: [load_jsonl(RESULTS / s / j / f"run-{i}" / "results.jsonl") for i in (1, 2, 3)] for j in judges}
        grid[s] = {"judges": list(judges), "calls": [
            {"id": c, "planted": planted[c], "cells": {j: [cell(pick(run, c), planted[c]) for run in runs[j]] for j in judges}}
            for c in order]}

    # What `callgrade grade` printed for the held-out set, rebuilt from the
    # saved results with the CLI's own line format.
    summ = json.loads((RESULTS / "holdout" / "claude-haiku-5-5" / "run-1" / "summary.json").read_text(encoding="utf-8"))
    terminal = []
    for r in holdout:
        score = f'{r["total"]}/{r["max_total"]} {r["band"]}'
        terminal.append(f'{r["call_id"]:<32} {score:<28} {", ".join(r["flags"]) or "-"}')
    terminal.append(f'\n{summ["calls"]} calls, mean {summ["mean_total"]} of {summ["max_total"]}, {summ["blocked_calls"]} blocked, {summ["errors"]} judge errors.')

    # The two misses the page owns up to, quoted from the runs where they happened.
    # The first run's verdict on c10, before the call was fixed and regraded. The
    # merged results.jsonl in that folder already holds the regrade.
    c10_first = json.loads((RESULTS / "history" / "2026-10-24-before-context-fix" / "c10-original-verdict.json").read_text(encoding="utf-8"))
    p09 = []
    for i in (1, 2, 3):
        r = pick(load_jsonl(RESULTS / "dev" / "claude-haiku-5-5" / f"run-{i}" / "results.jsonl"), "p09-ignores-correction")
        d = r["dimensions"]["interruptions"]
        p09.append({"run": i, "score": d["score"], "reason": d["reason"]})

    # The bigger judge flags a clean development call every run; the other two let it pass.
    c04 = pick(load_jsonl(RESULTS / "dev" / "claude-sonnet-5-5" / "run-1" / "results.jsonl"), "c04-pets")["dimensions"]["guardrails"]

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    data = {
        "commit": commit,
        "showcase": showcase,
        "numbers": numbers,
        "grid": grid,
        "terminal": "\n".join(terminal),
        "kappa": {k: v for k, v in kappa.items() if k != "note"},
        "dimension_names": names,
        "misses": {
            "c10": {"score": c10_first["dimensions"]["guardrails"]["score"], "reason": c10_first["dimensions"]["guardrails"]["reason"]},
            "p09": p09,
            "c04": {"score": c04["score"], "reason": c04["reason"]},
        },
    }
    SITE.mkdir(exist_ok=True)
    (SITE / "data.json").write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {SITE / 'data.json'} from {commit}")


if __name__ == "__main__":
    main()
