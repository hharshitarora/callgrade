"""One call in, one result out: measured checks, judge scores, a total and a band."""
from __future__ import annotations

from . import checks as checks_mod
from . import judge as judge_mod
from .call import Call
from .rubric import Rubric


def grade_call(call: Call, rubric: Rubric, provider=None, context: str = "", thresholds: dict | None = None) -> dict:
    checks = checks_mod.run(call, thresholds)
    result = {
        "call_id": call.id,
        "platform": call.meta.get("platform", "callgrade"),
        "rubric": rubric.name,
        "turns": len(call.turns),
        "checks": [c.to_dict() for c in checks],
        "dimensions": None,
        "total": None,
        "max_total": rubric.max_total,
        "band": None,
        "flags": [f"check:{c.id}" for c in checks if c.status == "fail"],
        "error": None,
    }
    if provider is None:
        return result
    try:
        dims = judge_mod.grade(call, rubric, checks, provider, context)
    except Exception as exc:  # one bad call must not sink a batch; the error is reported on the call
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    total = sum(d["score"] for d in dims.values())
    result["dimensions"] = {d.id: dims[d.id] for d in rubric.dimensions}
    result["total"] = total
    result["band"] = rubric.band(total)
    result["flags"] += [f"blocker:{d.id}" for d in rubric.dimensions if d.blocker and dims[d.id]["score"] == rubric.min]
    result["flags"] += [f"low:{d.id}" for d in rubric.dimensions
                        if not d.blocker and dims[d.id]["score"] == rubric.min]
    return result


def summarize(results: list[dict], rubric: Rubric) -> dict:
    scored = [r for r in results if r["total"] is not None]
    per_dim = {}
    for d in rubric.dimensions:
        vals = [r["dimensions"][d.id]["score"] for r in scored]
        per_dim[d.id] = round(sum(vals) / len(vals), 3) if vals else None
    check_fails = {}
    for r in results:
        for c in r["checks"]:
            if c["status"] == "fail":
                check_fails[c["id"]] = check_fails.get(c["id"], 0) + 1
    return {
        "calls": len(results),
        "scored": len(scored),
        "errors": sum(1 for r in results if r["error"]),
        "mean_total": round(sum(r["total"] for r in scored) / len(scored), 3) if scored else None,
        "max_total": rubric.max_total,
        "mean_by_dimension": per_dim,
        "check_failures": check_fails,
        "blocked_calls": sum(1 for r in results if any(f.startswith("blocker:") for f in r["flags"])),
    }
