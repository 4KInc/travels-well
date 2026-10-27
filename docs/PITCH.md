# Three minutes, live

For the 5 November show. Every number here matches `/evidence`; if you change
one, run `python3 check_submission.py` and fix the site too.

---

## The script

### 0:00 — One person, one decision (35s)

> Someone programs a horror channel. Not a big streamer — a niche channel with
> a defined audience and a licensing budget that runs out.
>
> Monday morning she has twelve films offered to her and room for five. She
> knows her viewers play Dark Souls and Elden Ring. She has no data connecting
> that to films, so she does what everyone does: she picks by genre tag and by
> what sounds famous.
>
> Two of those five will be wrong, and she will not find out for a year.

Do not say "AI-powered". Say what she is holding and what she has to decide.

### 0:35 — The thing we measured first (30s)

> Before building anything we tested the obvious assumption — that where an
> audience lives predicts what it watches. Pin a catalogue in Qloo and vary the
> city across New York, São Paulo, Tokyo, Mumbai and Berlin.
>
> The affinities come back **identical to four decimal places**. The location
> filter is ignored for film. The location *signal* does change the answer, but
> it returns so little of the catalogue that there is nothing left to compare.
> Either way you cannot route a slate by city.
>
> That killed the product we were going to build, on day one. What does move it
> is what an audience already plays and watches.

This is the credibility moment with the Qloo seats on the panel. It is a
measurement about their API that most entrants will not have made.

### 1:05 — The demo (50s)

Open `/` — it is already answered, nothing to wait for.

> Same twelve films, ranked twice. On the left with Qloo's taste graph. On the
> right, the same question to a language model that sees the identical two
> lists and nothing else.
>
> **One title in common out of five.**
>
> > Its picks lean toward notoriously transgressive titles — Martyrs, Ichi the
> Killer, Tetsuo. Ours lean toward what Qloo’s graph associates with those
> players: Train to Busan, The Host, Battle Royale.
>
> And here is the part I would check if I were you. Ask our side where the
> model's picks belong for this audience: **6th, 8th, 9th and 11th of 11.** Its
> top pick is our last.

Then click one `why ›` drawer.

> Every one of these is traceable. That is Qloo's own explainability telling us
> which of her games drove the title.

### 1:55 — The part nobody else will show you (40s)

Scroll to the withheld row, then open `/slate` on the refusal preset.

> This title got **no verdict**. We read every audience twice through two
> halves that share no games, and these two readings disagreed about it. We
> could have averaged them into a confident number. We withheld it instead.
>
> And this preset refuses outright. Springsteen, Beyoncé and Taylor Swift are
> three different audiences wearing one city's name — their two readings agree
> at 0.13, so nothing measured against them means anything. The agent says so
> and stops.
>
> A tool that always answers is not a tool you can licence against.

### 2:35 — The business, and the close (25s)

> The input is a list she already keeps. Niche SVOD and FAST programmers,
> distributors, sales agents — all making this decision monthly, all with genre
> tags and a model's sense of fame as their substitute for taste data.
>
> We have not sold it, so there is no revenue slide and no pricing number — the
> hypothesis is on the about page, labelled as one.
>
> Everything I have shown you is on the evidence page with the assumption that
> limits it, including the four pairs that qualified in our selection sweep and
> the forty-four that did not.

---

## Questions, with answers

**"Isn't this just ChatGPT with extra steps?"**
> We shipped the comparison rather than the claim. On this audience a frontier
> model shares one title of five with us. It is a strong baseline — on most
> inputs it gets three or four of five, and if you offer it the chance to
> decline it takes it — we tested that, and it withheld 6/7/7 of twelve, more than
> we did.
>
> The difference is not that it cannot say no. It is what the no rests on. We
> withhold a title when two disjoint readings of the audience place it far
> apart — a measurement we can show you. It withholds on its own sense of its
> confidence, and it withheld three of the five titles the graph ranks highest
> here. Neither of us can be proved right. Only one of us can show the
> working.

**"Who pays, and how much?"**
> Programmers at niche SVOD and FAST channels, distributors, international
> sales agents. We have not sold it, so any number I gave you would be
> invented. The shape we would test is per-seat for a programming team with a
> catalogue tier above it, priced against one wrong licensing decision rather
> than per query — because the product sometimes answers "not enough
> evidence", and you should not be charged more for the honest answer.

**"How big can this get?"**
> The engine is catalogue-agnostic: music programming, live-event booking and
> sponsorship fit are the same question with a different catalogue. I will not
> oversell it — we measured cross-domain signal strength per domain, and brands
> score 0.39 where games score 0.08, so sponsorship starts as a negative result
> to overturn rather than an adjacent market to claim.

**"What if Qloo's data is wrong?"**
> Then we want to find out, so we built the checks that would catch it. Every
> audience is read twice through disjoint halves. We backtested against
> Wikipedia pageview ranks collected before any Qloo call — it agrees in Mumbai
> and Berlin and **not** in the other three markets, and we publish that. And
> the agent abstains rather than ranking when the evidence is thin.

**"Why does location not matter?"**
> It is a measurement, not an opinion: pin the candidate set, vary
> `filter.location.query` across five cities, and the affinities are identical
> to four decimals. It *is* honoured for places — it is film where it does
> nothing. We tested neighbourhood granularity too, Bronx against Manhattan,
> and abandoned it for the same reason.

**"What would you do with $25k?"**
> Two things. Get the catalogue feed working so an acquisitions list imports
> instead of being typed — that is what turns this from a demo into something
> used on a Tuesday. And run the same domain measurement for music and live
> events before claiming either, because right now I would be guessing.

**"Why you?"**
> Because I built the thing that could have killed it first. Day one was a
> verification harness with the thresholds hashed before any data was
> collected, and it found that the product I intended to build did not work. I
> would rather ship a smaller true claim than a larger one I cannot defend.

**If asked about the separation caveat** — and a sharp judge will be:
> Good catch, and it is on the page rather than buried. Every pair that
> qualified in our sweep sits below the 0.35 separation floor, which was in the
> code nine days before the sweep ran. So the five titles hold up — all five
> survive re-reading from a separate set of games — but the order within them
> is uncertain, and we label it that way rather than moving the floor.

---

## If the demo breaks

1. **The site is a recorded run.** The landing page spends no Qloo calls, so
   nothing about quota or the API can take it down mid-pitch.
2. **If the network goes**, the gallery images in `docs/gallery/` are the demo:
   `1-hero-side-by-side.jpg` is the whole argument in one frame.
3. **If a page misbehaves**, go to `/slate?preset=newyork-refused` — it is the
   smallest page, 2 calls, and it is the refusal story, which is the most
   distinctive thing we have.
4. **Do not** run a custom pitch live on stage. It takes about 40 calls and a
   few seconds, and the prefilled example makes the same point instantly.
5. Health check before you start: `/status` should report
   `presets_all_cached: true`.
