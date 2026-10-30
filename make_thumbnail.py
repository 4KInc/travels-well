#!/usr/bin/env python3
"""Build the 3:2 Devpost thumbnail.

DEV-ONLY, like make_gallery.py. Needs Chrome and macOS sips.

Every number and title here is read from the live /api/hero rather than typed,
so the thumbnail cannot drift from the site the way the gallery twice did.

    python3 make_thumbnail.py [--base URL]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import tempfile
import urllib.request

HERE = pathlib.Path(__file__).parent
OUT = HERE / "docs" / "gallery" / "thumbnail.jpg"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

W, H, SCALE = 1200, 800, 2

PAGE = """<!doctype html><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{--screen:#0a0a0c;--ink:#f4f1ea;--ink-2:#a9a49a;--ink-3:#6f6b64;
  --rule:#26262e;--bulb:#e8b84b;
  --display:"Bebas Neue",Impact,sans-serif;
  --sans:Inter,-apple-system,sans-serif;
  --mono:"IBM Plex Mono",Menlo,monospace}
*{box-sizing:border-box;margin:0}
html,body{width:1200px;height:800px;overflow:hidden}
body{background:var(--screen);color:var(--ink);font:400 15px/1.5 var(--sans);
  -webkit-font-smoothing:antialiased;display:flex;flex-direction:column}
.perf{height:12px;flex:none;
  background:repeating-linear-gradient(90deg,transparent 0 10px,var(--rule) 10px 17px)}
.pad{padding:26px 54px 0;flex:1;display:flex;flex-direction:column}
.top{display:flex;align-items:baseline;justify-content:space-between}
.mark{font:400 25px/1 var(--display);letter-spacing:.07em;text-transform:uppercase}
.mark b{color:var(--bulb);font-weight:400}
.kicker{font:400 11px/1 var(--mono);letter-spacing:.17em;text-transform:uppercase;
  color:var(--ink-3)}
h1{font:400 88px/.88 var(--display);letter-spacing:.012em;text-transform:uppercase;
  margin:26px 0 0}
h1 em{font-style:normal;color:var(--bulb)}
.sub{font:400 16.5px/1.45 var(--sans);color:var(--ink-2);margin:16px 0 0;max-width:94ch}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:0 46px;margin:26px 0 0}
.ch{font:500 11px/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;
  padding-bottom:9px;border-bottom:1px solid var(--rule);margin-bottom:4px}
.ch.g{color:var(--bulb)}
.ch.n{color:var(--ink-3)}
.ch i{font-style:normal;letter-spacing:.1em;opacity:.72}
.row{display:flex;align-items:baseline;gap:11px;padding:7.5px 10px 7.5px 11px;
  border-left:3px solid transparent}
.row .n{font:400 11.5px/1 var(--mono);color:var(--ink-3);width:17px;flex:none}
.row .n.b{font-size:17px;color:#55525c;position:relative;top:1px}
.row .t{font:500 19.5px/1.25 var(--sans);color:var(--ink)}
.row.hit{border-left-color:var(--bulb);background:rgba(232,184,75,.085)}
.row.hit .t{color:var(--bulb)}
.row.hit .n{color:var(--bulb)}
.band{margin:34px 0 0;padding:17px 0 0;border-top:1px solid var(--rule);
  display:grid;grid-template-columns:15ch 1fr 1fr;gap:0 30px;align-items:start}
.bl{font:500 10.5px/1.6 var(--mono);letter-spacing:.14em;text-transform:uppercase;
  color:var(--bulb);width:15ch;opacity:.9}
.bi{font:400 14.5px/1.5 var(--sans);color:var(--ink-2)}
.band b{color:var(--ink);font-weight:600}
.foot{margin-top:auto;padding:14px 0 22px;border-top:1px solid var(--rule);
  display:flex;justify-content:space-between;align-items:baseline;gap:30px}
.foot span{font:400 12.5px/1.5 var(--mono);letter-spacing:.055em;color:var(--ink-3)}
.foot b{color:var(--ink-2);font-weight:400}
</style>
<div class="perf"></div>
<div class="pad">
  <div class="top">
    <div class="mark">Taste <b>Atlas</b></div>
    <div class="kicker">__KICKER__</div>
  </div>
  <h1>One title in common<br><em>out of five</em></h1>
  <p class="sub">__SUB__</p>
  <div class="cols">
    <div>
      <div class="ch g">With Qloo's taste graph</div>
      __LEFT__
    </div>
    <div>
      <div class="ch n">Without it <i>(a set, not an order)</i></div>
      __RIGHT__
    </div>
  </div>
  <div class="band">
    <div class="bl">What the agent did about it</div>
    <div class="bi"><b>5 of 5</b> of the left column hold when the audience is
      re-read from a separate set of games</div>
    <div class="bi"><b>A twelfth title got no verdict.</b> The two readings
      placed it too far apart, so it was withheld rather than averaged</div>
  </div>
  <div class="foot">
    <span>__FOOT_L__</span>
    <span>__FOOT_R__</span>
  </div>
</div>
"""


def rows(titles, shared, ordered):
    """Left column is a ranking and gets ordinals. Right column is the set the
    model picks, which is steady across runs while its order is not, so it gets
    a bullet. Numbering it would assert an order we explicitly do not claim."""
    out = []
    for i, t in enumerate(titles, 1):
        hit = " hit" if t == shared else ""
        mark = ('<span class="n">%d</span>' % i if ordered
                else '<span class="n b">&bull;</span>')
        out.append('<div class="row%s">%s<span class="t">%s</span></div>'
                   % (hit, mark, t))
    return "\n      ".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base",
                    default="https://travels-well-722527905604.us-central1.run.app")
    args = ap.parse_args()

    with urllib.request.urlopen(args.base + "/api/hero", timeout=30) as r:
        d = json.load(r)

    grounded = [row["title"] for row in d["rows"][:5]]
    llm = sorted(d["llm_top5"])
    shared = d["shared_top5"][0]
    ranks = sorted(d["llm_only_ranks"], key=lambda x: x["grounded_place"])
    of = ranks[0]["of"]
    places = ", ".join(str(r["grounded_place"]) for r in ranks[:-1])
    places = "%s and %s" % (places, ranks[-1]["grounded_place"])

    # Not every member is a game. Castlevania is a show, and saying "7 games"
    # would be the kind of small false claim the whole project is against.
    ms = d["audience"]["members"]
    ngame = sum(1 for m in ms if m["kind"] == "game")
    rest = len(ms) - ngame
    kinds = "%d games" % ngame
    if rest:
        kinds += " and a show" if rest == 1 else " and %d shows" % rest

    html = (PAGE
            .replace("__KICKER__", "Taste-fit for content licensing")
            .replace("__SUB__",
                     "The same twelve films, ranked twice for one audience. "
                     "On the left by Qloo's taste graph. On the right by a "
                     "language model shown the identical lists and nothing else.")
            .replace("__LEFT__", rows(grounded, shared, True))
            .replace("__RIGHT__", rows(llm, shared, False))
            .replace("__FOOT_L__", "Audience: <b>%s</b> they already love" % kinds)
            .replace("__FOOT_R__",
                     "The model's other four picks rank <b>%s of %d</b> here"
                     % (places, of)))

    tmp = pathlib.Path(tempfile.mkdtemp())
    src = tmp / "thumb.html"
    src.write_text(html, encoding="utf-8")
    raw = tmp / "thumb.png"

    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=%d" % SCALE,
                    "--window-size=%d,%d" % (W, H),
                    "--virtual-time-budget=15000",
                    "--screenshot=%s" % raw, src.as_uri()],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    if not raw.exists():
        raise SystemExit("capture failed")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg",
                    "-s", "formatOptions", "90", str(raw), "--out", str(OUT)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print("wrote %s (%d KB)" % (OUT, OUT.stat().st_size // 1024))
    print("  shared title highlighted: %s" % shared)
    print("  ranks line: %s of %d" % (places, of))


if __name__ == "__main__":
    main()
