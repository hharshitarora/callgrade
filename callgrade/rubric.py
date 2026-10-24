"""Rubrics are YAML so a team can change what "good" means without touching code."""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

import yaml


@dataclass
class Dimension:
    id: str
    name: str
    question: str
    levels: dict[int, str]
    blocker: bool = False  # a minimum score here fails the call whatever the total


@dataclass
class Rubric:
    name: str
    title: str
    min: int
    max: int
    dimensions: list[Dimension]
    bands: list[tuple[int, str]] = field(default_factory=list)

    @property
    def max_total(self) -> int:
        return self.max * len(self.dimensions)

    def band(self, total: int) -> str:
        for floor, label in self.bands:
            if total >= floor:
                return label
        return ""

    def dimension(self, dim_id: str) -> Dimension:
        for d in self.dimensions:
            if d.id == dim_id:
                return d
        raise KeyError(dim_id)


def parse(data: dict) -> Rubric:
    scale = data.get("scale") or {"min": 0, "max": 2}
    lo, hi = int(scale["min"]), int(scale["max"])
    dims = []
    for d in data["dimensions"]:
        levels = {int(k): str(v).strip() for k, v in d["levels"].items()}
        if set(levels) != set(range(lo, hi + 1)):
            raise ValueError(f"dimension {d['id']!r} must describe every level {lo}..{hi}")
        dims.append(Dimension(d["id"], d["name"], d["question"].strip(), levels, bool(d.get("blocker", False))))
    if len({d.id for d in dims}) != len(dims):
        raise ValueError("dimension ids must be unique")
    bands = sorted(((int(b["min"]), b["label"]) for b in data.get("bands") or []), reverse=True)
    return Rubric(data["name"], data.get("title", data["name"]), lo, hi, dims, bands)


def presets() -> list[str]:
    return sorted(p.name[:-5] for p in resources.files("callgrade.rubrics").iterdir() if p.name.endswith(".yaml"))


def load(name_or_path: str) -> Rubric:
    path = Path(name_or_path)
    if path.suffix in {".yaml", ".yml"} and path.exists():
        text = path.read_text(encoding="utf-8")
    elif name_or_path in presets():
        text = (resources.files("callgrade.rubrics") / f"{name_or_path}.yaml").read_text(encoding="utf-8")
    else:
        raise ValueError(f"no rubric {name_or_path!r}; presets: {', '.join(presets())}, or pass a .yaml path")
    return parse(yaml.safe_load(text))
