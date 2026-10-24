from callgrade import checks
from callgrade.call import Call, Turn


def call(*turns):
    return Call("t", [Turn(*t) for t in turns])


def test_clean_timed_call_passes_everything():
    c = call(("agent", "hi", 0.0, 1.0), ("caller", "hello", 1.6, 2.4), ("agent", "great", 3.2, 4.0))
    assert {r.id: r.status for r in checks.run(c)} == {
        "reply_latency": "pass", "talk_over": "pass", "dead_air": "pass", "barge_ins": "pass"}


def test_slow_reply_points_at_the_agent_turn():
    c = call(("caller", "hello", 0.0, 1.0), ("agent", "hi", 5.0, 6.0))
    r = checks.reply_latency(c, 3.0)
    assert r.status == "fail" and r.turns == [1] and r.value == 4.0


def test_talk_over_needs_more_than_the_tolerance():
    near = call(("caller", "hello there", 0.0, 2.0), ("agent", "hi", 1.7, 2.5))
    over = call(("caller", "hello there", 0.0, 2.0), ("agent", "hi", 1.0, 2.5))
    assert checks.talk_over(near, 0.5).status == "pass"
    assert checks.talk_over(over, 0.5).status == "fail"


def test_dead_air_counts_any_long_gap():
    c = call(("caller", "one", 0.0, 1.0), ("caller", "hello?", 9.5, 10.0))
    assert checks.dead_air(c, 7.0).status == "fail"


def test_untimed_call_is_unmeasured_not_passed():
    c = call(("agent", "hi"), ("caller", "hello"))
    assert {r.status for r in checks.run(c)} == {"unmeasured"}


def test_thresholds_are_configurable():
    c = call(("caller", "hello", 0.0, 1.0), ("agent", "hi", 5.0, 5.5))
    assert checks.run(c)[0].status == "fail"
    assert checks.run(c, {"slow_reply_secs": 5.0})[0].status == "pass"
