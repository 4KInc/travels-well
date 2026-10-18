"""Which titles rank the same whoever is asking.

A recommender that puts the same film at the top for every buyer is reporting
popularity, not fit. The check: score the slate against four deliberately
unalike reference audiences and measure how far each title's rank moves. A
title that barely moves is flagged, because its position in a buyer's
shortlist is not evidence about that buyer.

Four extra calls per run, and the reference audiences are fixed so the result
is comparable between runs.
"""
from __future__ import annotations

import json
from pathlib import Path

from qloo_client import entities_of, id_of
from stats import rank_percentiles

HERE = Path(__file__).resolve().parent.parent
SPEC = json.loads((HERE / "fixtures" / "reference_audiences.json").read_text())
FLAT = 0.25          # rank range below this is "the same wherever you ask"


def _resolve(client, name, kind, cache):
    key = "%s/%s" % (kind, name)
    if key in cache:
        return cache[key]
    hits = entities_of(client.search(name, types="urn:entity:%s" % kind))
    cache[key] = id_of(hits[0]) if hits else None
    return cache[key]


def check(client, slate_ids, by_id, entity_type, scorer, trace=None):
    """`scorer(slate_ids, signal_ids, label)` returns {entity_id: affinity}."""
    cache, per_audience = {}, {}
    for label, members in SPEC["audiences"].items():
        ids = [i for i in (_resolve(client, n, k, cache) for n, k in members) if i]
        if len(ids) < 2:
            continue
        scores = scorer(slate_ids, ids, "reference:" + label)
        if scores:
            per_audience[label] = rank_percentiles(scores)
    if len(per_audience) < 3:
        return {"available": False,
                "note": "Not enough reference audiences resolved to test this."}

    rows = []
    for eid in slate_ids:
        places = [r[eid] for r in per_audience.values() if eid in r]
        if len(places) < 3:
            continue
        spread = max(places) - min(places)
        rows.append({"title": by_id[eid]["name"],
                     "spread": round(spread, 3),
                     "mean_rank": round(sum(places) / len(places), 3),
                     "invariant": spread < FLAT})
    rows.sort(key=lambda r: r["spread"])
    return {"available": True,
            "audiences": list(per_audience),
            "rows": rows,
            "invariant": [r["title"] for r in rows if r["invariant"]],
            "threshold": FLAT}
