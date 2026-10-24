"""A single self-contained HTML report: no server, no scripts, opens anywhere."""
from __future__ import annotations

from html import escape

from .call import Call
from .rubric import Rubric

_CSS = """
:root{--bg:#fbfaf7;--fg:#1d1d1b;--muted:#6b6a64;--card:#fff;--line:#e6e3dc;--good:#1f7a4d;--mid:#a86b00;--bad:#b3261e;--hl:#fff3cd}
@media (prefers-color-scheme:dark){:root{--bg:#151514;--fg:#ecebe6;--muted:#9c9a92;--card:#1f1f1d;--line:#33322e;--good:#5cc28d;--mid:#e0a63c;--bad:#ef6b62;--hl:#3a3220}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:0}
.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:16px 0 28px}
.stat,.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat b{display:block;font-size:22px}.card{margin:0 0 18px}.head{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline}
.pill{display:inline-block;border-radius:99px;padding:1px 10px;font-size:13px;border:1px solid var(--line)}
.s2,.pass{color:var(--good)}.s1{color:var(--mid)}.s0,.fail{color:var(--bad)}.unmeasured{color:var(--muted)}
table{width:100%;border-collapse:collapse;margin:12px 0}td,th{text-align:left;vertical-align:top;padding:6px 8px;border-top:1px solid var(--line)}
th{font-weight:600;font-size:13px;color:var(--muted)}td.score{font-weight:700;white-space:nowrap}
details{margin-top:8px}summary{cursor:pointer;color:var(--muted)}ol{padding-left:28px}li{padding:2px 4px;border-radius:4px}
li.hit{background:var(--hl)}.who{font-weight:600}.t{color:var(--muted);font-variant-numeric:tabular-nums}
"""


def _score_class(score: int, rubric: Rubric) -> str:
    if score == rubric.max:
        return "s2"
    return "s0" if score == rubric.min else "s1"


def _call_card(result: dict, call: Call | None, rubric: Rubric) -> str:
    hits = set()
    for c in result["checks"]:
        if c["status"] == "fail":
            hits.update(c["turns"])
    if result["total"] is not None:
        score = f'<span class="pill">{result["total"]} / {result["max_total"]}</span> <span class="muted">{escape(result["band"] or "")}</span>'
    elif result["error"]:
        score = f'<span class="pill fail">judge error</span> <span class="muted">{escape(result["error"])}</span>'
    else:
        score = '<span class="pill">checks only</span>'
    flags = ", ".join(escape(f) for f in result["flags"]) or "none"
    rows = []
    if result["dimensions"]:
        for d in rubric.dimensions:
            v = result["dimensions"][d.id]
            hits.update(t - 1 for t in v.get("evidence_turns", []) if v["score"] < rubric.max)
            na = "" if v.get("applicable", True) else ' <span class="muted">(did not come up)</span>'
            rows.append(f'<tr><td>{escape(d.name)}{na}</td><td class="score {_score_class(v["score"], rubric)}">{v["score"]}</td>'
                        f'<td>{escape(v["reason"])}</td></tr>')
    dims = (f'<table><tr><th>Dimension</th><th>Score</th><th>Why</th></tr>{"".join(rows)}</table>' if rows else "")
    checks = "".join(f'<tr><td>{escape(c["name"])}</td><td class="score {c["status"]}">{c["status"]}</td><td>{escape(c["detail"])}</td></tr>'
                     for c in result["checks"])
    transcript = ""
    if call is not None:
        items = []
        for i, t in enumerate(call.turns):
            stamp = f'<span class="t">{t.start:.1f}s</span> ' if t.start is not None else ""
            items.append(f'<li class="{"hit" if i in hits else ""}">{stamp}<span class="who">{t.speaker}</span>: {escape(t.text)}</li>')
        transcript = f'<details><summary>Transcript ({len(call.turns)} turns, flagged turns highlighted)</summary><ol>{"".join(items)}</ol></details>'
    return (f'<section class="card"><div class="head"><h2>{escape(result["call_id"])}</h2><div>{score}</div></div>'
            f'<div class="muted">platform {escape(result["platform"])} &middot; flags: {flags}</div>{dims}'
            f'<table><tr><th>Measured check</th><th>Result</th><th>Detail</th></tr>{checks}</table>{transcript}</section>')


def render(results: list[dict], summary: dict, rubric: Rubric, calls: dict[str, Call], judge_label: str) -> str:
    mean = f'{summary["mean_total"]} / {summary["max_total"]}' if summary["mean_total"] is not None else "n/a"
    stats = [
        ("Calls", summary["calls"]),
        ("Mean score", mean),
        ("Blocked by a guardrail", summary["blocked_calls"]),
        ("Failed timing checks", sum(summary["check_failures"].values())),
        ("Judge errors", summary["errors"]),
    ]
    grid = "".join(f'<div class="stat"><span class="muted">{escape(k)}</span><b>{escape(str(v))}</b></div>' for k, v in stats)
    worst_first = sorted(results, key=lambda r: (r["total"] if r["total"] is not None else 10**6, -len(r["flags"])))
    cards = "".join(_call_card(r, calls.get(r["call_id"]), rubric) for r in worst_first)
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>callgrade report</title><style>{_CSS}</style></head><body><main>'
            f'<h1>callgrade report</h1><div class="muted">rubric {escape(rubric.title)} &middot; judge {escape(judge_label)} &middot; worst calls first</div>'
            f'<div class="grid">{grid}</div>{cards}</main></body></html>')
