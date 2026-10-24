"""The LLM judge: reads the call against the rubric and returns a score and a reason per dimension.

The provider is a single function from (prompt, schema) to a dict, so any model
can sit behind it. Anthropic is the default because structured output there
guarantees the verdict parses; any OpenAI-compatible endpoint (OpenAI, Groq,
Together, a local server) works through `openai`.

The judge never sees the platform's own analysis or summary, only the turns,
the measured checks and the optional context the team supplies. A judge that
reads another model's summary is grading the summary.
"""
from __future__ import annotations

import json
import os
from typing import Callable

from .call import Call
from .checks import CheckResult
from .rubric import Rubric

DEFAULT_MODELS = {"anthropic": "claude-haiku-5-5"}

Provider = Callable[[str, dict], dict]


class JudgeError(RuntimeError):
    pass


def render_transcript(call: Call) -> str:
    lines = []
    for i, t in enumerate(call.turns, 1):
        stamp = f"[{t.start:7.1f}s] " if t.start is not None else ""
        flag = " (cut off)" if t.interrupted else ""
        lines.append(f"{i:>3}. {stamp}{t.speaker.upper()}: {t.text}{flag}")
    return "\n".join(lines)


def render_checks(checks: list[CheckResult]) -> str:
    rows = []
    for c in checks:
        where = f" at turn(s) {', '.join(str(i + 1) for i in c.turns)}" if c.turns else ""
        rows.append(f"- {c.name}: {c.status}, {c.detail}{where}")
    return "\n".join(rows)


def build_prompt(call: Call, rubric: Rubric, checks: list[CheckResult], context: str = "") -> str:
    dims = []
    for d in rubric.dimensions:
        levels = "\n".join(f"    {score}: {text}" for score, text in sorted(d.levels.items(), reverse=True))
        dims.append(f"- {d.id} ({d.name}): {d.question}\n{levels}")
    ctx = f"\nWHAT THE AGENT IS SUPPOSED TO DO (supplied by the team):\n{context.strip()}\n" if context.strip() else ""
    return f"""You are grading one phone call handled by an AI voice agent. Grade the AGENT, not the caller.
{ctx}
RUBRIC ({rubric.title}, each dimension scored {rubric.min} to {rubric.max}):
{chr(10).join(dims)}

MEASURED FROM THE CALL'S TIMESTAMPS (these are facts, do not second-guess them):
{render_checks(checks)}

TRANSCRIPT (turns are numbered; times are seconds from the start of the call when known):
{render_transcript(call)}

How to grade:
- Judge only from the transcript, the measured facts and the supplied context. Do not assume anything happened off the call.
- For each dimension, write the reason first, then pick the level whose description fits best. Cite turn numbers.
- A polite or fluent agent can still fail a dimension. Do not reward tone when the substance is wrong.
- If something the agent said is not supported by the supplied context and would mislead the caller, treat it as an invented fact.
- If a dimension never came up in this call (for example the caller never interrupted), set applicable to false and score it {rubric.max}.
"""


def verdict_schema(rubric: Rubric) -> dict:
    ids = [d.id for d in rubric.dimensions]
    return {
        "type": "object",
        "properties": {
            "dimensions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "enum": ids},
                        "reason": {"type": "string"},
                        "evidence_turns": {"type": "array", "items": {"type": "integer"}},
                        "applicable": {"type": "boolean"},
                        "score": {"type": "integer", "enum": list(range(rubric.min, rubric.max + 1))},
                    },
                    "required": ["id", "reason", "evidence_turns", "applicable", "score"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["dimensions"],
        "additionalProperties": False,
    }


def validate(verdict: dict, rubric: Rubric) -> dict[str, dict]:
    """Every dimension exactly once, every score in range. Anything else is a judge failure, not a score."""
    out = {}
    for row in verdict.get("dimensions", []):
        dim_id = row.get("id")
        if dim_id in out:
            raise JudgeError(f"judge scored {dim_id!r} twice")
        score = row.get("score")
        if not isinstance(score, int) or not rubric.min <= score <= rubric.max:
            raise JudgeError(f"judge gave {dim_id!r} an out-of-range score {score!r}")
        out[dim_id] = row
    missing = [d.id for d in rubric.dimensions if d.id not in out]
    if missing:
        raise JudgeError(f"judge skipped {', '.join(missing)}")
    unknown = set(out) - {d.id for d in rubric.dimensions}
    if unknown:
        raise JudgeError(f"judge invented dimensions {', '.join(sorted(unknown))}")
    return out


def anthropic_provider(model: str) -> Provider:
    import anthropic

    client = anthropic.Anthropic()

    def call(prompt: str, schema: dict) -> dict:
        response = client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        if response.stop_reason == "refusal":
            raise JudgeError("the judge model declined to grade this call")
        if response.stop_reason == "max_tokens":
            raise JudgeError("the judge ran out of tokens before finishing its verdict")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise JudgeError("the judge returned no verdict")
        return json.loads(text)

    return call


def openai_provider(model: str) -> Provider:
    from openai import OpenAI

    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)

    def call(prompt: str, schema: dict) -> dict:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_schema", "json_schema": {"name": "verdict", "schema": schema, "strict": True}},
        )
        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise JudgeError("the judge model declined to grade this call")
        return json.loads(choice.message.content)

    return call


def get_provider(name: str, model: str | None = None) -> Provider | None:
    if name == "none":
        return None
    if name == "anthropic":
        return anthropic_provider(model or DEFAULT_MODELS["anthropic"])
    if name == "openai":
        if not model:
            raise ValueError("--judge openai needs --model (any model your endpoint serves)")
        return openai_provider(model)
    raise ValueError(f"unknown judge {name!r}; use anthropic, openai or none")


def grade(call: Call, rubric: Rubric, checks: list[CheckResult], provider: Provider, context: str = "") -> dict[str, dict]:
    prompt = build_prompt(call, rubric, checks, context)
    return validate(provider(prompt, verdict_schema(rubric)), rubric)
