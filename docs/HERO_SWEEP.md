# Hero sweep: every candidate, and why this one

The landing page shows one audience and one slate. This is the record of how that pair was chosen, so the divergence it reports can be read as a selection under a published rule rather than the best thing we happened to find.

**Pre-registered before any of this data existed:** `prereg_amended_hero_9e0c0e0b78bf.json`, sha256 `9e0c0e0b78bff416`. The rules below are read from that file by the sweep itself, not restated here by hand.

## The rule, fixed in advance

All of these had to hold:

- grounded-vs-LLM top-five overlap **<= 2** titles
- buyer split-half agreement **>= 0.50** (the pipeline's existing threshold)
- withheld titles **<= 3** of 12
- no abort and no abstain on the hero path
- every grounded top-five title absent from the LLM's top five has explainable evidence from Qloo

Tie-break, in order: largest divergence (fewest shared titles in the top five); then highest buyer split-half agreement; then fewest withheld titles; then audience id, alphabetically, so the result is deterministic.

Model: gemini-2.5-flash, temperature 0.0, 3 repeats, modal top five across repeats; a title counts toward top-5 overlap only if it appears in the model's top five in at least 2 of 3 repeats. The model ran only for pairs that had already passed the grounded gates, as registered -- the comparison cannot rescue a pair that fails them.

## Result

48 pairs evaluated, **4 qualified**. Cost: 256 Qloo calls (49726 remaining afterwards).

### The four that qualified

| audience | slate | top-5 overlap | halves agree | withheld | low separation |
|---|---|---|---|---|---|
| `horror-games` | `modern-world` | 2 | 0.727 | 2 | False |
| `soulslike` **<- chosen** | `genre-cult` | 1 | 0.848 | 1 | True |
| `indie-art-games` | `world-prestige` | 2 | 0.636 | 2 | True |
| `indie-art-games` | `modern-world` | 1 | 0.788 | 0 | False |

Two pairs tied on divergence at an overlap of 1. The registered tie-break goes to split-half agreement next, and `soulslike` reads 0.848 against `indie-art-games` at 0.788, so it is the one shown.

### Every pair evaluated

| audience | slate | outcome |
|---|---|---|
| `strategy-sim` | `world-prestige` | halves agree 0.364, below 0.50 |
| `strategy-sim` | `genre-cult` | top-5 overlap 4, above 2 |
| `strategy-sim` | `broad-mix` | halves agree 0.061, below 0.50 |
| `strategy-sim` | `modern-world` | halves agree 0.485, below 0.50 |
| `prestige-drama` | `world-prestige` | 4 withheld, above 3 |
| `prestige-drama` | `genre-cult` | halves agree 0.182, below 0.50 |
| `prestige-drama` | `broad-mix` | halves agree 0.485, below 0.50 |
| `prestige-drama` | `modern-world` | halves agree 0.091, below 0.50 |
| `anime-jrpg` | `world-prestige` | top-5 overlap 4, above 2 |
| `anime-jrpg` | `genre-cult` | top-5 overlap 4, above 2 |
| `anime-jrpg` | `broad-mix` | top-5 overlap 3, above 2 |
| `anime-jrpg` | `modern-world` | top-5 overlap 4, above 2 |
| `horror-games` | `world-prestige` | top-5 overlap 3, above 2 |
| `horror-games` | `genre-cult` | top-5 overlap 3, above 2 |
| `horror-games` | `broad-mix` | top-5 overlap 4, above 2 |
| `horror-games` | `modern-world` | **qualified** (overlap 2, agree 0.727) |
| `cozy-games` | `world-prestige` | top-5 overlap 3, above 2 |
| `cozy-games` | `genre-cult` | top-5 overlap 3, above 2 |
| `cozy-games` | `broad-mix` | top-5 overlap 3, above 2 |
| `cozy-games` | `modern-world` | halves agree 0.424, below 0.50 |
| `soulslike` | `world-prestige` | 4 withheld, above 3 |
| `soulslike` | `genre-cult` | **qualified** (overlap 1, agree 0.848) |
| `soulslike` | `broad-mix` | top-5 overlap 3, above 2 |
| `soulslike` | `modern-world` | top-5 overlap 5, above 2 |
| `open-world` | `world-prestige` | top-5 overlap 3, above 2 |
| `open-world` | `genre-cult` | top-5 overlap 5, above 2 |
| `open-world` | `broad-mix` | top-5 overlap 4, above 2 |
| `open-world` | `modern-world` | top-5 overlap 3, above 2 |
| `sitcom-comfort` | `world-prestige` | halves agree 0.455, below 0.50 |
| `sitcom-comfort` | `genre-cult` | top-5 overlap 4, above 2 |
| `sitcom-comfort` | `broad-mix` | top-5 overlap 4, above 2 |
| `sitcom-comfort` | `modern-world` | top-5 overlap 4, above 2 |
| `hard-scifi` | `world-prestige` | top-5 overlap 4, above 2 |
| `hard-scifi` | `genre-cult` | top-5 overlap 3, above 2 |
| `hard-scifi` | `broad-mix` | top-5 overlap 5, above 2 |
| `hard-scifi` | `modern-world` | top-5 overlap 3, above 2 |
| `indie-art-games` | `world-prestige` | **qualified** (overlap 2, agree 0.636) |
| `indie-art-games` | `genre-cult` | top-5 overlap 4, above 2 |
| `indie-art-games` | `broad-mix` | top-5 overlap 3, above 2 |
| `indie-art-games` | `modern-world` | **qualified** (overlap 1, agree 0.788) |
| `street-crime` | `world-prestige` | halves agree 0.455, below 0.50 |
| `street-crime` | `genre-cult` | top-5 overlap 5, above 2 |
| `street-crime` | `broad-mix` | top-5 overlap 4, above 2 |
| `street-crime` | `modern-world` | top-5 overlap 4, above 2 |
| `fighting-arcade` | `world-prestige` | halves agree 0.455, below 0.50 |
| `fighting-arcade` | `genre-cult` | halves agree 0.242, below 0.50 |
| `fighting-arcade` | `broad-mix` | top-5 overlap 4, above 2 |
| `fighting-arcade` | `modern-world` | 4 withheld, above 3 |

## The chosen pair

**Viewers who love punishing action role-playing games** against the `genre-cult` slate.

Described by: Dark Souls, Elden Ring, Bloodborne, Castlevania, Sekiro: Shadows Die Twice, Nioh, Hollow Knight.

| | grounded shortlist | LLM with no taste graph |
|---|---|---|
| 1 | Train to Busan | Martyrs |
| 2 | The Host | Tetsuo: The Iron Man |
| 3 | Battle Royale | Ichi the Killer |
| 4 | The Raid: Redemption | The Raid: Redemption |
| 5 | Cronos | REC |

Shared: **The Raid: Redemption**. The other four differ.

**5 of 5** of the grounded top five appear in both independent readings of this audience, so the selection holds up under re-reading even though the order within it does not.

### What drives each divergent title

Taken from Qloo's own `feature.explainability`, which returns how much each of the audience's entities contributed. Nothing here is written by hand. These say which parts of the audience pull hardest toward a title; they are not evidence that the titles are sharply separated from one another, and the scores below show they are not.

| title | driven most by |
|---|---|
| Train to Busan | Bloodborne (0.159), Nioh (0.158), Sekiro: Shadows Die Twice (0.151) |
| The Host | Hollow Knight (0.178), Nioh (0.153), Bloodborne (0.147) |
| Battle Royale | Hollow Knight (0.177), Nioh (0.153), Bloodborne (0.149) |
| Cronos | Hollow Knight (0.172), Castlevania (0.149), Bloodborne (0.148) |

## What this does not show

- **Not that the model is wrong.** There is no ground truth for what a programmer would license. This is divergence plus the evidence behind one side of it, not a score.
- **Every qualifying pair fell below the separation floor.** The 0.35 floor was in the code from 17 October, nine days before this sweep was registered. Measured on the reading each pair is actually ranked on, all four qualifiers sit under it: soulslike x genre-cult 0.152, indie-art-games x world-prestige 0.140, horror-games x modern-world 0.092, indie-art-games x modern-world 0.076. We label that on the page rather than hide it, and the floor was not recalibrated afterwards to make any pair look better.
- **The separation is weak.** This pair is flagged low-separation: the affinity span across the whole slate is 0.152 (0.713 to 0.865), under the 0.35 floor, so the order within the shortlist should be read as a group rather than a strict ranking. It is labelled that way on the page.
- **The drivers barely discriminate.** The contribution scores sit between 0.136 and 0.206 and the same two or three games lead for almost every title, so they explain the audience's pull toward this kind of cinema better than they explain one title over another.
- **The model's top five was stable; its full ordering was not.** All five of its titles appeared in all 3 repeats, but only 1 of 3 runs produced an identical ordering of the whole slate at temperature 0.
- **One title was withheld** (Audition): the two halves of the audience ranked it too differently to report.

## Amendment history

The candidate pool was enlarged from 3-5 entities per audience to 6-8 after a single smoke-test pair showed that `taste/pitch.py` will not cross-check a describing catalogue smaller than `SPLIT_MIN=6`. Every audience of four returned no split-half agreement at all, so the gate could never have been met for a structural reason. No criterion, threshold, tie-break or model setting changed. Both records are committed: `prereg_amended_hero_9e0c0e0b78bf.json` supersedes `prereg_amended_hero_91e62980a126.json`.

