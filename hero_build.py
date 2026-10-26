"""Record the hero run once, so the landing page costs a visitor nothing.

The pair is whatever the registered sweep selected -- this script reads the
winner rather than naming one, so the page and the pre-registration cannot
drift apart. On top of the ordinary grounded run it records, per title, which
of the audience's own entities drive it, taken from Qloo's own
`feature.explainability`. That is what lets the page say *why* a title is
there without a sentence anyone had to write by hand.
"""
from __future__ import annotations

import json
import pathlib

from qloo_client import QlooClient, entities_of, id_of, load_dotenv
from taste import pitch
from taste.evidence import Trace

HERE = pathlib.Path(__file__).parent
CAND = json.loads((HERE / "fixtures" / "hero_candidates.json").read_text())
SWEEP = json.loads((HERE / "out" / "hero_sweep.json").read_text())
TYPES = CAND["entity_types"]


def main():
    load_dotenv()
    win = SWEEP["winner"]
    if not win:
        raise SystemExit("No qualifying pair; nothing to build.")
    aud = next(a for a in CAND["audiences"] if a["id"] == win["audience"])
    slate = next(s for s in CAND["slates"] if s["id"] == win["slate"])
    client = QlooClient(log_name="hero_build.jsonl")
    trace = Trace()

    members = [{"name": m["name"], "type": TYPES[m["type"]]} for m in aud["members"]]
    res = pitch.run(client, slate["titles"], members, trace=trace, with_llm=False)

    # Name the audience entities so explainability can be read by a person.
    sig = {}
    for m in members:
        hits = entities_of(client.search(m["name"], types=m["type"]))
        if hits:
            sig[id_of(hits[0])] = m["name"]

    # One explainability call over the ranked titles.
    name_by_id, id_by_name = {}, {}
    for t in slate["titles"]:
        hits = entities_of(client.search(t, types="urn:entity:movie"))
        if hits:
            nm = hits[0].get("name") or t
            name_by_id[id_of(hits[0])] = nm
            id_by_name[nm] = id_of(hits[0])

    ranked = [r["title"] for r in res["rows"]]
    ids = [id_by_name[n] for n in ranked if n in id_by_name]
    params = {"filter.type": "urn:entity:movie",
              "filter.results.entities": ",".join(ids),
              "signal.interests.entities": ",".join(sig),
              "feature.explainability": "true",
              "take": len(ids)}
    status, body = client.insights(params, allow_error=True)
    items = entities_of(body)
    trace.record_call("/v2/insights", dict(params, _reading="hero:explainability"),
                      status, len(items))

    drivers = {}
    for item in items:
        nm = item.get("name")
        ex = ((item.get("query") or {}).get("explainability") or {})
        ents = ex.get("signal.interests.entities") or []
        named = [{"name": sig.get(e.get("entity_id")),
                  "score": round(e.get("score", 0), 4)}
                 for e in ents if sig.get(e.get("entity_id"))]
        named.sort(key=lambda d: -d["score"])
        if nm and named:
            drivers[nm] = named[:3]

    llm_top5 = win["llm_top5_stable"]
    grounded_top5 = [r["title"] for r in res["rows"][:5]]
    payload = dict(res)
    payload.update({
        "hero": True,
        "audience": {"id": aud["id"], "label": aud["label"],
                     "members": [{"name": m["name"], "kind": m["type"]}
                                 for m in aud["members"]]},
        "slate_id": slate["id"],
        "drivers": drivers,
        "llm_top5": llm_top5,
        "llm_repeats": win["llm_runs"],
        "llm_top5_counts": win["llm_top5_counts"],
        "llm_full_order_identical": win["llm_repeats_identical"],
        "shared_top5": [t for t in grounded_top5 if t in llm_top5],
        "grounded_only_top5": [t for t in grounded_top5 if t not in llm_top5],
        "llm_only_top5": [t for t in llm_top5 if t not in grounded_top5],
        "provenance": {
            "pre_registration": SWEEP["pre_registration_file"],
            "sha256": SWEEP["pre_registration_sha256"],
            "pairs_evaluated": SWEEP["pairs_evaluated"],
            "pairs_qualified": SWEEP["qualified"],
        },
        "evidence": trace.summary() if hasattr(trace, "summary") else None,
    })
    out = HERE / "app" / "cache" / "hero.json"
    out.write_text(json.dumps(payload, indent=2))
    print("hero: %s x %s" % (aud["id"], slate["id"]))
    print("  grounded top5 :", grounded_top5)
    print("  llm-only top5 :", llm_top5)
    print("  shared        :", payload["shared_top5"])
    print("  drivers for   :", list(drivers)[:6])
    print("  written       :", out)
    print("  quota         :", client.quota_remaining)


if __name__ == "__main__":
    main()
