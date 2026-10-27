import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def test_site_data_matches_the_results_on_disk():
    before = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
    run = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_site.py")], capture_output=True, text=True,
                         env={**os.environ, "PYTHONPATH": str(ROOT)})
    assert run.returncode == 0, run.stderr
    after = json.loads((ROOT / "site" / "data.json").read_text(encoding="utf-8"))
    before.pop("commit"), after.pop("commit")
    assert before == after, "site/data.json is stale; run scripts/make_site.py and commit"
    assert len(after["showcase"]) == 3 and all(c["dimensions"] for c in after["showcase"])
    assert after["misses"]["c10"]["score"] == 0
