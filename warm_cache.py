#!/usr/bin/env python3
"""Record each preset so the demo survives an exhausted quota.

Judging runs to 16 November. A public URL with no login will be crawled, and
the monthly quota is shared with development. A recorded run is the real
output of this pipeline against the live API, served verbatim and labelled
CACHED -- not a synthetic stand-in.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from engine import run_translation  # noqa: E402

presets = json.loads((HERE / "app" / "presets.json").read_text())["presets"]
out_dir = HERE / "app" / "cache"
out_dir.mkdir(parents=True, exist_ok=True)

for preset in presets:
    try:
        result = run_translation(preset)
    except Exception as exc:
        print("  %-20s FAILED %s: %s" % (preset["id"], type(exc).__name__,
                                         str(exc)[:120]))
        continue
    (out_dir / ("%s.json" % preset["id"])).write_text(json.dumps(result, indent=2))
    answered = len(result.get("markets") or [])
    note = "aborted" if result.get("aborted") else "%d markets" % answered
    print("  %-20s recorded (%s, %d calls)"
          % (preset["id"], note, result["evidence"]["summary"]["calls"]))

# The pitch desk example, recorded so arriving on the page spends no quota.
try:
    from qloo_client import QlooClient
    from taste.evidence import Trace
    from taste.pitch import run as run_pitch
    ex = json.loads((HERE / "app" / "pitch_example_input.json").read_text())
    tr = Trace()
    res = run_pitch(QlooClient(log_name="warm_pitch.jsonl"),
                    ex["slate"], ex["buyer"], ex["home"], trace=tr, with_llm=True)
    res["calls"] = tr.summary()["calls"]
    (out_dir / "pitch_example.json").write_text(json.dumps(res, indent=2))
    print("  %-20s recorded (%d ranked, %d calls)"
          % ("pitch-example", len(res["rows"]), res["calls"]))
except Exception as exc:
    print("  %-20s FAILED %s: %s" % ("pitch-example", type(exc).__name__, str(exc)[:100]))
