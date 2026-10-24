"""The one call format everything else reads.

Every platform exports calls differently. Adapters convert each export into
this shape once, so the checks and the judge never know which platform a call
came from.

Times are seconds from the start of the call. They are optional because some
platforms only record when a turn started, and some record nothing at all. A
check that needs a time it does not have reports itself as unmeasured instead
of guessing.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

SPEAKERS = ("agent", "caller")


@dataclass
class Turn:
    speaker: str
    text: str
    start: float | None = None
    end: float | None = None
    interrupted: bool | None = None  # the platform says this turn was cut off

    def __post_init__(self):
        if self.speaker not in SPEAKERS:
            raise ValueError(f"speaker must be one of {SPEAKERS}, got {self.speaker!r}")
        if self.start is not None and self.end is not None and self.end < self.start:
            raise ValueError(f"turn ends before it starts: {self.start} > {self.end}")


@dataclass
class Call:
    id: str
    turns: list[Turn]
    meta: dict = field(default_factory=dict)

    @property
    def timed(self) -> bool:
        return all(t.start is not None and t.end is not None for t in self.turns)

    def to_dict(self) -> dict:
        return {"id": self.id, "meta": self.meta, "turns": [asdict(t) for t in self.turns]}

    @classmethod
    def from_dict(cls, data: dict) -> "Call":
        if "turns" not in data:
            raise ValueError("not a callgrade call: missing 'turns'")
        turns = [Turn(**t) for t in data["turns"]]
        return cls(id=str(data.get("id") or "call"), turns=turns, meta=data.get("meta") or {})

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
