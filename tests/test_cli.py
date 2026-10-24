import json
from pathlib import Path

from callgrade import cli, judge

ROOT = Path(__file__).parent.parent


def test_grade_writes_results_summary_and_report(tmp_path):
    code = cli.main(["grade", str(ROOT / "examples" / "calls"), "--judge", "none", "--out", str(tmp_path)])
    assert code == 0
    results = [json.loads(line) for line in (tmp_path / "results.jsonl").read_text().splitlines()]
    assert len(results) == 20
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert html.startswith("<!doctype html>") and "p01-slow-replies" in html


def test_fail_on_blocker_sets_exit_code(tmp_path, monkeypatch):
    def provider(prompt, schema):
        ids = schema["properties"]["dimensions"]["items"]["properties"]["id"]["enum"]
        return {"dimensions": [{"id": i, "reason": "r", "evidence_turns": [], "applicable": True,
                                "score": 0 if i == "guardrails" else 2} for i in ids]}
    monkeypatch.setattr(judge, "get_provider", lambda name, model=None: provider)
    code = cli.main(["grade", str(ROOT / "examples" / "calls" / "p10-guarantees-approval.json"),
                     "--out", str(tmp_path), "--fail-on-blocker"])
    assert code == 1


def test_label_sheet_lists_every_call(capsys):
    cli.main(["label-sheet", str(ROOT / "examples" / "calls")])
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines[0].startswith("call_id,intent,") and len(lines) == 21
