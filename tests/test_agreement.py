from callgrade import agreement, rubric


def test_kappa_perfect_chance_and_constant():
    assert agreement.weighted_kappa([0, 1, 2, 2], [0, 1, 2, 2], 0, 2) == 1.0
    assert agreement.weighted_kappa([2, 2, 2], [2, 2, 2], 0, 2) == 1.0
    assert agreement.weighted_kappa([0, 2, 0, 2], [2, 0, 2, 0], 0, 2) < 0


def test_kappa_punishes_big_misses_more_than_small_ones():
    near = agreement.weighted_kappa([0, 1, 2, 1, 2, 0], [1, 1, 2, 1, 2, 0], 0, 2)
    far = agreement.weighted_kappa([0, 1, 2, 1, 2, 0], [2, 1, 2, 1, 2, 0], 0, 2)
    assert near > far


def result(call_id, scores=None, checks=()):
    return {"call_id": call_id, "dimensions": {k: {"score": v} for k, v in (scores or {}).items()} or None,
            "checks": [{"id": i, "status": s} for i, s in checks],
            "flags": [f"low:{k}" for k, v in (scores or {}).items() if v == 0] + [f"check:{i}" for i, s in checks if s == "fail"]}


def test_planted_detection_and_false_alarms():
    core = rubric.load("core")
    full = {d.id: 2 for d in core.dimensions}
    results = [
        result("bad1", {**full, "guardrails": 0}),
        result("bad2", full),  # a planted failure the judge missed
        result("slow", checks=[("reply_latency", "fail")]),
        result("clean", {**full, "intent": 0}),  # a false alarm
    ]
    planted = {"bad1": ["dim:guardrails"], "bad2": ["dim:intent"], "slow": ["check:reply_latency"], "clean": []}
    out = agreement.planted_detection(results, planted, core)
    assert out["caught"] == 2 and out["missed"] == ["bad2 dim:intent"]
    assert out["detection_rate"] == round(2 / 3, 3)
    assert out["false_alarms_on_clean_calls"] == ["clean low:intent"]


def test_human_agreement_per_dimension(tmp_path):
    core = rubric.load("core")
    sheet = tmp_path / "h.csv"
    sheet.write_text("call_id,intent,understanding,interruptions,guardrails,completion,notes\n"
                     "a,2,2,2,0,2,\nb,1,2,2,2,,unsure\n")
    full = {d.id: 2 for d in core.dimensions}
    results = [result("a", {**full, "guardrails": 0}), result("b", full)]
    out = agreement.human_agreement(results, agreement.load_human(sheet), core)
    assert out["guardrails"]["exact"] == 1.0 and out["intent"]["exact"] == 0.5
    assert out["completion"]["n"] == 1
