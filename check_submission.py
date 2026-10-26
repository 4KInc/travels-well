"""Does the submission text still match what the site says?

The numbers in docs/SUBMISSION.md and the numbers on /evidence come from the
same recorded run, so they can drift apart only by someone editing the prose.
This asserts they have not, and that phrasing we retired has not come back.

Run: python3 check_submission.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
RAW = (HERE / "docs" / "SUBMISSION.md").read_text()
# Normalise typography before comparing numbers: the prose uses a real minus
# sign and real dashes, which should not count as a mismatch against a value
# formatted with an ASCII hyphen.
DOC = (RAW.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "--")
          .replace("\u00a0", " "))
HERO = json.loads((HERE / "app" / "cache" / "hero.json").read_text())

bad = []


def must(label, cond):
    print(("  ok    " if cond else "  WRONG ") + label)
    if not cond:
        bad.append(label)


print("numbers in SUBMISSION.md against the recorded run")
t = HERO["llm_tau"]
overlap = len(HERO["shared_top5"])
places = {r["title"]: r["grounded_place"] for r in HERO["llm_only_ranks"]}

must("top-five overlap (%d of 5)" % overlap,
     "%d of 5" % overlap in DOC)
must("rank correlation %.2f" % t["min"],
     ("%.2f" % t["min"]) in DOC or ("%.3f" % t["min"]) in DOC)
must("null standard error %.2f" % t["null_se"],
     ("%.2f" % t["null_se"]) in DOC)
must("titles ranked (%d)" % HERO["ranked_total"],
     "of %d" % HERO["ranked_total"] in DOC)
must("top-five hold (%d of 5)" % HERO["buyer"]["top5_hold"],
     "%d of 5" % HERO["buyer"]["top5_hold"] in DOC)
must("sweep size (%d pairs)" % HERO["provenance"]["pairs_evaluated"],
     str(HERO["provenance"]["pairs_evaluated"]) in DOC)
must("sweep qualifiers (%d)" % HERO["provenance"]["pairs_qualified"],
     str(HERO["provenance"]["pairs_qualified"]) in DOC)
# EVERY placement, not the ones that flatter us. Quoting only the lowest
# three dropped the model's best-placed pick, which anyone opening /evidence
# would see immediately.
_ordinals = []
for title, place in sorted(places.items(), key=lambda kv: kv[1] or 99):
    must("placement of %s (%d) appears" % (title, place), str(place) in DOC)
    if place:
        _ordinals.append("%d%s" % (place, "th" if 11 <= place % 100 <= 13
                                   else {1: "st", 2: "nd", 3: "rd"}.get(place % 10, "th")))
_flat = re.sub(r"\s+", " ", DOC)
must("the headline lists all %d placements together (%s)"
     % (len(_ordinals), ", ".join(_ordinals)),
     all(o in _flat for o in _ordinals)
     and (", ".join(_ordinals[:-1]) + " and " + _ordinals[-1]) in _flat)
must("it does not quote a subset of the placements as if complete",
     (", ".join(_ordinals[1:-1]) + " and " + _ordinals[-1]) not in _flat
     or (", ".join(_ordinals[:-1]) + " and " + _ordinals[-1]) in _flat)
for title in HERO["rows"][:5]:
    must("names the grounded pick %s" % title["title"], title["title"] in DOC)
for title in HERO["llm_top5"]:
    must("names the model's pick %s" % title, title in DOC)

print("\nretired phrasing must not reappear")
RETIRED = {
    "0.18": r"\b0\.18\b",
    "a 10,000 monthly quota": r"10[,_]?000",
    '"independent" for disjoint halves': r"(?<!not )(?<!fully )independent readings?",
    '"contrary"/"runs against"': r"\b(contrary|runs against|inverse)\b",
    '"opened with"': r"open(ed)? with",
    '"perfectly repeatable"': r"perfectly repeatable",
}
for label, pattern in RETIRED.items():
    hit = re.search(pattern, DOC, re.I)
    must("no %s" % label, hit is None)
    if hit:
        line = DOC[:hit.start()].count("\n") + 1
        print("        line %d: %s" % (line, hit.group(0)))

print()
if bad:
    print("%d problem(s): %s" % (len(bad), "; ".join(bad)))
    sys.exit(1)
print("submission text agrees with the recorded run")
