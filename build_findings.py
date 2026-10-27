#!/usr/bin/env python3
"""Freeze the harness's own verdicts into something the evidence page serves.

The page used to describe measurements in prose. Prose drifts from the data
and reads like it was written rather than measured -- and in at least two
places it had drifted into claiming more than out/results.json supports. This
copies the harness output, verdicts and all, into app/cache/findings.json so
the page renders the actual result, including the tests that did not resolve.

    python3 build_findings.py        (after python3 run_all.py --only qloo)
"""
from __future__ import annotations

import datetime
import json
import pathlib

HERE = pathlib.Path(__file__).parent
R = json.loads((HERE / "out" / "results.json").read_text())["qloo"]

# Every differential test, with the claim it does or does not support. The
# claim is ours; the verdict and the numbers are the harness's.
TESTS = [
    {"id": "F0", "name": "Which location parameter actually bites",
     "claim": "filter.location.query is ignored for movies; signal.location.query is not",
     "verdict": R["F0_location_param"].get("verdict"),
     "how": "python3 run_all.py",
     "matrix": R["F0_location_param"]["per_param"]},
    {"id": "C", "name": "Does filter.results.entities score the list I pinned",
     "claim": "a pinned candidate set is honoured, so rank positions are comparable",
     "verdict": R["C_results_entities"].get("verdict"),
     "how": "python3 run_all.py",
     "detail": {"requested": R["C_results_entities"].get("requested"),
                "returned": R["C_results_entities"].get("returned"),
                "unrequested": len(R["C_results_entities"].get("unrequested_returned") or [])}},
    {"id": "A2", "name": "Is the API deterministic",
     "claim": "the same query twice returns the same answer",
     "verdict": R["A2_determinism"].get("verdict"),
     "how": "python3 run_all.py",
     "detail": {"first": R["A2_determinism"].get("results_first"),
                "second": R["A2_determinism"].get("results_second")}},
    {"id": "B", "name": "Is affinity normalised per candidate set",
     "claim": "we do not know, and the product does not rely on it",
     "verdict": R["B_normalisation"].get("verdict"),
     "how": "python3 run_all.py",
     "note": R["B_normalisation"].get("note")},
    {"id": "D", "name": "Are invalid parameters silently ignored",
     "claim": "a 200 is not evidence a parameter was applied",
     "verdict": R["D_silent_ignore"].get("verdict"),
     "how": "python3 run_all.py",
     "note": R["D_silent_ignore"].get("note"),
     "detail": {"nonsense_param_ignored": R["D_silent_ignore"].get("nonsense_param_ignored"),
                "positive_control_moved": R["D_silent_ignore"].get("positive_control_changed_results")}},
    {"id": "E", "name": "Does the insights response carry explainability",
     "claim": "absent on this query shape; present when asked for per-entity contributions",
     "verdict": R["E_explainability"].get("verdict"),
     "how": "python3 run_all.py",
     "note": ("Returned nothing on the harness's query shape. feature.explainability "
              "does return per-entity contributions on the shape the hero uses, which "
              "is how the landing page names its drivers; the two disagree and the "
              "harness verdict is reported as it stands.")},
]

out = {
    "measured_at": datetime.date.today().isoformat(),
    "endpoint": "https://hackathon.api.qloo.com",
    "tests": TESTS,
    "verdict_counts": {},
}
for t in TESTS:
    v = t["verdict"] or "UNKNOWN"
    out["verdict_counts"][v] = out["verdict_counts"].get(v, 0) + 1

(HERE / "app" / "cache" / "findings.json").write_text(json.dumps(out, indent=2))
print("wrote app/cache/findings.json")
for t in TESTS:
    print("  %-3s %-52s %s" % (t["id"], t["name"][:52], t["verdict"]))
