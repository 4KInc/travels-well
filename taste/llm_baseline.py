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


def rank(slate_titles, buyer_titles, qloo_ranks=None):
    """Returns the model's ordering and, where possible, its agreement with
    Qloo's. `qloo_ranks` maps title -> rank percentile."""
    if not available():
        return {"available": False, "note": "No model key configured on this server."}
    prompt = (
        "A film buyer's catalogue is:\n%s\n\n"
        "Rank the following films from MOST to LEAST likely to appeal to that "
        "buyer's audience. Reply ONLY with a JSON array of the titles in order, "
        "no prose.\n\n%s"
        % ("\n".join("- " + t for t in buyer_titles), json.dumps(slate_titles)))
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

    known = {t.lower(): t for t in slate_titles}
    order = [known[t.lower()] for t in order if t.lower() in known]
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
            out["top_agreement"] = sum(
                1 for t in list(sorted(shared, key=lambda x: -shared[x]))[:3]
                if l_pos.get(t, 99) < 3)
            out["disagreements"] = [
                {"title": t, "qloo_place": qp, "llm_place": lp}
                for gap, t, qp, lp in gaps[:4] if gap >= max(2, n // 4)]
    return out
