#!/usr/bin/env python3
"""Does the model decline, when declining is actually offered?

We claimed the baseline "cannot decline". That claim was not earned: the
prompt behind it said "rank ALL of these" and "reply with exactly N strings",
so the model was never given the option. This asks the same question of the
same audience and catalogue, with withholding explicitly available and an
explicit invitation to use it, and reports whatever comes back.

Costs Gemini calls only; no Qloo quota. Dev-only.

    python3 probe_withhold.py
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).parent
HERO = json.loads((HERE / "app" / "cache" / "hero.json").read_text())
RUNS = 3

PROMPT = """You are advising someone who programs films for a streaming audience.

LIST A -- what this AUDIENCE already loves (context only, do NOT rank these):
{members}

LIST B -- the CATALOGUE to choose from ({n} titles):
{titles}

Pick the FIVE titles from LIST B most likely to appeal to that audience.

You do not have to place every title. If the evidence available to you is too
thin to judge a title confidently, put it in "withhold" instead of ranking it.
Withholding is a legitimate answer and is preferred over a guess: say so rather
than filling the list.

Reply ONLY with JSON of the form:
{{"top5": ["...", "..."], "withhold": ["..."], "note": "one sentence"}}
"""


def main():
    from taste import llm_baseline
    if not llm_baseline.available():
        raise SystemExit("No model key configured.")
    import probe_gap

    members = [m["name"] for m in HERO["audience"]["members"]]
    titles = [r["title"] for r in HERO["rows"]] + list(HERO["withheld"])
    prompt = PROMPT.format(members="\n".join("- " + m for m in members),
                           n=len(titles),
                           titles="\n".join("- " + t for t in titles))

    results = []
    for i in range(RUNS):
        raw = probe_gap.call_llm(prompt, grounded=False)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            results.append({"run": i + 1, "error": "unparseable", "raw": raw[:200]})
            continue
        try:
            d = json.loads(m.group(0))
        except ValueError:
            results.append({"run": i + 1, "error": "bad json", "raw": raw[:200]})
            continue
        results.append({"run": i + 1,
                        "top5": d.get("top5") or [],
                        "withhold": d.get("withhold") or [],
                        "note": (d.get("note") or "")[:200]})
        print("run %d: picked %d, withheld %d  %s"
              % (i + 1, len(results[-1]["top5"]), len(results[-1]["withhold"]),
                 results[-1]["note"][:90]))

    ok = [r for r in results if "error" not in r]
    withheld_counts = [len(r["withhold"]) for r in ok]
    verdict = {
        "question": "Does the baseline withhold when withholding is offered?",
        "prompt": prompt,
        "runs": len(ok),
        "withheld_per_run": withheld_counts,
        "declined_at_least_once": any(c > 0 for c in withheld_counts),
        "results": results,
    }
    (HERE / "out" / "withhold_probe.json").write_text(json.dumps(verdict, indent=2))
    print("\nwithheld per run:", withheld_counts)
    print("declined at least once:", verdict["declined_at_least_once"])
    print("written to out/withhold_probe.json")


if __name__ == "__main__":
    main()
