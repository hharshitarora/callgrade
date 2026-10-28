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
        result("bad3", {**full, "intent": 1}),  # marked down but not flagged: still a miss
        result("slow", checks=[("reply_latency", "fail")]),
        result("clean", {**full, "intent": 0}),  # a false alarm
    ]
    planted = {"bad1": ["dim:guardrails"], "bad2": ["dim:intent"], "bad3": ["dim:intent"], "slow": ["check:reply_latency"], "clean": []}
    out = agreement.planted_detection(results, planted, core)
    assert out["caught"] == 2 and out["missed"] == ["bad2 dim:intent", "bad3 dim:intent"]
    assert out["missed_but_marked_down"] == ["bad3 dim:intent"]
    assert out["detection_rate"] == 0.5
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


def test_wilson_interval_is_a_range_even_at_a_perfect_score():
    assert agreement.wilson(11, 11) == [0.741, 1.0]
    assert agreement.wilson(0, 10) == [0.0, 0.278]
    assert agreement.wilson(0, 0) is None


def test_across_runs_counts_a_failure_only_if_caught_every_time():
    core = rubric.load("core")
    full = {d.id: 2 for d in core.dimensions}
    run1 = [result("bad", {**full, "intent": 0}), result("clean", full)]
    run2 = [result("bad", {**full, "intent": 1}), result("clean", full)]
    out = agreement.across_runs([run1, run2], {"bad": ["dim:intent"], "clean": []}, core)
    assert out["planted_detection_rate_per_run"] == [1.0, 0.0]
    assert out["planted_caught_every_run"] == "0 of 1" and out["planted_missed_in_some_run"] == ["bad dim:intent"]
    assert out["identical_by_dimension"]["intent"] == 0.5 and out["identical_by_dimension"]["guardrails"] == 1.0
    assert out["scores_identical_in_every_run"] == 0.9


def test_compare_runs_fails_only_on_always_pass_to_always_fail():
    ok = lambda c: {"call_id": c, "flags": [], "dimensions": {"intent": {"score": 2}}}
    bad = lambda c: {"call_id": c, "flags": ["low:intent"], "dimensions": {"intent": {"score": 0}}}
    before = [[ok("a"), ok("b"), bad("c"), ok("d")], [ok("a"), ok("b"), bad("c"), bad("d")]]
    after = [[bad("a"), ok("b"), ok("c"), ok("d")], [bad("a"), bad("b"), ok("c"), ok("d")]]
    out = agreement.compare_runs(before, after)
    assert out["regressed"] == ["a"]          # passed every run, now fails every run
    assert out["now_flaky"] == ["b"]          # fails in one new run: listed, not a regression
    assert out["fixed"] == ["c"]
    assert out["flaky_before"] == ["d"] and "d" not in out["regressed"]
    assert out["missing"] == []
    assert out["pass_rate_before"] == 0.625 and out["pass_rate_after"] == 0.625
    gone = agreement.compare_runs(before, [[ok("a"), ok("b"), ok("c")]])
    assert gone["missing"] == ["d"]
