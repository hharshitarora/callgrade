import subprocess
import sys
from pathlib import Path

from callgrade import adapters, agreement, grade, rubric

ROOT = Path(__file__).parent.parent


def test_committed_testset_matches_the_generator():
    before = {p.name: p.read_text() for p in (ROOT / "examples" / "calls").glob("*.json")}
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_testset.py")], check=True, capture_output=True)
    after = {p.name: p.read_text() for p in (ROOT / "examples" / "calls").glob("*.json")}
    assert before == after, "examples/calls is stale; run scripts/make_testset.py and commit"


def test_timing_failures_are_caught_with_no_judge_and_clean_calls_raise_nothing():
    core = rubric.load("core")
    calls = [adapters.load(p) for p in sorted((ROOT / "examples" / "calls").glob("*.json"))]
    results = [grade.grade_call(c, core) for c in calls]
    out = agreement.planted_detection(results, agreement.load_planted(ROOT / "examples" / "planted.jsonl"), core)
    assert out["missed"] == [] and out["caught"] >= 3
    assert out["false_alarms_on_clean_calls"] == []
