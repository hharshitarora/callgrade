"""Pull call history from a Bolna account into private/bolna/, one file per call.

Reads BOLNA_API_KEY from the environment (or .env). Saves the raw execution
and, when available, the debug bundle with per-message timestamps, which is
what the Bolna adapter needs for timing checks. private/ is gitignored: real
calls never go into the repo.

    python scripts/fetch_bolna.py            # every agent, every call since the agent was created
    python scripts/fetch_bolna.py --limit 20
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "private" / "bolna"
API = "https://api.bolna.ai"


def key() -> str:
    k = os.environ.get("BOLNA_API_KEY")
    if not k and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith("BOLNA_API_KEY="):
                k = line.split("=", 1)[1].strip().strip('"')
    if not k:
        sys.exit("BOLNA_API_KEY not set")
    return k


def get(path: str, k: str):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {k}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "_body": e.read().decode("utf-8", "replace")[:300]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500, help="calls per agent, newest first")
    args = ap.parse_args()
    k = key()
    agents = get("/v2/agent/all", k)
    if isinstance(agents, dict) and agents.get("_error"):
        agents = get("/agent/all", k)
    if isinstance(agents, dict):
        sys.exit(f"could not list agents: {agents}")
    print(f"{len(agents)} agents")
    for a in agents:
        aid, name = a["id"], a.get("agent_name", "")
        folder = OUT / aid
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "agent.json").write_text(json.dumps(a, indent=1), encoding="utf-8")
        # v2 only answers for a window of at most 7 days, so walk back from today to the
        # agent's creation one week at a time. v1 (/agent/{id}/executions) returns at most 100.
        execs, seen = [], set()
        start = datetime.fromisoformat(a["created_at"].split(".")[0]).replace(tzinfo=timezone.utc)
        hi = datetime.now(timezone.utc)
        while hi > start and len(execs) < args.limit:
            lo = max(start, hi - timedelta(days=7))
            page = 1
            while True:
                q = f"from={lo:%Y-%m-%dT%H:%M:%SZ}&to={hi:%Y-%m-%dT%H:%M:%SZ}&page_size=50&page_number={page}"
                res = get(f"/v2/agent/{aid}/executions?{q}", k)
                if not isinstance(res, dict) or res.get("_error"):
                    print(f"  {name}: executions error {res}")
                    break
                for e in res.get("data", []):
                    if e["id"] not in seen:
                        seen.add(e["id"]); execs.append(e)
                if not res.get("has_more"):
                    break
                page += 1
            hi = lo
        execs = execs[: args.limit]
        done = sum(1 for e in execs if e.get("status") == "completed")
        print(f"  {name} ({aid[:8]}): {len(execs)} executions, {done} completed")
        for e in execs:
            eid = e["id"]
            full = get(f"/executions/{eid}", k)
            (folder / f"{eid}.json").write_text(json.dumps(full, indent=1), encoding="utf-8")
            debug = get(f"/executions/{eid}/debug?include=execution,progression", k)
            if isinstance(debug, dict) and not debug.get("_error"):
                (folder / f"{eid}.debug.json").write_text(json.dumps(debug, indent=1), encoding="utf-8")
    print(f"saved under {OUT}")


if __name__ == "__main__":
    main()
