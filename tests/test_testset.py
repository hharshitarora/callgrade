import subprocess
import sys
from pathlib import Path

import pytest

from callgrade import adapters, agreement, grade, rubric

ROOT = Path(__file__).parent.parent


SETS = [ROOT / "examples", ROOT / "examples" / "holdout"]


def test_committed_testsets_match_the_generator():
    def snapshot():
        return {str(p.relative_to(ROOT)): p.read_text() for s in SETS for p in (s / "calls").glob("*.json")}
    before = snapshot()
    subprocess.run([sys.executable, str(ROOT / "scripts" / "make_testset.py")], check=True, capture_output=True)
    assert before == snapshot(), "examples/ is stale; run scripts/make_testset.py and commit"


@pytest.mark.parametrize("folder", SETS, ids=["dev", "holdout"])
def test_timing_failures_are_caught_with_no_judge_and_clean_calls_raise_nothing(folder):
    core = rubric.load("core")
    calls = [adapters.load(p) for p in sorted((folder / "calls").glob("*.json"))]
    results = [grade.grade_call(c, core) for c in calls]
    out = agreement.planted_detection(results, agreement.load_planted(folder / "planted.jsonl"), core)
    assert out["missed"] == [] and out["caught"] >= 3
    assert out["false_alarms_on_clean_calls"] == []
