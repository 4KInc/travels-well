"""Pitch desk: rank YOUR slate for a buyer described by what they already hold.

The atlas answers with audiences we discovered. A sales agent needs the
opposite: her own titles, and a specific buyer who is not on our map. So a
buyer here is described the way the industry already describes one -- by their
catalogue -- and the profile is built from those films directly.

That also restores the consensus check the small clusters could not support: a
catalogue of eight titles splits into two halves of four, each half becomes an
separate reading -- disjoint, not independent, since both still come from
the same graph -- and any title the two halves rank very differently is
withheld rather than reported.
"""
from __future__ import annotations

from qloo_client import QlooError, affinity_of, entities_of, id_of
from stats import kendall_tau_b, rank_percentiles

FLAT_SPREAD = 0.35     # a reading this flat separates nothing
WEAK_HALVES = 0.50     # below this the two halves describe different tastes
MIN_SLATE = 4
MIN_BUYER = 4
SPLIT_MIN = 6          # below this a catalogue cannot be halved meaningfully
DISAGREE = 0.25        # rank-percentile gap above which a title is withheld
MAX_TITLES = 50        # the API caps take at 50


class PitchError(RuntimeError):
    pass


def resolve_titles(client, titles, entity_type="urn:entity:movie", trace=None):
    """Resolve, reporting what the graph does not know rather than dropping it.

    An entry is either a plain title, resolved as `entity_type`, or a mapping
    {"name": ..., "type": "urn:entity:videogame"} carrying its own type. The
    second form is what lets an audience be described by the things it already
    loves -- games, shows, artists -- rather than only by films, while the
    slate being ranked stays a single type.
    """
    found, missing = [], []
    for raw in titles:
        if isinstance(raw, dict):
            name = (raw.get("name") or "").strip()
            etype = raw.get("type") or entity_type
        else:
            name, etype = raw.strip(), entity_type
        if not name:
            continue
        try:
            hits = entities_of(client.search(name, types=etype))
        except QlooError:
            hits = []
        if trace is not None:
            trace.record_call("/search", {"query": name, "_type": etype},
                              200, len(hits))
        if not hits:
            missing.append(name)
            continue
        props = hits[0].get("properties") or {}
        found.append({"asked": name,
                      "name": hits[0].get("name") or name,
                      "id": id_of(hits[0]),
                      "type": etype,
                      "image": (props.get("image") or {}).get("url")})
    return found, missing


def _score(client, slate_ids, signal_ids, entity_type, trace=None, label=None):
    params = {"filter.type": entity_type,
              "filter.results.entities": ",".join(slate_ids),
              "signal.interests.entities": ",".join(signal_ids),
              "take": min(len(slate_ids), MAX_TITLES)}
    status, body = client.insights(params, allow_error=True)
    items = entities_of(body)
    if trace is not None:
        trace.record_call("/v2/insights", dict(params, _reading=label or "-"),
                          status, len(items))
    out = {}
    for item in items:
        eid, aff = id_of(item), affinity_of(item)
        if eid and aff is not None:        # never fall back to popularity
            out[eid] = aff
    return out


def _spread(scores):
    if len(scores) < 2:
        return 0.0
    vals = sorted(scores.values())
    return vals[-1] - vals[0]


def profile(client, slate_ids, catalogue_ids, entity_type, trace=None,
            tag="buyer", log=None):
    """Rank the slate for one taste profile, cross-checked by splitting the
    describing catalogue into halves.

    Two points here are decisions rather than steps: a reading flat enough to
    separate nothing is re-probed against the catalogue's most distinctive
    half, and a split whose halves disagree is re-split a different way and
    the better-agreeing one kept. Both are recorded with what was observed.
    """
    flat_warning = [False]

    def step(action, reason, observed=None, changed=None):
        if log is not None:
            # Tagged, because the same sequence runs for the buyer and again
            # for the home audience and the trace is unreadable without it.
            log.append({"action": action, "reason": reason, "profile": tag,
                        "observed": observed, "changed": changed})

    whole = _score(client, slate_ids, catalogue_ids, entity_type, trace, tag)
    if not whole:
        raise PitchError("Qloo returned no affinities for that combination")
    spread = _spread(whole)
    step("probe", "score your slate against everything the buyer holds",
         "%d titles scored, affinity spread %.3f (floor %.2f)"
         % (len(whole), spread, FLAT_SPREAD))

    if spread < FLAT_SPREAD and len(catalogue_ids) >= SPLIT_MIN:
        # The catalogue as a whole separates nothing. Re-probe against the
        # half that is most unlike the other, which is where the signal is.
        half_a, half_b = catalogue_ids[0::2], catalogue_ids[1::2]
        sa = _score(client, slate_ids, half_a, entity_type, trace, tag + ":probe A")
        sb = _score(client, slate_ids, half_b, entity_type, trace, tag + ":probe B")
        best = max((sa, sb), key=_spread) if (sa and sb) else (sa or sb)
        if best and _spread(best) > spread:
            step("re-probe",
                 "the first reading was too flat to separate anything, so the "
                 "catalogue was split and the more distinctive half used",
                 "spread %.3f -> %.3f (floor %.2f)"
                 % (spread, _spread(best), FLAT_SPREAD),
                 "switched to the sharper half of the buyer's catalogue")
            whole = best
        else:
            step("re-probe", "tried the halves separately; neither sharpened "
                 "the reading, so the original stands",
                 "spread stayed near %.3f" % spread,
                 "the original reading stands")

    # The flag is a property of the reading we are about to rank on, not of
    # whether the re-probe helped. An earlier version cleared it on ANY
    # improvement: a catalogue that moved 0.076 -> 0.082 against a 0.35 floor
    # came out unflagged and read as well separated, while a flatter-looking
    # 0.152 was flagged. That inverted the label on the four pairs it was
    # measured against.
    final_spread = _spread(whole)
    flat_warning[0] = final_spread < FLAT_SPREAD
    if flat_warning[0]:
        step("separation check",
             "the reading being ranked on is still flatter than the floor, so "
             "the order within the shortlist is reported as uncertain",
             "final spread %.3f, floor %.2f" % (final_spread, FLAT_SPREAD),
             "ranking continues, but marked low-separation: this catalogue "
             "barely distinguishes your titles from one another")

    if len(catalogue_ids) < SPLIT_MIN:
        step("no cross-check",
             "a catalogue under %d titles cannot be halved into two readings "
             "that can disagree" % SPLIT_MIN,
             "%d titles supplied" % len(catalogue_ids))
        return rank_percentiles(whole), [], None, flat_warning[0], None

    def split_eval(a, b, label):
        ra = _score(client, slate_ids, a, entity_type, trace, tag + ":" + label + " A")
        rb = _score(client, slate_ids, b, entity_type, trace, tag + ":" + label + " B")
        if not ra or not rb:
            return None
        pa, pb = rank_percentiles(ra), rank_percentiles(rb)
        return pa, pb, (kendall_tau_b(pa, pb) or 0.0)

    first = split_eval(catalogue_ids[0::2], catalogue_ids[1::2], "alternating")
    if first is None:
        return rank_percentiles(whole), [], None, flat_warning[0], None
    pa, pb, agreement = first
    step("cross-check", "split the catalogue in two and read each half, so a "
         "title the halves disagree about can be withheld",
         "halves agree at %.2f" % agreement)

    if agreement < WEAK_HALVES:
        mid = len(catalogue_ids) // 2
        second = split_eval(catalogue_ids[:mid], catalogue_ids[mid:], "contiguous")
        if second and second[2] > agreement:
            step("re-split",
                 "the halves disagreed, which can be an artefact of how they "
                 "were divided rather than of the catalogue, so a different "
                 "division was tried",
                 "agreement %.2f -> %.2f" % (agreement, second[2]),
                 "kept the better-agreeing split")
            pa, pb, agreement = second
        else:
            step("re-split",
                 "tried a different division; the halves still disagree, so "
                 "this catalogue genuinely describes more than one taste",
                 "agreement stayed near %.2f" % agreement,
                 "evidence marked weak")

    shared = [e for e in pa if e in pb]
    withheld = [e for e in shared if abs(pa[e] - pb[e]) > DISAGREE]
    if withheld:
        step("withhold", "the two halves placed these titles far apart, so no "
             "verdict is offered on them", "%d of %d titles withheld"
             % (len(withheld), len(shared)))
    # How many of the top five survive a re-reading from the other half of
    # the describing catalogue. The halves are disjoint, not independent: they
    # share no entities, but both are read out of the same graph. Rank
    # correlation over the whole slate can look healthy while the five titles
    # actually shown churn, and the five are what someone acts on.
    top5_a = [e for e in sorted(pa, key=lambda x: -pa[x])[:5]]
    top5_b = [e for e in sorted(pb, key=lambda x: -pb[x])[:5]]
    top5_hold = len(set(top5_a) & set(top5_b))
    step("top-five check",
         "rank correlation can look healthy while the five titles actually "
         "shown change, and the five are what someone acts on",
         "%d of 5 top titles appear in both halves' readings" % top5_hold)
    return rank_percentiles(whole), withheld, agreement, flat_warning[0], top5_hold


def placements_for(llm_titles, rows, withheld_ids, by_id):
    """Where each of the model's picks landed in the grounded reading.

    This is the plainest account of a disagreement: both columns come from the
    same pinned query, so a title the model chose and the graph ranked ninth is
    simply that. A title the graph withheld has no rank to report -- saying it
    ranked last would invent a verdict the agent explicitly declined to give.
    """
    place = {r["title"]: i + 1 for i, r in enumerate(rows)}
    withheld_names = {by_id[e]["name"] for e in withheld_ids if e in by_id}
    grounded_top5 = {r["title"] for r in rows[:5]}
    out = []
    for title in llm_titles:
        if title in grounded_top5:
            out.append({"title": title, "shared": True})
        elif title in withheld_names:
            out.append({"title": title, "shared": False, "withheld": True})
        else:
            out.append({"title": title, "shared": False, "withheld": False,
                        "grounded_place": place.get(title),
                        "of_ranked": len(rows)})
    return out


def run(client, slate_titles, buyer_titles, home_titles=None,
        entity_type="urn:entity:movie", trace=None, with_llm=False,
        with_invariance=False, audience_label=None):
    steps = []
    slate, slate_missing = resolve_titles(client, slate_titles, entity_type, trace)
    steps.append({"action": "resolve", "profile": "setup",
                  "reason": "bind every title to a real entity before measuring "
                            "anything; an unresolvable name is reported, never guessed",
                  "observed": "%d of %d slate titles resolved%s"
                              % (len(slate), len([t for t in slate_titles if t.strip()]),
                                 (", missing: " + ", ".join(slate_missing)) if slate_missing else "")})
    if len(slate) < MIN_SLATE:
        raise PitchError(
            "Only %d of your titles resolved. At least %d are needed before a "
            "ranking means anything." % (len(slate), MIN_SLATE))
    buyer, buyer_missing = resolve_titles(client, buyer_titles, entity_type, trace)
    if len(buyer) < MIN_BUYER:
        raise PitchError(
            "Only %d of the buyer's titles resolved. At least %d are needed to "
            "describe what they like." % (len(buyer), MIN_BUYER))

    # Qloo excludes a signal entity from its own results, so any title that
    # appears both in the slate and in a describing catalogue comes back
    # unscored and would silently disappear. Take it out openly instead.
    describing = {b["id"] for b in buyer}
    home_pre, _ = (resolve_titles(client, home_titles, entity_type, trace)
                   if home_titles else ([], []))
    describing |= {h["id"] for h in home_pre}
    overlap = [s["name"] for s in slate if s["id"] in describing]
    slate = [s for s in slate if s["id"] not in describing]
    if len(slate) < MIN_SLATE:
        raise PitchError(
            "After removing titles that also appear in the catalogues you used "
            "to describe the buyer (%s), only %d of your titles are left. Qloo "
            "cannot score a title against itself."
            % (", ".join(overlap) or "none", len(slate)))

    slate_ids = [s["id"] for s in slate][:MAX_TITLES]
    by_id = {s["id"]: s for s in slate}

    if overlap:
        steps.append({"action": "remove overlap", "profile": "setup",
                      "reason": "Qloo excludes an entity from its own results, so a "
                                "title that also describes the buyer cannot be scored "
                                "against itself and would vanish silently",
                      "observed": "removed " + ", ".join(overlap)})
    buyer_affinity = _score(client, slate_ids, [b["id"] for b in buyer],
                            entity_type, trace, "buyer:absolute")
    buyer_ranks, withheld, buyer_agreement, buyer_flat, buyer_top5_hold = profile(
        client, slate_ids, [b["id"] for b in buyer], entity_type, trace, "buyer",
        log=steps)

    home_ranks, home_agreement, home = None, None, []
    if home_titles:
        home = home_pre
        if len(home) >= MIN_BUYER:
            home_ranks, home_withheld, home_agreement, _, _ = profile(
                client, slate_ids, [h["id"] for h in home], entity_type,
                trace, "home", log=steps)
            withheld = list(set(withheld) | set(home_withheld))

    # FIT and SHIFT answer different questions and can disagree sharply. In
    # the worked example Parasite sits 9th of 12 for the buyer yet 5th by
    # movement, because it also ranks low at home and so has no drop to
    # register. Sorting by movement would put a title the buyer barely wants
    # above one they want more. So fit is what orders the shortlist; movement
    # is reported beside it as the surprise, never as the ranking.
    rows, uncomparable = [], []
    for eid, rank in buyer_ranks.items():
        if eid in withheld or eid not in by_id:
            continue
        row = {"title": by_id[eid]["name"], "image": by_id[eid]["image"],
               "fit": round(rank, 3),
               "place": None,              # filled in after sorting
               "affinity": round(buyer_affinity.get(eid), 4)
                           if buyer_affinity.get(eid) is not None else None}
        if home_ranks:
            if eid in home_ranks:
                row["shift"] = round(rank - home_ranks[eid], 3)
                row["home_fit"] = round(home_ranks[eid], 3)
            else:
                # Scored for the buyer but not for home: no movement can be
                # computed, and reporting it as zero would be a lie.
                uncomparable.append(row)
                continue
        rows.append(row)
    # The same question put to a model with no taste graph. Divergence is the
    # finding; which one is right is not something we can show.
    llm_block = None
    if with_llm:
        from taste import llm_baseline
        llm_block = llm_baseline.rank(
            [by_id[e]["name"] for e in buyer_ranks if e in by_id],
            [b["name"] for b in buyer],
            {by_id[e]["name"]: v for e, v in buyer_ranks.items() if e in by_id},
            audience_label=audience_label)
        if llm_block and llm_block.get("available"):
            llm_block["placements"] = placements_for(
                llm_block.get("llm_top5") or [], rows, withheld, by_id)
            steps.append({"action": "ablate", "profile": "result",
                          "reason": "ask the same question of a model with no "
                                    "access to the taste graph, so the difference "
                                    "Qloo makes is shown rather than claimed",
                          "observed": "agreement with the grounded ranking: %s"
                                      % llm_block.get("agreement")})

    # Does this title's rank depend on who is asking, or not at all?
    invariance = None
    if with_invariance:
        from taste import invariance as inv
        invariance = inv.check(
            client, slate_ids, by_id, entity_type,
            lambda ids, sig, label: _score(client, ids, sig, entity_type, trace, label),
            trace)
        if invariance.get("available"):
            flat = set(invariance["invariant"])
            for r in rows:
                if r["title"] in flat:
                    r["invariant"] = True
            steps.append({"action": "invariance", "profile": "result",
                          "reason": "check each title against four unalike "
                                    "reference audiences, so a title that ranks "
                                    "the same for everyone is not mistaken for fit",
                          "observed": "%d of %d titles rank the same wherever "
                                      "you ask" % (len(flat), len(invariance["rows"]))})

    rows.sort(key=lambda r: -r["fit"])          # rank position orders the list
    for i, r in enumerate(rows, 1):
        r["place"] = "%d of %d" % (i, len(rows))

    # An absolute reading, because rank alone cannot say "this whole slate is
    # weak for this buyer": the top title is 1.00 even when nothing fits.
    affs = [r["affinity"] for r in rows if r.get("affinity") is not None]
    absolute = None
    if affs:
        best, worst = max(affs), min(affs)
        mean = sum(affs) / len(affs)
        absolute = {"best": round(best, 3), "worst": round(worst, 3),
                    "mean": round(mean, 3), "span": round(best - worst, 3)}
        steps.append({"action": "absolute check", "profile": "result",
                      "reason": "rank position cannot say whether the slate as "
                                "a whole suits this buyer, so the raw affinities "
                                "are reported alongside it",
                      "observed": "affinity %.3f to %.3f, mean %.3f"
                                  % (worst, best, mean)})
    steps.append({"action": "rank", "profile": "result",
                  "reason": "order by fit, not by movement: a title that merely "
                            "improves against home is not the same as one the buyer wants",
                  "observed": "%d titles ranked, %d withheld, %d uncomparable"
                              % (len(rows), len(withheld), len(uncomparable))})

    # Flag the two ways fit and movement part company, so neither is read as
    # the other.
    if home_ranks and len(rows) >= 4:
        by_fit = {r["title"]: i for i, r in enumerate(rows)}
        by_shift = {r["title"]: i for i, r in
                    enumerate(sorted(rows, key=lambda r: -r.get("shift", 0)))}
        for r in rows:
            gap = by_shift[r["title"]] - by_fit[r["title"]]
            if gap <= -4:
                r["note"] = "moves up a lot, but the buyer still ranks it low"
            elif gap >= 4:
                r["note"] = "strong fit even though it does well at home too"

    return {
        "mode": "shift" if home_ranks else "fit",
        "ordered_by": "fit",
        "absolute": absolute,
        "metric_note": (
            "RANK is a title's place among the ones you offered, not a score: "
            "the top title reads 1.00 even if this buyer is lukewarm about "
            "your whole slate, and the bottom reads 0.00 only because "
            "something has to be last. MOVEMENT is that place minus its place "
            "with your home audience. The raw affinities are shown separately "
            "so the slate can be judged as a whole."),
        "rows": rows,
        "withheld": [by_id[e]["name"] for e in withheld if e in by_id],
        "uncomparable": uncomparable,
        "excluded_overlap": overlap,
        "low_separation": buyer_flat,
        "buyer": {"resolved": [b["name"] for b in buyer],
                  "missing": buyer_missing,
                  "halves_agree": (round(buyer_agreement, 3)
                                   if buyer_agreement is not None else None),
                  "top5_hold": buyer_top5_hold},
        "home": {"resolved": [h["name"] for h in home],
                 "halves_agree": (round(home_agreement, 3)
                                  if home_agreement is not None else None)},
        "slate": {"resolved": len(slate), "missing": slate_missing},
        "art": {s_["name"]: s_["image"] for s_ in slate if s_.get("image")},
        "steps": steps,
        "llm": llm_block,
        "invariance": invariance,
    }
