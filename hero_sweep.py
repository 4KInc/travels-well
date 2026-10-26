"""Choose the hero audience and slate, under a rule fixed before the data.

Every audience x slate pair is evaluated and every result is reported, so the
landing page's divergence number is a selection under a published rule rather
than the best thing we happened to find. The rule is hashed in
out/prereg_amended_hero_*.json; this script reads it rather than restating it,
so the two cannot drift apart.

The grounded side reuses taste/pitch.py unchanged. A parallel implementation
tuned for the sweep would make the hero number describe something the product
does not actually do.
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

from qloo_client import QlooClient, load_dotenv
from taste import llm_baseline, pitch
from taste.evidence import Trace

HERE = pathlib.Path(__file__).parent
CAND = json.loads((HERE / "fixtures" / "hero_candidates.json").read_text())
TYPES = CAND["entity_types"]

# The gates come from the registered amendment, not from here.
# Newest by mtime, not by name: the filename is a content hash, so sorting
# by name would pick an arbitrary amendment rather than the current one.
_rec = sorted((HERE / "out").glob("prereg_amended_hero_*.json"),
              key=lambda q: q.stat().st_mtime)
if not _rec:
    sys.exit("No hero pre-registration found. Run prereg.write_hero() first.")
REG = json.loads(_rec[-1].read_text())
RULES = REG["decision_rules"]
GATES = RULES["selection_criteria_all_must_hold"]
LLM = RULES["llm_baseline"]
CALL_BUDGET = 1500


def members_for(audience):
    return [{"name": m["name"], "type": TYPES[m["type"]]} for m in audience["members"]]


def stable_llm_top5(runs):
    """A title counts only if the model put it in its top five in at least 2 of
    3 repeats. At temperature zero the repeats are expected to agree; recording
    it is what lets us say so rather than assume it."""
    seen = collections.Counter()
    for order in runs:
        for t in order[:5]:
            seen[t] += 1
    need = max(2, (len(runs) + 1) // 2)
    stable = [t for t, n in seen.items() if n >= need]
    # Preserve the first run's ordering for readability.
    order0 = runs[0] if runs else []
    stable.sort(key=lambda t: order0.index(t) if t in order0 else 99)
    return stable, dict(seen)


def evaluate(client, audience, slate):
    """Grounded first; the model only runs for pairs that already pass the
    grounded gates, as registered."""
    row = {"audience": audience["id"], "audience_label": audience["label"],
           "slate": slate["id"], "qualified": False, "why_not": None}
    trace = Trace()
    try:
        res = pitch.run(client, slate["titles"], members_for(audience),
                        trace=trace, with_llm=False)
    except pitch.PitchError as exc:
        row["why_not"] = "aborted: %s" % exc
        return row, None
    except Exception as exc:                       # noqa: BLE001 - reported, not hidden
        row["why_not"] = "%s: %s" % (type(exc).__name__, exc)
        return row, None

    agree = res["buyer"]["halves_agree"]
    withheld = len(res["withheld"])
    rows = res["rows"]
    row.update({"halves_agree": agree, "withheld": withheld,
                "ranked": len(rows), "low_separation": res.get("low_separation"),
                "absolute": res.get("absolute"),
                "grounded_top5": [r["title"] for r in rows[:5]]})

    if agree is None or agree < GATES["buyer_halves_agree_min"]:
        row["why_not"] = "halves agree %s, below %.2f" % (
            agree, GATES["buyer_halves_agree_min"])
        return row, res
    if withheld > GATES["withheld_max"]:
        row["why_not"] = "%d withheld, above %d" % (withheld, GATES["withheld_max"])
        return row, res
    if len(rows) < 5:
        row["why_not"] = "only %d titles survived to rank" % len(rows)
        return row, res

    runs, notes = [], []
    for _ in range(LLM["repeats"]):
        out = llm_baseline.rank([r["title"] for r in rows],
                                [m["name"] for m in audience["members"]],
                                audience_label=audience["label"])
        if out.get("available"):
            runs.append(out["order"])
        else:
            notes.append(out.get("note"))
    if not runs:
        row["why_not"] = "no usable model answer (%s)" % (notes[0] if notes else "?")
        return row, res

    stable, counts = stable_llm_top5(runs)
    g5 = set(row["grounded_top5"])
    overlap = len(g5 & set(stable))
    identical = sum(1 for o in runs[1:] if o == runs[0])
    row.update({"llm_runs": len(runs), "llm_repeats_identical": identical + 1,
                "llm_top5_stable": stable, "llm_top5_counts": counts,
                "top5_overlap": overlap,
                "llm_only": [t for t in stable if t not in g5],
                "grounded_only": [t for t in row["grounded_top5"] if t not in set(stable)]})
    if overlap > GATES["top5_overlap_max"]:
        row["why_not"] = "top-5 overlap %d, above %d" % (
            overlap, GATES["top5_overlap_max"])
        return row, res
    row["qualified"] = True
    return row, res


def main():
    load_dotenv()
    client = QlooClient(log_name="hero_sweep.jsonl")
    before = None
    results, kept = [], {}
    pairs = [(a, s) for a in CAND["audiences"] for s in CAND["slates"]]
    print("evaluating %d pairs (%d audiences x %d slates)"
          % (len(pairs), len(CAND["audiences"]), len(CAND["slates"])))

    for i, (aud, slate) in enumerate(pairs, 1):
        row, res = evaluate(client, aud, slate)
        if before is None:
            before = client.quota_remaining
        results.append(row)
        if row["qualified"]:
            kept[(aud["id"], slate["id"])] = res
        print("  [%2d/%d] %-16s x %-14s %s"
              % (i, len(pairs), aud["id"], slate["id"],
                 ("QUALIFIES overlap=%d agree=%s" % (row["top5_overlap"], row["halves_agree"]))
                 if row["qualified"] else ("- " + (row["why_not"] or "?"))))
        spent = (before - client.quota_remaining) if (
            before is not None and client.quota_remaining is not None) else 0
        if spent > CALL_BUDGET:
            print("  !! call budget %d exceeded, stopping early" % CALL_BUDGET)
            break

    qualifying = [r for r in results if r["qualified"]]
    winner = None
    if qualifying:
        winner = sorted(qualifying, key=lambda r: (
            r["top5_overlap"], -(r["halves_agree"] or 0), r["withheld"], r["audience"]))[0]

    out = {"pre_registration_sha256": REG["sha256"],
           "pre_registration_file": _rec[-1].name,
           "pairs_evaluated": len(results),
           "qualified": len(qualifying),
           "quota_before": before, "quota_after": client.quota_remaining,
           "winner": winner, "results": results}
    (HERE / "out" / "hero_sweep.json").write_text(json.dumps(out, indent=2))

    if winner:
        key = (winner["audience"], winner["slate"])
        (HERE / "out" / "hero_result.json").write_text(
            json.dumps(kept[key], indent=2))
        print("\nwinner: %s x %s  overlap=%d  agree=%s"
              % (winner["audience"], winner["slate"],
                 winner["top5_overlap"], winner["halves_agree"]))
    else:
        print("\nNOTHING QUALIFIED - do not loosen the criteria; report and amend.")
    print("quota: %s -> %s" % (before, client.quota_remaining))


if __name__ == "__main__":
    main()
