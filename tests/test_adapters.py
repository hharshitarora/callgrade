import json
from pathlib import Path

import pytest

from callgrade import adapters, checks

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return adapters.load(FIX / name)


def test_detects_every_platform():
    for name, platform in [("vapi.json", "vapi"), ("retell.json", "retell"), ("elevenlabs.json", "elevenlabs"),
                           ("bland.json", "bland"), ("bolna.json", "bolna"), ("bolna-debug.json", "bolna")]:
        assert adapters.detect(json.loads((FIX / name).read_text())) == platform


def test_vapi_drops_system_and_tool_messages_and_keeps_times():
    call = load("vapi.json")
    assert [t.speaker for t in call.turns] == ["agent", "caller", "agent"]
    assert call.turns[1].start == 4.1 and call.turns[1].end == pytest.approx(5.1)
    assert checks.reply_latency(call, 3.0).status == "fail"  # 9.6 - 5.1 = 4.5s


def test_retell_word_timings_catch_talk_over():
    call = load("retell.json")
    assert [t.speaker for t in call.turns] == ["agent", "caller", "agent"]  # transfer_target dropped
    assert (call.turns[1].start, call.turns[1].end) == (2.5, 3.9)
    assert checks.talk_over(call, 0.5).status == "fail"


def test_elevenlabs_has_starts_and_interruptions_but_no_ends():
    call = load("elevenlabs.json")
    assert len(call.turns) == 3  # the tool-only turn has no message
    assert call.turns[0].interrupted is True and call.turns[0].end is None
    results = {c.id: c.status for c in checks.run(call)}
    assert results["reply_latency"] == "unmeasured" and results["barge_ins"] == "pass"


def test_bland_times_are_relative_to_call_start():
    call = load("bland.json")
    assert [t.speaker for t in call.turns] == ["agent", "caller"]  # agent-action dropped
    assert call.turns[0].start == 1.5 and call.turns[1].start == 4.0


def test_bolna_plain_transcript_joins_wrapped_lines():
    call = load("bolna.json")
    assert [t.speaker for t in call.turns] == ["agent", "caller", "agent", "caller"]
    assert call.turns[2].text == "When are you hoping to move? Ideally soon?"
    assert all(c.status == "unmeasured" for c in checks.run(call))


def test_bolna_debug_bundle_keeps_interrupted_and_relative_times():
    call = load("bolna-debug.json")
    assert [(t.speaker, t.start, t.interrupted) for t in call.turns] == [("agent", 0.0, True), ("caller", 1.5, False)]


def test_unknown_export_is_rejected():
    with pytest.raises(ValueError):
        adapters.convert({"hello": "world"})


def test_roundtrip_through_callgrade_format(tmp_path):
    call = load("vapi.json")
    call.save(tmp_path / "c.json")
    again = adapters.load(tmp_path / "c.json")
    assert again.to_dict() == call.to_dict()
