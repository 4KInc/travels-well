# The Taste Atlas

**For an audience described by the games it loves, four of our five
recommendations are titles a language model without Qloo did not choose in
any of 6 runs
— and the model's four other picks rank 6th, 8th, 9th and 11th of 11
for that audience.**

Describe an audience by what it already loves — games, television, music — and
this ranks a catalogue for them, shows where an AI without the taste graph
would have guessed differently, and refuses when the evidence is too thin to
carry a decision.

**Live:** https://travels-well-722527905604.us-central1.run.app
&nbsp;·&nbsp; **[Evidence](https://travels-well-722527905604.us-central1.run.app/evidence)**
&nbsp;·&nbsp; MIT

The landing page is that comparison run on a real audience. It is a recorded
run, so opening it spends no Qloo calls.

```bash
cp .env.example .env     # add QLOO_API_KEY
python3 app/server.py    # http://localhost:8080
python3 test_taste.py && python3 test_loop.py && python3 test_startup.py
```

Stdlib only: no dependencies, no build step. A fresh checkout has no recorded
runs — see [What a fresh checkout is missing](#what-a-fresh-checkout-is-missing).

Built for the Qloo Agentic Hackathon. The repository and URL keep the earlier
name `travels-well`; the product is the Taste Atlas.

---

## The finding

**Neither location parameter gives a usable way to route a slate by city.**
Pin a catalogue and vary `filter.location.query` across New York, Sao Paulo,
Tokyo, Mumbai and Berlin and the scores come back identical to four decimals:
the filter is ignored for film. `signal.location.query` does change the
answer, but it returns so little of the catalogue (84% absent in every market)
that nothing can be compared across cities. What *does* move film taste is
what an audience listens to and watches. The full matrix is on
[/evidence](https://travels-well-722527905604.us-central1.run.app/evidence).

So city is the wrong unit, and the API itself shows it. Two sets of musicians
both from New York, anchored on different scenes, rank the same catalogue at
0.26 -- while one of them agrees with a Berlin set at 0.78. Geography never
entered the computation; scene did.

The agent therefore stops assuming who an audience is and discovers it instead. The
groups that come out are smaller and stranger than marketing segments --
Racionais MC's with Snowfall and The Sopranos; Ben Klock with Fela Kuti,
Journey and Breath of the Wild.

## Three surfaces

| Page | What it does | Cost |
|---|---|---|
| `/` **The Atlas** | 18 audiences clustered from 73 anchors over 65 films, laid out by MDS so distance is taste distance. Each names itself from its members' Qloo tags. | precomputed, no API calls |
| `/pitch` **Pitch Desk** | Your slate, and a buyer described by what they have already licensed. Ranks your titles for them against your home audience. | ~32 calls |
| `/slate` **Travels Well** | The same engine on a fixed catalogue, including a preset the agent refuses. | ~10 calls |

## Evidence

- 11 of 11 regionally-skewed films rank highest with their home audience, p = 0.0005
- 10 of 11 survive replacing every anchor artist (p = 0.0059)
- 67% of within-cluster pairings survive bootstrap resampling at the shipped threshold
- Backtest ground truth collected from Wikipedia **before** any Qloo call, pre-registered and committed

Full record, including the negative results, in **[FINDINGS.md](FINDINGS.md)**.

## What we measured about the API

`filter.location.query` is **silently ignored for movies** (honoured for
places). `affinity` and `popularity` sit side by side and confusing them makes
every audience look identical. Affinity is **not** normalised per candidate
set. Cross-domain signal strength varies enormously: TV 0.06, games 0.08,
music 0.11, brands 0.39, books 0.70, podcasts 0.72, places none. `take` caps
at 50.

## Where it refuses

Refusing well is most of the product.

- A market whose two readings disagree about a title **withholds that title**.
- A market too thinly covered to rank **abstains**, naming the gap.
- A **home market whose own two readings disagree cannot be a baseline**. New
  York's agree at 0.13 — three audiences under one city's name — so the agent
  aborts and says why, rather than measuring everything against an unstable
  reference. Mumbai's agree at 0.97 and work fine. One preset demonstrates the
  refusal deliberately.
- A claim with no supporting API call **raises rather than rendering**.

## Run it

```bash
cp .env.example .env          # add QLOO_API_KEY
python3 app/server.py         # http://localhost:8080
```

Stdlib only: no dependencies, no build step.

### What a fresh checkout is missing

**Recorded runs are not committed.** The hackathon's rule on publishing raw
Qloo responses is unresolved — one entrant reports organisers disallow it,
another commits them — so this repository takes the conservative reading and
keeps them out. `app/cache/` is gitignored; the recordings reach the deployed
image through the build context instead.

So a fresh checkout has no recorded runs, and the landing page says so rather
than failing. With a key in `.env`, build them:

```bash
python3 warm_cache.py       # the four slate presets and the pitch example
python3 hero_build.py       # the landing page's recorded run
```

`hero_build.py` reads whichever pair the registered sweep selected, so it
cannot drift from `docs/HERO_SWEEP.md`. To redo the selection itself —
roughly 250 Qloo calls — run `python3 hero_sweep.py` first.

Without a key **and** without recordings the server still starts, every page
still answers, and `/healthz` reports `presets_all_cached: false` with the
missing names. That path has its own test.

### Everything else

```bash
python3 run_agent.py --home "Mumbai · Bollywood playback"   # agent in the terminal
python3 atlas_build.py      # discover audiences: cluster + bootstrap
python3 atlas_view.py       # lay them out by MDS, write the map
python3 name_clusters.py    # let each audience name itself from its tags
python3 test_taste.py && python3 test_loop.py && python3 test_startup.py
```

## How it is built

```
taste/loop.py           the agent: chooses, retries, abstains, records why
taste/qloo_backend.py   consensus scoring over two anchor sets per audience
taste/pitch.py          your slate against a buyer's own catalogue
taste/rank.py           within-query ranks only; nothing divides across calls
taste/abstain.py        the refusal thresholds
taste/evidence.py       a claim with no supporting call cannot be rendered
atlas_build.py          discover audiences: signatures, average linkage, bootstrap
atlas_view.py           classical MDS layout, split-half consensus per cluster
name_clusters.py        names derived from members' shared tags, TF-IDF scored
engine.py               what the server calls for the fixed-catalogue view
app/server.py           public demo, stdlib HTTP, LIVE/CACHED labelled
run_all.py              the verification harness (see docs/HARNESS.md)
```

## Honest limits

Qloo knows brands, not products: films, artists, places, brands, books, shows,
podcasts and games, not arbitrary retail SKUs. Fifteen of the eighteen
clusters have too few members to split into halves that agree with each other
and are labelled single-reading rather than implying a check that did not
happen. The external backtest agrees in Mumbai (tau 0.39) and Berlin (0.20)
and not elsewhere; reported either way, with the reasons.
