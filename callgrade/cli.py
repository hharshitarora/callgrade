from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import __version__, adapters, agreement, grade, report
from . import judge as judge_mod
from . import rubric as rubric_mod


def _call_files(paths: list[str]) -> list[Path]:
    files = []
    for p in map(Path, paths):
        files += sorted(p.glob("*.json")) if p.is_dir() else [p]
    if not files:
        sys.exit("no call files found")
    return files


def _load_calls(paths: list[str], platform: str):
    calls, failed = [], []
    for f in _call_files(paths):
        try:
            calls.append(adapters.load(f, platform))
        except (ValueError, KeyError, json.JSONDecodeError) as exc:
            failed.append(f"{f}: {exc}")
    for line in failed:
        print(f"skipped {line}", file=sys.stderr)
    return calls


def cmd_grade(args) -> int:
    rubric = rubric_mod.load(args.rubric)
    provider = judge_mod.get_provider(args.judge, args.model)
    label = "none (measured checks only)" if provider is None else f"{args.judge} {args.model or judge_mod.DEFAULT_MODELS.get(args.judge, '')}".strip()
    context = Path(args.context).read_text(encoding="utf-8") if args.context else ""
    calls = _load_calls(args.paths, args.platform)
    results = []
    for call in calls:
        r = grade.grade_call(call, rubric, provider, context)
        results.append(r)
        score = f'{r["total"]}/{r["max_total"]} {r["band"]}' if r["total"] is not None else ("ERROR" if r["error"] else "checks only")
        print(f'{call.id:<32} {score:<28} {", ".join(r["flags"]) or "-"}')
    summary = grade.summarize(results, rubric)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (out / "report.html").write_text(report.render(results, summary, rubric, {c.id: c for c in calls}, label), encoding="utf-8")
    print(f"\n{summary['calls']} calls, mean {summary['mean_total']} of {summary['max_total']}, "
          f"{summary['blocked_calls']} blocked, {summary['errors']} judge errors. Report: {out / 'report.html'}")
    if args.fail_on_blocker and summary["blocked_calls"]:
        return 1
    if args.fail_under is not None and (summary["mean_total"] is None or summary["mean_total"] < args.fail_under):
        return 1
    return 0


def cmd_convert(args) -> int:
    call = adapters.load(Path(args.path), args.platform)
    text = json.dumps(call.to_dict(), indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


def cmd_rubrics(args) -> int:
    for name in rubric_mod.presets():
        r = rubric_mod.load(name)
        print(f"{name:<10} {r.title}: {', '.join(d.name for d in r.dimensions)}")
    return 0


def cmd_label_sheet(args) -> int:
    """A blank CSV for blind human scoring. Fill it in without looking at the judge's results."""
    rubric = rubric_mod.load(args.rubric)
    calls = _load_calls(args.paths, args.platform)
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["call_id"] + [d.id for d in rubric.dimensions] + ["notes"])
    for c in calls:
        writer.writerow([c.id] + [""] * len(rubric.dimensions) + [""])
    return 0


def cmd_agree(args) -> int:
    rubric = rubric_mod.load(args.rubric)
    runs = [[json.loads(line) for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip()]
            for f in args.results]
    results = runs[0]
    out = {}
    if args.human:
        out["human_agreement"] = agreement.human_agreement(results, agreement.load_human(Path(args.human)), rubric)
    if args.planted:
        out["planted_failures"] = agreement.planted_detection(results, agreement.load_planted(Path(args.planted)), rubric)
    if len(runs) > 1:
        out["across_runs"] = agreement.across_runs(
            runs, agreement.load_planted(Path(args.planted)) if args.planted else None, rubric)
    if not out:
        sys.exit("pass --human and/or --planted")
    print(json.dumps(out, indent=2))
    if args.min_detection is not None:
        rate = (out.get("planted_failures") or {}).get("detection_rate")
        if len(runs) > 1 and args.planted:  # with repeats, a failure only counts if it was caught every time
            rate = out["across_runs"]["planted_caught_every_run_rate"]
        if rate is None or rate < args.min_detection:
            return 1
    return 0


def _load_runs(files: list[str]) -> list[list[dict]]:
    return [[json.loads(line) for line in Path(f).read_text(encoding="utf-8").splitlines() if line.strip()] for f in files]


def cmd_compare(args) -> int:
    """Before and after a change, over repeat runs: what got fixed, what broke, what is flaky."""
    out = agreement.compare_runs(_load_runs(args.before), _load_runs(args.after))
    print(json.dumps(out, indent=2))
    if args.fail_on_regression and (out["regressed"] or out["missing"]):
        return 1
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="callgrade", description="Grade voice agent calls from any platform.")
    p.add_argument("--version", action="version", version=f"callgrade {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grade", help="grade one or more calls")
    g.add_argument("paths", nargs="+", help="call files or folders of .json files")
    g.add_argument("--platform", default="auto", help="auto, vapi, retell, elevenlabs, bland, bolna or callgrade")
    g.add_argument("--rubric", default="core", help="a preset name or a path to a rubric .yaml")
    g.add_argument("--judge", default="anthropic", help="anthropic, openai or none")
    g.add_argument("--model", help="judge model; defaults to claude-haiku-5-5 for anthropic")
    g.add_argument("--context", help="a text file describing what the agent is supposed to do and what it must never say")
    g.add_argument("--out", default="callgrade-out")
    g.add_argument("--fail-under", type=float, help="exit 1 if the mean total is below this")
    g.add_argument("--fail-on-blocker", action="store_true", help="exit 1 if any call hits a blocker dimension")
    g.set_defaults(fn=cmd_grade)

    c = sub.add_parser("convert", help="convert a platform export to the callgrade format")
    c.add_argument("path")
    c.add_argument("--platform", default="auto")
    c.add_argument("-o", "--output")
    c.set_defaults(fn=cmd_convert)

    r = sub.add_parser("rubrics", help="list the built-in rubrics")
    r.set_defaults(fn=cmd_rubrics)

    ls = sub.add_parser("label-sheet", help="print a blank CSV for blind human scoring")
    ls.add_argument("paths", nargs="+")
    ls.add_argument("--platform", default="auto")
    ls.add_argument("--rubric", default="core")
    ls.set_defaults(fn=cmd_label_sheet)

    cp = sub.add_parser("compare", help="compare runs before and after a change; flaky calls are listed, not failed")
    cp.add_argument("--before", nargs="+", required=True, help="results.jsonl from each baseline run")
    cp.add_argument("--after", nargs="+", required=True, help="results.jsonl from each run after the change")
    cp.add_argument("--fail-on-regression", action="store_true",
                    help="exit 1 if a call that passed every baseline run fails every new run, or is missing")
    cp.set_defaults(fn=cmd_compare)

    a = sub.add_parser("agree", help="measure the judge against human scores, planted failures and its own repeat runs")
    a.add_argument("results", nargs="+",
                   help="results.jsonl from callgrade grade; pass several runs of the same calls to measure consistency")
    a.add_argument("--rubric", default="core")
    a.add_argument("--human", help="filled-in CSV from callgrade label-sheet")
    a.add_argument("--planted", help="jsonl of {call_id, planted: [check:<id> | dim:<id>]}")
    a.add_argument("--min-detection", type=float, help="exit 1 if the planted-failure detection rate is below this")
    a.set_defaults(fn=cmd_agree)

    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except ValueError as exc:
        sys.exit(f"callgrade: {exc}")
