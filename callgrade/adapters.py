"""Platform exports in, callgrade calls out.

Each adapter follows the platform's published API response for a single call.
`load` sniffs which one a file is, so users can point callgrade at whatever
their platform gave them.

What each platform gives us for timing:

| Platform   | Start | End | Interrupted flag |
|------------|-------|-----|------------------|
| Vapi       | yes   | yes | no               |
| Retell     | yes   | yes (word timings) | no |
| ElevenLabs | yes   | no  | yes              |
| Bland      | yes   | no  | no               |
| Bolna      | no    | no  | no (yes in the debug bundle, start only) |
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .call import Call, Turn

_AGENT = {"agent", "assistant", "bot", "ai"}
_CALLER = {"user", "caller", "customer", "human"}


def _speaker(role: str) -> str | None:
    role = (role or "").strip().lower()
    if role in _AGENT:
        return "agent"
    if role in _CALLER:
        return "caller"
    return None  # system prompts, tool calls, transfer targets: not part of the conversation


def from_vapi(data: dict) -> Call:
    messages = (data.get("artifact") or {}).get("messages") or data.get("messages") or []
    turns = []
    for m in messages:
        speaker = _speaker(m.get("role"))
        text = (m.get("message") or "").strip()
        if not speaker or not text:
            continue
        start = m.get("secondsFromStart")
        # time and endTime are epoch milliseconds, so their difference is unambiguous.
        # duration is documented in seconds; it is only the fallback.
        if start is not None and m.get("time") is not None and m.get("endTime") is not None:
            end = start + (m["endTime"] - m["time"]) / 1000.0
        elif start is not None and m.get("duration") is not None:
            end = start + m["duration"]
        else:
            end = None
        turns.append(Turn(speaker, text, start, end))
    return Call(id=str(data.get("id", "vapi-call")), turns=turns, meta={"platform": "vapi"})


def from_retell(data: dict) -> Call:
    turns = []
    for u in data.get("transcript_object") or []:
        speaker = _speaker(u.get("role"))
        text = (u.get("content") or "").strip()
        if not speaker or not text:
            continue
        words = u.get("words") or []
        start = words[0].get("start") if words else None
        end = words[-1].get("end") if words else None
        turns.append(Turn(speaker, text, start, end))
    return Call(id=str(data.get("call_id", "retell-call")), turns=turns, meta={"platform": "retell"})


def from_elevenlabs(data: dict) -> Call:
    turns = []
    for t in data.get("transcript") or []:
        speaker = _speaker(t.get("role"))
        text = (t.get("message") or "").strip()
        if not speaker or not text:
            continue
        turns.append(Turn(speaker, text, float(t["time_in_call_secs"]) if t.get("time_in_call_secs") is not None else None,
                          None, bool(t.get("interrupted", False))))
    return Call(id=str(data.get("conversation_id", "elevenlabs-call")), turns=turns,
                meta={"platform": "elevenlabs"})


def _iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def from_bland(data: dict) -> Call:
    rows = data.get("transcripts") or []
    origin = data.get("started_at") or (rows[0].get("created_at") if rows else None)
    t0 = _iso(origin) if origin else None
    turns = []
    for r in rows:
        speaker = _speaker(r.get("user"))
        text = (r.get("text") or "").strip()
        if not speaker or not text:
            continue
        start = round((_iso(r["created_at"]) - t0).total_seconds(), 3) if t0 and r.get("created_at") else None
        turns.append(Turn(speaker, text, start if start is None or start >= 0 else 0.0, None))
    return Call(id=str(data.get("call_id", "bland-call")), turns=turns, meta={"platform": "bland"})


_LINE = re.compile(r"^\s*(assistant|user|agent|bot)\s*:\s*(.*)$", re.IGNORECASE)


def from_bolna(data: dict) -> Call:
    debug = (data.get("progression") or {}).get("transcript")
    if debug:  # the debug bundle: per-message timestamps and an interrupted flag
        rows = [r for r in debug if r.get("kind", "message") == "message"]
        t0 = min((r["ts_ms"] for r in rows if r.get("ts_ms") is not None), default=None)
        turns = []
        for r in rows:
            speaker = _speaker(r.get("role"))
            text = (r.get("text") or "").strip()
            if not speaker or not text:
                continue
            start = (r["ts_ms"] - t0) / 1000.0 if t0 is not None and r.get("ts_ms") is not None else None
            turns.append(Turn(speaker, text, start, None, r.get("interrupted")))
        call_id = data.get("execution_id") or (data.get("execution") or {}).get("id") or "bolna-call"
        return Call(id=str(call_id), turns=turns, meta={"platform": "bolna"})

    turns = []
    for line in (data.get("transcript") or "").splitlines():
        m = _LINE.match(line)
        if m and m.group(2).strip():
            turns.append(Turn(_speaker(m.group(1)), m.group(2).strip()))
        elif turns and line.strip():  # a wrapped line continues the previous turn
            turns[-1].text += " " + line.strip()
    return Call(id=str(data.get("id", "bolna-call")), turns=turns, meta={"platform": "bolna"})


ADAPTERS = {
    "vapi": from_vapi,
    "retell": from_retell,
    "elevenlabs": from_elevenlabs,
    "bland": from_bland,
    "bolna": from_bolna,
}


def detect(data: dict) -> str:
    if "turns" in data:
        return "callgrade"
    if "transcript_object" in data:
        return "retell"
    if "transcripts" in data and "concatenated_transcript" in data:
        return "bland"
    if "progression" in data or "telephony_data" in data or "execution_id" in data:
        return "bolna"
    if isinstance(data.get("transcript"), list) and "conversation_id" in data:
        return "elevenlabs"
    if "artifact" in data or ("messages" in data and "orgId" in data):
        return "vapi"
    raise ValueError("could not tell which platform this call came from; pass --platform")


def convert(data: dict, platform: str = "auto") -> Call:
    platform = detect(data) if platform == "auto" else platform
    if platform == "callgrade":
        return Call.from_dict(data)
    if platform not in ADAPTERS:
        raise ValueError(f"unknown platform {platform!r}; known: {', '.join(ADAPTERS)}")
    call = ADAPTERS[platform](data)
    if not call.turns:
        raise ValueError(f"{platform} export has no conversation turns")
    return call


def load(path: Path, platform: str = "auto") -> Call:
    return convert(json.loads(Path(path).read_text(encoding="utf-8")), platform)
