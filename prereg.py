"""Pre-registration: freeze the fixtures and the decision rules before any
data is seen.

The backtest and the kill gates are only worth anything if the thresholds were
chosen in advance. This writes a hashed record so that a sceptical reader --
or a judge -- can confirm the rules were not fitted to the result.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent

RULES = {
    "location_signal_test": {
        "pass_if": ">=2 non-US market pairs with Kendall tau-b < 0.70, each "
                   "with overlap n >= 12, catalog-composition hi95 < 0.85, and "
                   "control-set rank variance below the rest of the catalog",
        "uncertainty_method": "jackknife SE of the observed tau, tested against "
                              "the 0.70 threshold. The null SE (0.1427 at n=25) "
                              "is reported as a different-from-random sanity "
                              "line only: tau's variance shrinks toward 0 as tau "
                              "approaches 1, so judging an observed tau near the "
                              "top against a null-hypothesis spread mixes two "
                              "distributions and overstates uncertainty.",
        "overlap_floor": "Pairs sharing fewer than 12 titles are marked "
                         "INSUFFICIENT_OVERLAP and cannot qualify. Surviving "
                         "titles skew to the globally popular ones, which are "
                         "least likely to reorder, so a thin overlap biases tau "
                         "upward.",
        "decides": "Catalog Passport is viable",
    },
    "groundwork_gap_test": {
        "metric": "gap = (best shipped LLM configuration) - (Qloo), both "
                  "verified by the same OpenStreetMap instrument",
        "alive_if": "95% Newcombe lower bound on the gap above 0 AND point "
                    "estimate >= 10 points",
        "dead_if": "lower bound includes 0",
        "arms": "ungrounded LLM, grounded LLM with search, Qloo control",
        "script_coverage_amendment": {
            "finding": "OpenStreetMap stores many Japanese venues only under "
                       "Japanese script, so romanised names return no hit and "
                       "are scored as hallucinations. Osaka returned 62% "
                       "not-found in BOTH LLM arms, including famous real "
                       "institutions (Kushikatsu Daruma, Jiyuken Curry).",
            "decision": "The headline gap is computed over Latin-script "
                        "markets only (Lisbon, Medellin). Osaka is reported "
                        "separately and labelled as beyond this instrument.",
            "why_this_is_not_cherry_picking": "The exclusion is a property of "
                       "the verifier, not of any arm: the bias hits every arm "
                       "equally, and both LLM arms failed Osaka at the same "
                       "rate. Excluding it favours neither branch. The Qloo "
                       "arm would be flattered or punished by the same effect "
                       "depending on whether its place names are romanised, "
                       "which is itself unknown until the key arrives.",
        },
        "supersedes": "An earlier registration set >=25% / <=10% against the "
                      "LLM's OWN failure rate. Adding the Qloo control changed "
                      "what is being measured -- a rate became a difference -- "
                      "so the threshold had to be re-derived rather than "
                      "carried over. This is a LOOSENING of the bar and is "
                      "recorded as such. No live call had been made when it "
                      "was changed.",
        "decides": "whether the Groundwork branch has a premise at all",
    },
    "normalisation_test": {
        "per_query_if": "the same entity's affinity changes between two "
                        "different candidate sets",
        "consequence": "all cross-call ratio maths is abandoned in favour of "
                       "within-query ranks",
    },
    "planned_backtest": {
        "design": "predict relative country-level performance for the catalog "
                  "from Qloo ranks alone, compare against public country box "
                  "office splits",
        "honesty_constraints": [
            "titles and metric fixed here, before outcomes are looked up",
            "Qloo's graph is built partly from real consumption signal, so this "
            "is less circular than scoring Qloo with Qloo, NOT independent of it",
            "report N and the confidence interval, never a bare correlation",
        ],
    },
}


def content_digest(catalog, prompts):
    """Hash the CONTENT only -- never the timestamp. A digest that changes on
    every run proves nothing about what was fixed in advance."""
    blob = json.dumps({"catalog": catalog, "prompts": prompts,
                       "decision_rules": RULES}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def write():
    catalog = json.loads((HERE / "fixtures" / "catalog.json").read_text())
    prompts = json.loads((HERE / "fixtures" / "prompts.json").read_text())
    digest = content_digest(catalog, prompts)
    out = HERE / "out" / "prereg.json"
    out.parent.mkdir(exist_ok=True)

    if out.exists():
        prior = json.loads(out.read_text())
        if prior.get("sha256") == digest:
            return digest  # same rules, same fixtures: leave the original alone
        # Fixtures or thresholds changed after registration. Keep the original
        # and record the amendment beside it, so the edit is visible rather
        # than silent. Thresholds moved after seeing data are worthless.
        amended = HERE / "out" / ("prereg_amended_%s.json" % digest[:12])
        amended.write_text(json.dumps({
            "amended_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "supersedes_sha256": prior.get("sha256"),
            "sha256": digest, "catalog": catalog, "prompts": prompts,
            "decision_rules": RULES,
            "warning": "Original pre-registration retained in prereg.json. "
                       "Any threshold changed after data was seen must be "
                       "disclosed when the numbers are quoted.",
        }, indent=2))
        print("  !! fixtures/rules changed after registration -> %s" % amended.name)
        return prior.get("sha256")

    out.write_text(json.dumps({
        "registered_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "sha256": digest, "catalog": catalog, "prompts": prompts,
        "decision_rules": RULES,
    }, indent=2))
    return digest


if __name__ == "__main__":
    print("pre-registration sha256:", write())


# --- Hero-preset sweep -------------------------------------------------------
# Registered before the sweep ran. The point of fixing these in advance is that
# "we searched until we found a big divergence" and "we pre-committed to a
# selection rule and reported every candidate" are indistinguishable after the
# fact unless the rule is hashed first.
HERO_RULES = {
    "purpose": ("Select one hero audience x slate pair for the landing page, "
                "where the grounded shortlist and an LLM with no taste graph "
                "differ materially, without cherry-picking."),
    "candidate_generation": {
        "source": "fixtures/hero_candidates.json, fixed before any sweep data",
        "audiences": ("12 candidates, each described by 3-5 entities drawn only "
                      "from television, video games and music -- the three "
                      "domains measured to discriminate film taste (0.06, 0.08, "
                      "0.11). Music is a minority of any audience."),
        "slates": "4 candidate slates of 12 films each",
        "pairs": "every audience x slate pair is evaluated; none skipped",
    },
    "llm_baseline": {
        "provider": "google",
        "model": "gemini-2.5-flash",
        "temperature": 0.0,
        "repeats": 3,
        "aggregate": ("modal top five across repeats; a title counts toward "
                      "top-5 overlap only if it appears in the model's top "
                      "five in at least 2 of 3 repeats"),
        "prompt_mode": ("audience mode: LIST A names what the audience already "
                        "loves, LIST B is the catalogue to rank. The model "
                        "sees the same describing entities Qloo does."),
        "run_when": ("only for pairs that already pass the grounded quality "
                     "gates below, since the comparison cannot rescue a pair "
                     "that fails them"),
    },
    "selection_criteria_all_must_hold": {
        "top5_overlap_max": 2,
        "buyer_halves_agree_min": 0.50,   # the existing WEAK_HALVES threshold
        "withheld_max": 3,
        "no_abort_or_abstain": True,
        "every_divergent_grounded_top5_title_has_evidence": (
            "shared Qloo tags and/or driving audience entities, with the "
            "supporting call recorded through taste/evidence.py"),
    },
    "tie_break_in_order": [
        "largest divergence (fewest shared titles in the top five)",
        "highest buyer split-half agreement",
        "fewest withheld titles",
        "audience id, alphabetically, so the result is deterministic",
    ],
    "if_nothing_qualifies": ("report the closest candidates and their metrics "
                             "and propose a further amendment; do not loosen "
                             "these criteria silently"),
    "reporting": ("every candidate evaluated is listed in docs/HERO_SWEEP.md "
                  "with its metrics, qualifying or not"),
}


def write_hero():
    """Amendment covering the hero sweep. Named to match the existing
    `prereg_amended_*` pattern so .gitignore keeps tracking it: a record that
    lives only on disk proves nothing."""
    candidates = json.loads((HERE / "fixtures" / "hero_candidates.json").read_text())
    blob = json.dumps({"candidates": candidates, "decision_rules": HERO_RULES},
                      sort_keys=True)
    digest = hashlib.sha256(blob.encode()).hexdigest()
    out = HERE / "out" / ("prereg_amended_hero_%s.json" % digest[:12])
    out.parent.mkdir(exist_ok=True)
    if out.exists():
        return digest
    prior = sorted(q for q in (HERE / "out").glob("prereg_amended_hero_*.json")
                   if q != out)
    out.write_text(json.dumps({
        "amended_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "scope": "hero-preset sweep only; does not supersede the original "
                 "pre-registration in prereg.json",
        "supersedes": [q.name for q in prior] or None,
        "amendment_reason": (
            "The candidate audiences were enlarged from 3-5 entities to 6-8 "
            "after a single smoke-test pair showed that taste/pitch.py cannot "
            "cross-check a describing catalogue smaller than SPLIT_MIN=6: an "
            "audience of four returns no split-half agreement at all, so the "
            "registered quality gate could never have been satisfied by any "
            "pair. No selection criterion, threshold, tie-break or model "
            "setting was changed. One grounded result (anime-jrpg x "
            "world-prestige) had been observed at the time of this amendment; "
            "it is reported in docs/HERO_SWEEP.md with every other candidate."
        ) if prior else None,
        "sha256": digest,
        "candidates": candidates,
        "decision_rules": HERO_RULES,
        "warning": "Registered before the sweep ran. If any criterion here is "
                   "changed after seeing sweep results, the change must be "
                   "disclosed wherever the divergence number is quoted.",
    }, indent=2))
    return digest
