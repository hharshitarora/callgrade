"""Writes results/judges-compared.json: how far each pair of judges agrees.

For every pair of judges that graded a set, run N of one is scored against
run N of the other as if the second were the human rater, with quadratic
weighted kappa per dimension, averaged over the paired runs.

    python scripts/compare_judges.py
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

from callgrade import agreement
from callgrade import rubric as rubric_mod

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SETS = ("dev", "holdout")


def load(path: Path) -> dict[str, dict]:
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {r["call_id"]: r for r in rows if r.get("dimensions")}


def main() -> None:
    core = rubric_mod.load("core")
    out = {"note": "Run N of the first judge scored against run N of the second as if the second were the human rater. "
                   "Quadratic weighted kappa per dimension, mean over the paired runs."}
    judges = sorted({p.name for s in SETS for p in (RESULTS / s).iterdir() if (p / "run-1").exists()})
    for a, b in itertools.combinations(judges, 2):
        key = f"{a} vs {b}"
        out[key] = {}
        for s in SETS:
            runs = sorted(p.name for p in (RESULTS / s / a).iterdir() if p.name.startswith("run-") and (RESULTS / s / b / p.name).exists())
            per_dim = {d.id: [] for d in core.dimensions}
            for r in runs:
                ra, rb = load(RESULTS / s / a / r / "results.jsonl"), load(RESULTS / s / b / r / "results.jsonl")
                shared = sorted(set(ra) & set(rb))
                for d in core.dimensions:
                    k = agreement.weighted_kappa([ra[c]["dimensions"][d.id]["score"] for c in shared],
                                                 [rb[c]["dimensions"][d.id]["score"] for c in shared], core.min, core.max)
                    if k is not None:
                        per_dim[d.id].append(k)
            out[key][s] = {d: round(sum(v) / len(v), 2) if v else None for d, v in per_dim.items()}
            out[key][s]["runs_paired"] = len(runs)
    (RESULTS / "judges-compared.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
