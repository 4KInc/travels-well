"""What an agent with no taste graph would pitch.

The same question, asked of a language model that sees only the title lists:
no Qloo, no affinities. This is the ablation the brief asks for -- "would this
work the same without Qloo" -- answered by running it rather than asserting it.

One thing it is NOT: a scoreboard. There is no ground truth for what a buyer
would actually license, so this shows where the two disagree, never which is
right. Saying otherwise would be the kind of claim the rest of the project
spends its effort avoiding.
"""
from __future__ import annotations

import json
import os
import re

from stats import kendall_tau_b, rank_percentiles

MODEL_ENV = "GAP_MODEL"
TIMEOUT_NOTE = ("The language model did not answer in time, so no comparison "
                "is shown. Nothing is inferred from its silence.")


def available():
    return bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTHROPIC_API_KEY"))


def _ask(prompt):
    import probe_gap          # reuses the provider plumbing from the harness
    return probe_gap.call_llm(prompt, grounded=False)


def rank(slate_titles, buyer_titles, qloo_ranks=None, audience_label=None):
    """Returns the model's ordering and, where possible, its agreement with
    Qloo's. `qloo_ranks` maps title -> rank percentile.

    Two modes, because the product describes an audience two ways. Without
    `audience_label` the describing list is a buyer's licensed catalogue, as
    at a film market. With it, the list is what an audience already loves --
    games, shows, artists -- and the label names them in plain words. The
    model sees the same describing entities Qloo does and nothing else, so
    the comparison isolates the taste graph rather than the information.
    """
    if not available():
        return {"available": False, "note": "No model key configured on this server."}
    # The lists must be impossible to confuse. An earlier version put the
    # buyer's catalogue first and then said "rank these films", and the model
    # ranked the buyer's own titles back at us.
    if audience_label:
        frame = ("You are advising someone who programs films for a streaming "
                 "audience.\n\n"
                 "LIST A -- what this AUDIENCE already loves (context only, do "
                 "NOT rank these):\n%s\n\n"
                 "LIST B -- the CATALOGUE to choose from (%d titles, rank ALL "
                 "of these):\n%s\n\n"
                 "Rank every title in LIST B from most to least likely to "
                 "appeal to that audience."
                 % ("\n".join("- " + t for t in buyer_titles),
                    len(slate_titles),
                    "\n".join("- " + t for t in slate_titles)))
    else:
        frame = ("You are advising a film sales agent.\n\n"
                 "LIST A -- titles the BUYER has already licensed (context "
                 "only, do NOT rank these):\n%s\n\n"
                 "LIST B -- the SLATE FOR SALE (%d titles, rank ALL of "
                 "these):\n%s\n\n"
                 "Rank every title in LIST B from most to least likely to "
                 "appeal to that buyer's audience."
                 % ("\n".join("- " + t for t in buyer_titles),
                    len(slate_titles),
                    "\n".join("- " + t for t in slate_titles)))
    prompt = (frame +
              " Reply ONLY with a JSON array of exactly %d strings, each "
              "spelled exactly as it appears in LIST B. No prose."
              % len(slate_titles))
    try:
        raw = _ask(prompt)
    except Exception as exc:
        return {"available": False, "note": "%s (%s)" % (TIMEOUT_NOTE, type(exc).__name__)}

    match = re.search(r"\[.*\]", raw, re.S)
    if not match:
        return {"available": False, "note": "The model did not return a usable ranking."}
    try:
        order = [t for t in json.loads(match.group(0)) if isinstance(t, str)]
    except ValueError:
        return {"available": False, "note": "The model's ranking could not be parsed."}

    # Accent- and punctuation-insensitive matching: the model does not always
    # echo "Amelie" or "La haine" exactly as Qloo spells them.
    import re as _re
    import unicodedata as _ud

    def key(t):
        t = _ud.normalize("NFKD", t or "")
        t = "".join(ch for ch in t if not _ud.combining(ch))
        return _re.sub(r"[^a-z0-9]+", "", t.lower())

    known = {key(t): t for t in slate_titles}
    order = [known[key(t)] for t in order if key(t) in known]
    # Guard against the model handing back a list that is not the slate.
    if len(order) < 0.6 * len(slate_titles):
        return {"available": False,
                "note": "The model did not rank the slate it was given "
                        "(%d of %d titles recognised)." % (len(order), len(slate_titles))}
    if len(order) < 4:
        return {"available": False,
                "note": "The model named too few of the slate to compare."}

    out = {"available": True, "order": order,
           "model": os.environ.get(MODEL_ENV, "gemini-2.5-flash")}
    if qloo_ranks:
        llm_ranks = {t: (len(order) - 1 - i) / (len(order) - 1)
                     for i, t in enumerate(order)}
        shared = {t: qloo_ranks[t] for t in llm_ranks if t in qloo_ranks}
        if len(shared) >= 4:
            tau = kendall_tau_b(rank_percentiles(shared),
                                rank_percentiles({t: llm_ranks[t] for t in shared}))
            out["agreement"] = round(tau, 3) if tau is not None else None
            out["compared_on"] = len(shared)
            # A single agreement number hides the shape of the disagreement.
            # On the worked example both pick the obvious top three and then
            # part company, which is the interesting part.
            n = len(shared)
            q_pos = {t: i for i, t in enumerate(
                sorted(shared, key=lambda x: -shared[x]))}
            l_pos = {t: i for i, t in enumerate(
                [t for t in order if t in shared])}
            gaps = sorted(((abs(q_pos[t] - l_pos[t]), t, q_pos[t] + 1, l_pos[t] + 1)
                           for t in shared), reverse=True)
            # Top-five overlap is the number that matters: she pitches five
            # titles, so agreement at ranks 6-12 does not change her meeting.
            q_top5 = set(sorted(shared, key=lambda x: -shared[x])[:5])
            l_top5 = set([t for t in order if t in shared][:5])
            out["top5_overlap"] = len(q_top5 & l_top5)
            out["llm_would_open_with"] = [t for t in order if t in shared][:5]
            out["disagreements"] = [
                {"title": t, "qloo_place": qp, "llm_place": lp}
                for gap, t, qp, lp in gaps[:4] if gap >= max(2, n // 4)]
    return out
