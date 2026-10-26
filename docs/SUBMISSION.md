# Devpost submission text

Paste-ready. Every number here matches `/evidence` on the live site; both are
generated from the same recorded run.

---

## Elevator pitch (175/200 chars)

An agent that tells anyone licensing content which titles their audience will
actually want — and shows where an AI without Qloo's taste graph would have
guessed differently.

---

## About the project

**For an audience described by the games it loves, four of our five
recommendations are titles a language model without Qloo would not have
picked — and its own picks land 8th, 9th and 11th of 11 for that audience.**
We measured four ways Qloo's API behaves differently from how entrants assume
it does, and built the agent to refuse when the evidence is weak.

### What it does

Describe an audience by what it already loves — games, television, music — and
it ranks a catalogue for them. The landing page shows one worked case.

The audience: viewers who love **Dark Souls, Elden Ring, Bloodborne, Sekiro,
Nioh, Hollow Knight and Castlevania**. The catalogue: twelve genre and cult
films. Both columns rank the same twelve; only one can see Qloo.

| | With the taste graph | Without it |
|---|---|---|
| | Train to Busan | Ichi the Killer |
| | The Host | Martyrs |
| | Battle Royale | REC |
| | **The Raid: Redemption** | **The Raid: Redemption** |
| | Cronos | Tetsuo: The Iron Man |

One title in common. The model read *punishing* as transgressive content;
the graph read it as what those players actually watch. Asked where the
model's own picks belong for this audience, the grounded reading puts
**Ichi the Killer 8th, Martyrs 9th and REC last of 11**.

Two more surfaces run the same engine: an **Audience Map** of 18 audiences
discovered by clustering the graph, and a **Pitch desk** where you type your
own catalogue and audience.

### What makes it agentic

It plans, re-probes, and is allowed to say no.

- **Re-probe.** A reading too flat to separate anything is re-run against the
  most distinctive half of the describing catalogue.
- **Re-split.** Halves that disagree are divided a different way, in case the
  disagreement was an artefact of the division rather than the catalogue.
- **Withhold.** Every audience is read twice through disjoint halves. A title
  the two readings place far apart gets **no verdict** rather than an average
  that looks confident. One title is withheld on the landing page.
- **Abstain.** Too little coverage, and it names the test that failed.
- **Abort.** A home audience whose own halves agree at only 0.13 — Springsteen,
  Beyoncé and Taylor Swift are three audiences wearing one city's name —
  cannot anchor a comparison. That case ships as a preset on purpose.

Every step records what it saw and what it did about it. No claim renders
without the API call that supports it (`taste/evidence.py` raises otherwise).

### How Qloo powers it

| Qloo surface | What it does here |
|---|---|
| `/search` | Resolves every title, game and show; unresolvable names are reported, never guessed |
| `/v2/insights` + `filter.results.entities` | Scores a pinned catalogue inside one query, so rank positions are comparable by construction |
| `/v2/insights` + `signal.interests.entities` | Carries an audience as the things it already loves, across entity types |
| `query.affinity`, never `popularity` | Ranking uses affinity only, with no fallback to global fame |
| `feature.explainability` | Names which of the audience's own entities drive each title |
| Entity `tags` | Audiences on the map name themselves from tags their members share |
| `properties.image` | Every poster comes from Qloo's CDN |
| `/v2/tags`, `/v2/analysis/compare` | Used by the verification harness |

### Why it would not work without Qloo

There is a **"Without Qloo" comparison** built into the product rather than
asserted in a README. It runs the same agent with the graph removed.

The honest result: a frontier model is a strong baseline. It shares three to
four of the top five on most inputs, and its *set* of five is steady across
repeats. What it cannot do is **decline** — it ranked every title confidently
where this run withheld one and reported that only 5 of 5 picks survived
re-reading. It also cannot tell you which titles rank the same for every
audience.

On the landing page's audience, **set overlap is 1 of 5**. Rank correlation is
−0.24 across three runs, but with 11 titles the null standard error is 0.23, so
that sits about one standard error from zero: read it as *no agreement*, not as
measured opposition. The set overlap is the number that means something.

### What we measured about the API, before building on it

Thresholds were registered and hashed **before** any data was collected. Every
parameter was differential-tested — assert the response *changes* when it is
removed — because this API silently ignores what it does not understand, which
makes an untested parameter indistinguishable from a working one.

- **`filter.location.query` is silently ignored for movies.** Pin a catalogue
  and vary the city across five markets: affinities come back identical to four
  decimals. It *is* honoured for places. Any entry that pins a set and varies
  location is reading a parameter the API never applied.
- **`affinity` and `popularity` sit side by side.** An early version of our
  client read popularity, which is identical in every market — every audience
  would have looked the same, and we would have shipped that as a finding.
- **Affinity is not normalised per candidate set.** It varies with the signal,
  not the set.
- **Cross-domain signal strength varies enormously.** Television (0.06), video
  games (0.08) and music (0.11) discriminate film taste sharply; brands (0.39),
  books (0.70), podcasts (0.72) and places (0.67–0.98) barely or not at all.
  Audiences are built only from the three that work.
- **`take` is capped at 50.** A larger value returns a 400 that reads
  downstream as "no data".

### Validation, and what it assumes

- **11 of 11** regionally-skewed films rank highest with their own home
  audience (p = 0.0005). This is a **validity check, not a finding** — it is
  what a working system should do.
- **10 of 11** survive replacing every anchor artist (p = 0.0059). This is the
  result with weight: the effect belongs to the audience, not to the names we
  picked.
- **67%** of cluster pairings survive bootstrap resampling.
- **2 of 5** markets agree with an external backtest against Wikipedia pageview
  ranks collected before any Qloo call. Reported either way.
- The landing page's pair was chosen from **48** audience-and-catalogue
  combinations by a rule hashed before the data existed; **4** qualified. Every
  candidate and the reason it did or did not qualify is published in
  `docs/HERO_SWEEP.md`.

### Honest limits

- The two readings of an audience are **disjoint, not independent**. They share
  no entities, but both come out of the same graph, so their agreement is a
  consistency check rather than corroboration.
- **Every pair that qualified in the selection sweep fell below the 0.35
  separation floor**, which was in the code nine days before the sweep was
  registered. The landing page is labelled low-separation rather than having
  the floor quietly moved: the five titles hold up, the order within them is
  less certain.
- The explainability drivers barely discriminate between titles — the same two
  or three games lead almost every one. They say which part of an audience
  pulls hardest, not that the titles are sharply separated.
- 15 of the 18 map audiences are too small to split into halves that can
  disagree, and are drawn dashed rather than implying a check that did not run.
- Divergence from a language model is **not** evidence the model is wrong.
  There is no ground truth for what a programmer would license.
- Qloo knows brands, not products: this works for films, artists, places,
  books, shows, podcasts and games, not arbitrary retail SKUs.

### The business case

Programmers at niche SVOD and FAST channels, distributors, and international
sales agents all make the same decision repeatedly — which titles for which
audience — with genre tags and a language model's sense of fame as the
substitutes for taste data. The input this needs is a list they already keep.
Pricing is an open hypothesis, stated as one on `/about`; we have not sold
this, so there is no number there.

### How to try it

Everything except a custom run costs **zero** Qloo calls — the landing page,
the map and all four presets are recorded runs served from the image.

1. **/** — the worked case above, already answered.
2. **/pitch** — type your own audience and catalogue.
3. **/slate** — four fixed presets, including one the agent refuses outright.
4. **/evidence** — every measurement, with the assumption that limits it.

### Built with

Python 3.12, standard library only — no dependencies and no build step. A
hand-rolled HTTP server on Cloud Run behind a Dockerfile. Kendall tau-b,
jackknife standard errors, Wilson and Newcombe intervals, bootstrap resampling,
average-linkage clustering and classical MDS are all implemented from scratch,
which keeps the whole thing auditable in one sitting. 57 tests.
