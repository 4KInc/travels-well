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
     "claim": "filter.location.query is ignored for movies, signal.location.query is not",
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
     "claim": "the same entity scores identically inside two different candidate sets",
     "verdict": R["B_normalisation"].get("verdict"),
     "how": "python3 run_all.py",
     "note": R["B_normalisation"].get("note")},
    {"id": "D", "name": "Are invalid parameters silently ignored",
     "claim": "yes, and a 200 is not evidence a parameter was applied",
     "verdict": R["D_silent_ignore"].get("verdict"),
     "how": "python3 run_all.py",
     "note": R["D_silent_ignore"].get("note"),
     "detail": {"nonsense_param_ignored": R["D_silent_ignore"].get("nonsense_param_ignored"),
                "positive_control": R["D_silent_ignore"].get("positive_control"),
                "positive_control_moved": R["D_silent_ignore"].get("positive_control_changed_results")}},
    {"id": "E", "name": "Does the insights response carry explainability",
     "claim": "returned on both the open and the pinned query shape",
     "verdict": R["E_explainability"].get("verdict"),
     "how": "python3 run_all.py",
     "note": ("Read as ABSENT until 2026-10-30, which was a fault in this test "
              "rather than in the API. It searched for the substring 'explain' in "
              "the first 4000 characters of each result, and a film entity carries "
              "enough metadata to push query.explainability past that cut. It now "
              "reads the documented field, the same one the landing page reads to "
              "name its drivers."),
     # Flat scalars only: the page joins detail values into one line, so a
     # nested dict renders as [object Object].
     "detail": {
         "open query": "%s (%s results)" % (
             (R["E_explainability"].get("open_query") or {}).get("explainability"),
             (R["E_explainability"].get("open_query") or {}).get("results")),
         "pinned query": "%s (%s results)" % (
             (R["E_explainability"].get("pinned_query") or {}).get("explainability"),
             (R["E_explainability"].get("pinned_query") or {}).get("results"))}},
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
