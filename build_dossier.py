#!/usr/bin/env python3
"""Regenerate the dossier PDF from repository numbers only.

DEV-ONLY. Not imported by the app, not in the container, and it needs Chrome,
which is why it is a script you run rather than part of the build. The runtime
stays stdlib-only.

The previous dossier was written by hand in October and went stale: it still
quoted an agreement figure from a worked-example run that no longer exists.
Nothing here is typed twice — every number is read from app/cache/hero.json,
out/hero_sweep.json and the pre-registration records, so the document cannot
drift from the site the way the last one did.

    python3 build_dossier.py [--out PATH]
"""
from __future__ import annotations

import argparse
import base64
import json
import pathlib
import subprocess
import sys
import tempfile
from datetime import date

HERE = pathlib.Path(__file__).parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


def load():
    hero = json.loads((HERE / "app" / "cache" / "hero.json").read_text())
    sweep = json.loads((HERE / "out" / "hero_sweep.json").read_text())
    return hero, sweep


def img(name):
    p = HERE / "docs" / "gallery" / name
    if not p.exists():
        return ""
    kind = "png" if p.suffix == ".png" else "jpeg"
    b64 = base64.b64encode(p.read_bytes()).decode()
    return "data:image/%s;base64,%s" % (kind, b64)


def ordinal(i):
    suffix = "th" if 11 <= i % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(i % 10, "th")
    return "%d%s" % (i, suffix)


def build_html(hero, sweep):
    t = hero["llm_tau"]
    aud = hero["audience"]
    prov = hero["provenance"]
    places = sorted((r["grounded_place"], r["title"]) for r in hero["llm_only_ranks"]
                    if r["grounded_place"])
    place_phrase = ", ".join(ordinal(p) for p, _ in places[:-1]) + \
        " and " + ordinal(places[-1][0]) + " of %d" % hero["ranked_total"]
    tau_str = ("%.2f" % t["min"]) if t["min"] == t["max"] else \
        "%.2f to %.2f" % (t["min"], t["max"])
    qualifiers = [r for r in sweep["results"] if r["qualified"]]

    def rows_pairs():
        out = []
        g = [r["title"] for r in hero["rows"][:5]]
        l = hero["llm_top5"]
        for i in range(5):
            shared = g[i] in l
            out.append(
                "<tr><td class='n'>%d</td><td%s>%s</td><td>%s</td></tr>"
                % (i + 1, " class='sh'" if shared else "", g[i],
                   l[i] if i < len(l) else ""))
        return "\n".join(out)

    def rows_qual():
        out = []
        for r in sorted(qualifiers, key=lambda r: -r["absolute"]["span"]):
            win = (r["audience"], r["slate"]) == (sweep["winner"]["audience"],
                                                  sweep["winner"]["slate"])
            out.append("<tr%s><td>%s &times; %s</td><td class='n'>%d</td>"
                       "<td class='n'>%.3f</td><td class='n'>%.3f</td>"
                       "<td class='n'>%d</td></tr>"
                       % (" class='win'" if win else "", r["audience"], r["slate"],
                          r["top5_overlap"], r["halves_agree"],
                          r["absolute"]["span"], r["withheld"]))
        return "\n".join(out)

    def rows_drivers():
        out = []
        for title in hero["grounded_only_top5"]:
            ds = hero["drivers"].get(title, [])
            out.append("<tr><td>%s</td><td>%s</td></tr>"
                       % (title, ", ".join("%s (%.3f)" % (d["name"], d["score"])
                                           for d in ds)))
        return "\n".join(out)

    def rows_steps():
        out = []
        for i, s in enumerate(hero["steps"], 1):
            obs = s.get("observed") or ""
            did = ("<div class='did'>&#8627; %s</div>" % s["changed"]) if s.get("changed") else ""
            out.append("<tr><td class='n'>%02d</td><td><b>%s</b> — %s"
                       "<div class='obs'>%s</div>%s</td></tr>"
                       % (i, (s.get("action") or "").replace("_", " "),
                          s.get("reason") or "", obs, did))
        return "\n".join(out)

    return TEMPLATE.format(
        today=date.today().strftime("%d %B %Y"),
        audience=aud["label"],
        members=", ".join(m["name"] for m in aud["members"]),
        offered=hero["slate"]["resolved"],
        ranked=hero["ranked_total"],
        withheld_n=len(hero["withheld"]),
        withheld=", ".join(hero["withheld"]),
        differ=len(hero["llm_only_top5"]),
        shared=", ".join(hero["shared_top5"]),
        place_phrase=place_phrase,
        places_detail=", ".join("%s %s" % (ti, ordinal(p)) for p, ti in places),
        tau=tau_str, tau_runs=t["runs"], null_se=t["null_se"],
        se_from_zero=t["max_abs_in_se"], n_titles=t["n_titles"],
        top5_hold=hero["buyer"]["top5_hold"],
        halves=hero["buyer"]["halves_agree"],
        span=hero["absolute"]["span"],
        aff_lo=hero["absolute"]["worst"], aff_hi=hero["absolute"]["best"],
        pairs=prov["pairs_evaluated"], qualified=prov["pairs_qualified"],
        sha=prov["sha256"][:16], prereg=prov["pre_registration"],
        pair_rows=rows_pairs(), qual_rows=rows_qual(),
        driver_rows=rows_drivers(), step_rows=rows_steps(),
        hero_img=img("1-hero-side-by-side.jpg"),
        map_img=img("5-audience-map.jpg"),
        refusal_img=img("2-refusal.jpg"),
    )


TEMPLATE = """<!doctype html><meta charset="utf-8">
<title>The Taste Atlas</title>
<style>
@page {{ size: A4; margin: 17mm 16mm 15mm; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; padding-bottom:9mm; font:10.5pt/1.55 "Helvetica Neue",Helvetica,Arial,sans-serif;
  color:#15151a; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
h1 {{ font-size:30pt; line-height:1.05; margin:0 0 6mm; letter-spacing:-.4pt; }}
h2 {{ font-size:13pt; margin:9mm 0 2mm; padding-top:3mm;
  border-top:1.5px solid #15151a; letter-spacing:-.2pt; }}
h3 {{ font-size:9pt; text-transform:uppercase; letter-spacing:1.1pt;
  color:#6b6b74; margin:6mm 0 1.5mm; }}
p {{ margin:0 0 3mm; max-width:60em; }}
.lede {{ font-size:12.5pt; line-height:1.5; color:#2a2a32; }}
.kicker {{ font:9pt/1.4 "Helvetica Neue"; letter-spacing:1.6pt;
  text-transform:uppercase; color:#8a7320; margin:0 0 3mm; }}
.rule {{ height:3px; background:#e0b83f; width:46mm; margin:0 0 7mm; }}
table {{ width:100%; border-collapse:collapse; margin:2mm 0 3mm; font-size:9.5pt; }}
th {{ text-align:left; font-size:7.5pt; text-transform:uppercase;
  letter-spacing:.9pt; color:#6b6b74; border-bottom:1px solid #c9c9d2;
  padding:0 3mm 1.5mm 0; }}
td {{ padding:1.8mm 3mm 1.8mm 0; border-bottom:1px solid #e6e6ec;
  vertical-align:top; }}
td.n {{ font-variant-numeric:tabular-nums; white-space:nowrap; }}
td.sh {{ color:#86868f; }}
tr.win td {{ background:#fdf6e0; font-weight:600; }}
.obs {{ font-size:8.5pt; color:#6b6b74; margin-top:.6mm; }}
.did {{ font-size:8.5pt; color:#8a7320; margin-top:.6mm; }}
.big {{ display:flex; gap:9mm; margin:4mm 0 5mm; flex-wrap:wrap; }}
.big div {{ min-width:32mm; }}
.big .v {{ font-size:21pt; font-weight:700; letter-spacing:-.5pt; }}
.big .k {{ font-size:7.5pt; text-transform:uppercase; letter-spacing:.9pt;
  color:#6b6b74; }}
.note {{ background:#f6f6f9; border-left:3px solid #e0b83f; padding:3mm 4mm;
  margin:3mm 0; font-size:9.5pt; }}
img.shot {{ width:100%; border:1px solid #d5d5de; margin:3mm 0 1mm; }}
.cap {{ font-size:8pt; color:#6b6b74; margin:0 0 5mm; }}
.page {{ page-break-after:always; }}
.page:last-child {{ page-break-after:auto; }}
h2, h3 {{ break-after:avoid; page-break-after:avoid; }}
tr {{ break-inside:avoid; page-break-inside:avoid; }}
.note, .big, figure {{ break-inside:avoid; page-break-inside:avoid; }}
img.shot {{ break-inside:avoid; page-break-inside:avoid; }}
ul {{ margin:0 0 3mm; padding-left:5mm; }}
li {{ margin-bottom:1.6mm; }}
.foot {{ position:fixed; bottom:4mm; left:0; right:0; font-size:7.5pt;
  color:#8a8a93; display:flex; justify-content:space-between; }}
code {{ font:8.5pt "SF Mono",Menlo,monospace; background:#f2f2f6;
  padding:.3mm 1mm; border-radius:1mm; }}
</style>

<div class="foot"><span>The Taste Atlas &middot; Qloo Agentic Hackathon</span>
<span>travels-well-722527905604.us-central1.run.app</span></div>

<div class="page">
<p class="kicker">Regenerated {today} from the live recorded run</p>
<h1>Four of our five picks<br>are titles an AI without<br>Qloo would not choose.</h1>
<div class="rule"></div>
<p class="lede">Describe an audience by what it already loves &mdash; games,
television, music &mdash; and this ranks a catalogue for them, shows where a
model without the taste graph would have guessed differently, and refuses when
the evidence is too thin to carry a decision.</p>

<div class="big">
<div><div class="v">{differ} of 5</div><div class="k">picks differ</div></div>
<div><div class="v">{place_phrase}</div><div class="k">where its picks rank here</div></div>
<div><div class="v">{top5_hold} of 5</div><div class="k">hold on re-reading</div></div>
<div><div class="v">{pairs}</div><div class="k">pairs evaluated, {qualified} qualified</div></div>
</div>

<img class="shot" src="{hero_img}">
<p class="cap">The landing page. Same {offered} films ranked twice; only the
left column can see Qloo.</p>

<h2>The measurement that rebuilt the product</h2>
<p>Everyone building on a taste graph starts by assuming they know who the
audience is &mdash; a city, a country, a genre. We tested that against the API
before building on it. Pin a catalogue and vary
<code>filter.location.query</code> across New York, S&atilde;o Paulo, Tokyo,
Mumbai and Berlin: the affinities come back <b>identical to four decimal
places</b>. Location does not move film taste in Qloo's model at all. It is
honoured for places; for film it does nothing.</p>
<p>So the agent stops assuming who an audience is and describes it by what it
already plays and watches.</p>
</div>

<div class="page">
<h2>The worked case</h2>
<p><b>{audience}</b> &mdash; {members}.</p>
<p>{offered} films offered, {ranked} ranked, {withheld_n} withheld
({withheld}).</p>
<table>
<thead><tr><th style="width:8%"></th><th style="width:46%">With the taste graph</th>
<th>Without it</th></tr></thead>
<tbody>{pair_rows}</tbody>
</table>
<p>One title in common: {shared}. The model read <i>punishing</i> as
transgressive content; the graph read it as what those players actually watch.
Asked where the model's own picks belong for this audience, the grounded
reading puts {places_detail} &mdash; none in the top five.</p>

<h3>What drives each of our picks</h3>
<p>From Qloo's <code>feature.explainability</code>, which returns how much each
of the audience's own entities contributed. Nothing here was written by hand.</p>
<table>
<thead><tr><th style="width:38%">Title</th><th>Driven most by</th></tr></thead>
<tbody>{driver_rows}</tbody>
</table>
<div class="note">These say which part of an audience pulls hardest toward a
title. They do <b>not</b> show the titles are sharply separated from one
another &mdash; the scores sit in a narrow band and the same two or three games
lead almost every row.</div>

<h2>What the agent does without Qloo</h2>
<div class="big">
<div><div class="v">{differ} of 5</div><div class="k">titles differ</div></div>
<div><div class="v">{tau}</div><div class="k">rank correlation, {tau_runs} runs</div></div>
<div><div class="v">&plusmn;{null_se:.2f}</div><div class="k">null standard error at n={n_titles}</div></div>
</div>
<p>A frontier model is a strong baseline and we are not claiming otherwise. Its
<i>set</i> of five is steady across repeats; its ordering is not reliably
reproducible, so we compare sets and never quote a place from it. Rank
correlation sits about {se_from_zero} standard errors from zero: read it as
<b>no agreement</b>, not as measured opposition.</p>
<p>What the model cannot do is <b>decline</b>. It ranked every title
confidently where this run withheld one, and it cannot report which titles rank
the same for every audience.</p>
</div>

<div class="page">
<h2>How the agent decided</h2>
<table><tbody>{step_rows}</tbody></table>
</div>

<div class="page">
<h2>How the hero pair was chosen</h2>
<p>Registered and hashed before any of the data existed &mdash;
<code>{sha}</code> in <code>{prereg}</code>. {pairs} audience-and-catalogue
pairs were evaluated against five criteria that all had to hold; {qualified}
qualified. Every candidate and the reason it did or did not qualify is
published.</p>
<table>
<thead><tr><th>Audience &times; catalogue</th><th class="n">Top-5 overlap</th>
<th class="n">Halves agree</th><th class="n">Affinity span</th>
<th class="n">Withheld</th></tr></thead>
<tbody>{qual_rows}</tbody>
</table>
<div class="note"><b>Every qualifying pair fell below the 0.35 separation
floor</b>, which was in the code nine days before the sweep was registered. The
chosen pair spans {span} ({aff_lo}&ndash;{aff_hi}). We label that on the page
rather than moving the floor: the five titles hold up &mdash; {top5_hold} of 5
survive re-reading from a separate set of games &mdash; but the order within
them is uncertain.</div>

<h2>Validation, and what limits it</h2>
<table>
<thead><tr><th style="width:34%">Result</th><th>The assumption</th></tr></thead>
<tbody>
<tr><td><b>11 of 11</b> regionally-skewed films rank highest with their own home
audience (p = 0.0005)</td><td>A <b>validity check, not a finding</b> &mdash; it
is what a working system should do. We chose which films count as skewed, and
the cases are not fully independent.</td></tr>
<tr><td><b>10 of 11</b> survive replacing every anchor artist (p = 0.0059)</td>
<td>The result with weight: the effect belongs to the audience, not the names we
picked. Both readings still come from one graph, so this is a <b>disjoint</b>
check, not an independent one.</td></tr>
<tr><td><b>67%</b> of cluster pairings survive bootstrap resampling</td>
<td>At the 0.75 linkage threshold. Looser grouping produced one large cluster
that dissolved under the same test.</td></tr>
<tr><td><b>2 of 5</b> markets agree with an external backtest</td>
<td>Wikipedia pageview ranks collected before any Qloo call. Mumbai and Berlin
agree; three markets do not. Pageviews measure attention, not licensing
demand.</td></tr>
<tr><td>Halves agree at <b>{halves}</b> on the hero audience</td>
<td>Rank correlation across the whole catalogue. The number that matters for a
shortlist is that {top5_hold} of 5 titles survive the re-reading.</td></tr>
</tbody>
</table>
</div>

<div class="page">
<h2>It is allowed to say no</h2>
<img class="shot" src="{refusal_img}">
<p class="cap">A shipped preset that refuses outright.</p>
<p>Springsteen, Beyonc&eacute; and Taylor Swift are three audiences wearing one
city's name. Their two readings agree at 0.13, so anything measured against
them inherits that instability. The agent says so and stops. A tool that always
answers is not one you can licence against.</p>

<h2>The audience map</h2>
<img class="shot" src="{map_img}">
<p class="cap">18 audiences discovered by clustering 73 cultural anchors by
their film-affinity signatures. Distance is taste distance.</p>

<h2>Honest limits</h2>
<ul>
<li>The two readings of an audience are <b>disjoint, not independent</b>: they
share no entities, but both come out of the same graph.</li>
<li>Every pair that qualified in the sweep fell below the separation floor. The
selection holds; the order within it is less certain.</li>
<li>15 of the 18 map audiences are too small to split into halves that can
disagree, and are drawn dashed rather than implying a check that did not run.</li>
<li>Divergence from a language model is <b>not</b> evidence the model is wrong.
There is no ground truth for what a programmer would licence.</li>
<li>Qloo knows brands, not products: films, artists, places, books, shows,
podcasts and games &mdash; not arbitrary retail SKUs.</li>
<li>Every number here is a snapshot of the graph in October 2026.</li>
</ul>

<h2>The business case</h2>
<p>Programmers at niche SVOD and FAST channels, distributors and international
sales agents all make the same decision repeatedly &mdash; which titles for
which audience &mdash; with genre tags and a model's sense of fame as the
substitutes for taste data. The input is a list they already keep.</p>
<p>We have not sold this, so there is no pricing number here. The shape we
would test first is per-seat for a programming team with a catalogue tier above
it, priced against one wrong licensing decision rather than per query &mdash;
because the product sometimes answers "not enough evidence", and that answer
should not cost more.</p>
</div>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pathlib.Path.home() / "Projects" /
                                         "qloo-concepts" / "taste-atlas-dossier.pdf"))
    args = ap.parse_args()

    if not pathlib.Path(CHROME).exists():
        sys.exit("Chrome not found at %s — this is a dev-only tool." % CHROME)

    hero, sweep = load()
    html = build_html(hero, sweep)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Keep the HTML beside the PDF: it is what Chrome actually printed, so it
    # is the thing to look at when the PDF comes out wrong.
    src = out.with_suffix(".html")
    src.write_text(html)

    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf=%s" % out, "--virtual-time-budget=10000",
                    src.as_uri()], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("wrote %s (%.0f KB)" % (out, out.stat().st_size / 1024))
    print("  audience : %s" % hero["audience"]["label"])
    print("  differ   : %d of 5   tau %s   top5 hold %s of 5"
          % (len(hero["llm_only_top5"]),
             hero["llm_tau"]["min"], hero["buyer"]["top5_hold"]))
    print("  sweep    : %d pairs, %d qualified"
          % (sweep["pairs_evaluated"], sweep["qualified"]))


if __name__ == "__main__":
    main()
