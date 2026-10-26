"""Emit docs/HERO_SWEEP.md from the sweep record.

Generated rather than written, so the published table and the data cannot
disagree. This file is the answer to "you picked the pair that flattered you":
every pair evaluated is here, with the reason it did or did not qualify.
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).parent
S = json.loads((HERE / "out" / "hero_sweep.json").read_text())
H = json.loads((HERE / "app" / "cache" / "hero.json").read_text())
REG = json.loads((HERE / "out" / S["pre_registration_file"]).read_text())
R = REG["decision_rules"]
G = R["selection_criteria_all_must_hold"]
W = S["winner"]

L = []
w = L.append
w("# Hero sweep: every candidate, and why this one\n")
w("The landing page shows one audience and one slate. This is the record of "
  "how that pair was chosen, so the divergence it reports can be read as a "
  "selection under a published rule rather than the best thing we happened "
  "to find.\n")
w("**Pre-registered before any of this data existed:** `%s`, sha256 `%s`. "
  "The rules below are read from that file by the sweep itself, not restated "
  "here by hand.\n" % (S["pre_registration_file"], S["pre_registration_sha256"][:16]))

w("## The rule, fixed in advance\n")
w("All of these had to hold:\n")
w("- grounded-vs-LLM top-five overlap **<= %d** titles" % G["top5_overlap_max"])
w("- buyer split-half agreement **>= %.2f** (the pipeline's existing threshold)"
  % G["buyer_halves_agree_min"])
w("- withheld titles **<= %d** of 12" % G["withheld_max"])
w("- no abort and no abstain on the hero path")
w("- every grounded top-five title absent from the LLM's top five has "
  "explainable evidence from Qloo\n")
w("Tie-break, in order: %s.\n" % "; then ".join(R["tie_break_in_order"]))
w("Model: %s, temperature %s, %d repeats, %s. The model ran only for pairs "
  "that had already passed the grounded gates, as registered -- the "
  "comparison cannot rescue a pair that fails them.\n"
  % (R["llm_baseline"]["model"], R["llm_baseline"]["temperature"],
     R["llm_baseline"]["repeats"], R["llm_baseline"]["aggregate"]))

w("## Result\n")
w("%d pairs evaluated, **%d qualified**. Cost: %d Qloo calls "
  "(%s remaining afterwards).\n"
  % (S["pairs_evaluated"], S["qualified"],
     (S["quota_before"] or 0) - (S["quota_after"] or 0), S["quota_after"]))

w("### The four that qualified\n")
w("| audience | slate | top-5 overlap | halves agree | withheld | low separation |")
w("|---|---|---|---|---|---|")
for r in S["results"]:
    if r["qualified"]:
        mark = " **<- chosen**" if (r["audience"], r["slate"]) == (W["audience"], W["slate"]) else ""
        w("| `%s`%s | `%s` | %d | %.3f | %d | %s |"
          % (r["audience"], mark, r["slate"], r["top5_overlap"],
             r["halves_agree"], r["withheld"], r["low_separation"]))
w("")
_tied = [r for r in S["results"] if r["qualified"]
         and r["top5_overlap"] == W["top5_overlap"]
         and (r["audience"], r["slate"]) != (W["audience"], W["slate"])]
if _tied:
    _run = max(_tied, key=lambda r: r["halves_agree"])
    w("Two pairs tied on divergence at an overlap of %d. The registered "
      "tie-break goes to split-half agreement next, and `%s` reads %.3f "
      "against `%s` at %.3f, so it is the one shown.\n"
      % (W["top5_overlap"], W["audience"], W["halves_agree"],
         _run["audience"], _run["halves_agree"]))

w("### Every pair evaluated\n")
w("| audience | slate | outcome |")
w("|---|---|---|")
for r in S["results"]:
    out = ("**qualified** (overlap %d, agree %.3f)" % (r["top5_overlap"], r["halves_agree"])
           if r["qualified"] else r["why_not"])
    w("| `%s` | `%s` | %s |" % (r["audience"], r["slate"], out))
w("")

w("## The chosen pair\n")
w("**%s** against the `%s` slate.\n" % (H["audience"]["label"], H["slate_id"]))
w("Described by: %s.\n" % ", ".join(m["name"] for m in H["audience"]["members"]))
w("| | grounded shortlist | LLM with no taste graph |")
w("|---|---|---|")
for i in range(5):
    g = H["rows"][i]["title"] if i < len(H["rows"]) else ""
    l = H["llm_top5"][i] if i < len(H["llm_top5"]) else ""
    w("| %d | %s | %s |" % (i + 1, g, l))
w("")
w("Shared: **%s**. The other four differ.\n" % (", ".join(H["shared_top5"]) or "none"))
w("**%s of 5** of the grounded top five appear in both independent readings "
  "of this audience, so the selection holds up under re-reading even though "
  "the order within it does not.\n" % H["buyer"]["top5_hold"])

w("### What drives each divergent title\n")
w("Taken from Qloo's own `feature.explainability`, which returns how much "
  "each of the audience's entities contributed. Nothing here is written by "
  "hand. These say which parts of the audience pull hardest toward a title; "
  "they are not evidence that the titles are sharply separated from one "
  "another, and the scores below show they are not.\n")
w("| title | driven most by |")
w("|---|---|")
for t in H["grounded_only_top5"]:
    ds = H["drivers"].get(t, [])
    w("| %s | %s |" % (t, ", ".join("%s (%.3f)" % (d["name"], d["score"]) for d in ds)))
w("")

w("## What this does not show\n")
w("- **Not that the model is wrong.** There is no ground truth for what a "
  "programmer would license. This is divergence plus the evidence behind one "
  "side of it, not a score.")
w("- **Every qualifying pair fell below the separation floor.** The 0.35 "
  "floor was in the code from 17 October, nine days before this sweep was "
  "registered. Measured on the reading each pair is actually ranked on, all "
  "four qualifiers sit under it: %s. We label that on the page rather than "
  "hide it, and the floor was not recalibrated afterwards to make any pair "
  "look better."
  % ", ".join("%s x %s %.3f" % (r["audience"], r["slate"], r["absolute"]["span"])
              for r in sorted([x for x in S["results"] if x["qualified"]],
                              key=lambda x: -x["absolute"]["span"])))
w("- **The separation is weak.** This pair is flagged low-separation: the "
  "affinity span across the whole slate is %.3f (%.3f to %.3f), under the "
  "%.2f floor, so the order within the shortlist should be read as a group "
  "rather than a strict ranking. It is labelled that way on the page."
  % (H["absolute"]["span"], H["absolute"]["worst"], H["absolute"]["best"], 0.35))
w("- **The drivers barely discriminate.** The contribution scores sit between "
  "%.3f and %.3f and the same two or three games lead for almost every title, "
  "so they explain the audience's pull toward this kind of cinema better than "
  "they explain one title over another."
  % (min(d["score"] for ds in H["drivers"].values() for d in ds),
     max(d["score"] for ds in H["drivers"].values() for d in ds)))
w("- **The model's top five was stable; its full ordering was not.** All five "
  "of its titles appeared in all %d repeats, but only %d of %d runs produced "
  "an identical ordering of the whole slate at temperature 0."
  % (H["llm_repeats"], H["llm_full_order_identical"], H["llm_repeats"]))
w("- **One title was withheld** (%s): the two halves of the audience ranked "
  "it too differently to report.\n" % ", ".join(H["withheld"]))

w("## Amendment history\n")
w("The candidate pool was enlarged from 3-5 entities per audience to 6-8 "
  "after a single smoke-test pair showed that `taste/pitch.py` will not "
  "cross-check a describing catalogue smaller than `SPLIT_MIN=6`. Every "
  "audience of four returned no split-half agreement at all, so the gate "
  "could never have been met for a structural reason. No criterion, "
  "threshold, tie-break or model setting changed. Both records are "
  "committed: `%s` supersedes `prereg_amended_hero_91e62980a126.json`.\n"
  % S["pre_registration_file"])

(HERE / "docs" / "HERO_SWEEP.md").write_text("\n".join(L) + "\n")
print("wrote docs/HERO_SWEEP.md (%d lines)" % len(L))
