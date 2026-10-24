from pathlib import Path

import pytest

from callgrade import adapters, grade, judge, rubric
from callgrade.checks import run as run_checks

CALLS = Path(__file__).parent.parent / "examples" / "calls"


def fake(scores, applicable=True):
    def provider(prompt, schema):
        return {"dimensions": [{"id": k, "reason": f"because {k}", "evidence_turns": [2], "applicable": applicable, "score": v}
                               for k, v in scores.items()]}
    return provider


@pytest.fixture
def core():
    return rubric.load("core")


def test_presets_load_and_describe_every_level():
    for name in rubric.presets():
        r = rubric.load(name)
        assert all(set(d.levels) == {0, 1, 2} for d in r.dimensions)


def test_prompt_numbers_turns_and_carries_checks_and_context(core):
    call = adapters.load(CALLS / "p01-slow-replies.json")
    prompt = judge.build_prompt(call, core, run_checks(call), "Never promise approval.")
    assert "  1. [" in prompt and "AGENT:" in prompt and "CALLER:" in prompt
    assert "Reply latency: fail" in prompt
    assert "Never promise approval." in prompt


def test_schema_only_allows_rubric_ids_and_scores(core):
    s = judge.verdict_schema(core)["properties"]["dimensions"]["items"]["properties"]
    assert s["id"]["enum"] == [d.id for d in core.dimensions]
    assert s["score"]["enum"] == [0, 1, 2]


def test_grade_call_totals_bands_and_blockers(core):
    call = adapters.load(CALLS / "p06-invented-refund.json")
    r = grade.grade_call(call, core, fake({"intent": 2, "understanding": 2, "interruptions": 2, "guardrails": 0, "completion": 2}))
    assert r["total"] == 8 and r["band"] == "minor tweaks"
    assert "blocker:guardrails" in r["flags"]


def test_judge_that_skips_a_dimension_is_an_error_not_a_score(core):
    call = adapters.load(CALLS / "c01-viewing-booked.json")
    r = grade.grade_call(call, core, fake({"intent": 2}))
    assert r["total"] is None and "skipped" in r["error"]


def test_duplicate_and_out_of_range_scores_are_rejected(core):
    with pytest.raises(judge.JudgeError):
        judge.validate({"dimensions": [{"id": "intent", "score": 2}, {"id": "intent", "score": 1}]}, core)
    with pytest.raises(judge.JudgeError):
        judge.validate({"dimensions": [{"id": d.id, "score": 3} for d in core.dimensions]}, core)


def test_openai_judge_requires_a_model():
    with pytest.raises(ValueError):
        judge.get_provider("openai")
