#!/usr/bin/env python3
"""Cut the demo video from page captures and a narration track.

DEV-ONLY, like make_gallery.py. Needs Chrome, ffmpeg and macOS sips.

The narration is the master clock. Each shot is held for exactly as long as
its own audio clip runs, measured with ffprobe rather than estimated, so the
picture cannot drift out of sync with the words. Shots are slow vertical pans
over tall page captures, which is what scrolling the real site looks like.

    python3 make_video.py --vo DIR [--base URL] [--out FILE]

DIR must contain one mp3 per shot, named for the SHOTS keys below.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
FFPROBE = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"

VW, VH, FPS = 1920, 1080, 30

# Page captures: name -> (path, window w, window h, device scale).
# The window has to be taller than the page or the capture is truncated, which
# silently cost us the whole lower half of /evidence the first time.
PAGES = {
    "hero":     ("/", 1600, 2400, 2),
    "evidence": ("/evidence", 1600, 4200, 2),
    "refusal":  ("/slate?preset=newyork-refused", 1600, 1400, 2),
    "pitch":    ("/pitch", 1600, 1600, 2),
    "atlas":    ("/atlas", 1600, 2000, 2),
    "about":    ("/about", 1600, 2000, 2),
    "markets":  ("/slate?preset=mumbai-out", 1600, 1800, 2),
}

# Variants of the hero page with a <details> forced open. A plain capture can
# only ever show them shut, and the driver drawer and the agent trace are two
# of the things most worth showing. Built by dumping the rendered DOM, cutting
# its <script> (which would otherwise rebuild the page from a relative
# /api/hero that does not resolve over file://), then setting the attribute.
VARIANTS = {
    "hero-why":   ('<details class="ev">', '<details class="ev" open>'),
    "hero-trace": ('<details class="trace">', '<details class="trace" open>'),
}
VARIANT_WINDOW = (1600, 2600, 2)

# Shot list, in order. Each is (page, crop w, crop h, crop x, y start, y end).
# Offsets are in captured pixels, so at scale 2 they are twice the CSS value.
SCRIPTS = {
 "sixty": [
    ("1-question",   "hero",     3200, 1800,   0,     0,  140),
    ("2-divergence", "hero",     3200, 1800,   0,   980, 1120),
    ("3a-withheld",  "hero",     2400, 1350, 400,  2400, 2500),
    ("3b-refusal",   "refusal",  3200, 1800,   0,    60,  220),
    ("4-evidence",   "evidence", 3200, 1800,   0,   700, 2050),
 ],
 # Told from the programmer's side rather than the harness's. The
 # statistical caveats stay on the site: in a voiceover they read as
 # showing off, and they are not what the person deciding actually asks.
 "story": [
    # The problem, then the comparison, then why you would believe it, then
    # what you actually do with it, then who it is for.
    ("01-monday",    "hero",       3200, 1800,    0,     0,  150),
    ("02-twice",     "hero",       3200, 1800,    0,   980, 1120),
    ("02b-crossdomain", "hero",    3200, 1800,    0,   380,  500),
    ("03-fourfilms", "hero",       1600,  900, 1560,  1200, 1290),
    ("04-why",       "hero-why",   3200, 1800,    0,   960, 1080),
    ("05-noanswer",  "hero",       2400, 1350,  400,  2400, 2500),
    ("06-shows",     "hero-trace", 2667, 1500,  267,  3000, 3120),
    ("07-refuses",   "refusal",    3200, 1800,    0,    60,  220),
    ("10-workflow",  "pitch",      3200, 1800,    0,     0,   80),
    # Pans from the map down through a picked audience to what it is drawn to
    # and what it is not, which is the half of the screen worth seeing.
    ("11-map",       "atlas",      3200, 1800,    0,   900, 2430),
    ("12-travel",    "markets",    3200, 1800,    0,   950, 1900),
    ("13-whofor",    "about",      3200, 1800,    0,   850, 1050),
    ("08-published", "evidence",   3200, 1800,    0,   700,  900),
    ("09-close",     "pitch",      2800, 1575,    0,    30,   90),
 ],
 "curtest": [
    ("03-fourfilms", "hero",       1600,  900, 1560,  1200, 1290),
 ],
 "full": [
    ("01-question",  "hero",       3200, 1800,    0,     0,  150),
    ("02-fives",     "hero",       3200, 1800,    0,   980, 1120),
    # x=1560 is the gutter between the columns. Starting any further left
    # catches the tail of the left column's rank labels.
    ("03-ranks",     "hero",       1600,  900, 1560,  1200, 1290),
    ("04-why",       "hero-why",   3200, 1800,    0,   960, 1080),
    ("05-withheld",  "hero",       2400, 1350,  400,  2400, 2500),
    ("06-trace",     "hero-trace", 2667, 1500,  267,  3000, 3120),
    ("07-refusal",   "refusal",    3200, 1800,    0,    60,  220),
    ("08-verdicts",  "evidence",   3200, 1800,    0,   700,  900),
    ("09-matrix",    "evidence",   3200, 1800,    0,  2300, 2450),
    ("10-ablation",  "evidence",   3200, 1800,    0,  3350, 3600),
    ("11-close",     "evidence",   2667, 1500,  267,  6340, 6460),
 ],
}

# Presenter picture-in-picture, bottom left. Square corners and a hairline
# border, because that is what the rest of the site looks like.
PIP_W = 384
PIP_MARGIN = 48
PIP_BORDER = 2
PIP_BORDER_COLOR = "0x3a3a44"

CURSOR = HERE / "assets" / "cursor.png"
CURSOR_MOVE = 0.55          # seconds to travel between waypoints
CURSOR_HOTSPOT = (10, 6)    # tip of the arrow inside cursor.png

# Where the pointer goes, per shot. Each waypoint is (arrive_by_seconds,
# page_x, page_y) in CAPTURED PAGE pixels, not video pixels, so a waypoint
# stays pinned to its element while the shot pans underneath it. The first
# waypoint is where the pointer starts.
CURSOR_PATHS = {
    # Times are where the phrase lands in that clip, measured by character
    # offset against the clip's own length. A fourth element overrides the
    # travel time, for a sweep rather than a snap.
    "01-monday": [
        (0.0, 1600, 500), (2.8, 1600, 962, 0.7),
        (7.3, 1060, 725, 0.6), (8.4, 1235, 725, 0.5),
        (11.0, 1600, 890, 0.7), (19.0, 1600, 890)],
    # Aimed at the first row of each column rather than the column headers:
    # the headers sit above the crop once this shot starts panning, so the
    # pointer was being drawn off the top edge.
    "02-twice": [
        (0.0, 1600, 1221), (2.4, 900, 1221, 0.6),
        (7.2, 1750, 1264, 0.7), (11.8, 1000, 1941, 0.8)],
    "02b-crossdomain": [
        (0.0, 1600, 700), (4.4, 1060, 725, 0.5), (5.2, 1235, 725, 0.4),
        (5.9, 1415, 725, 0.4), (7.2, 900, 1300, 0.9),
        (10.0, 900, 1800, 1.5), (19.0, 900, 1800)],
    "03-fourfilms": [
        (0.0, 2140, 1268), (6.0, 2140, 1268), (12.6, 2140, 2012, 3.2)],
    "04-why": [
        (0.0, 900, 1160), (1.5, 900, 1160),
        (2.8, 1000, 1270, 0.7), (12.0, 1000, 1270)],
    "05-noanswer": [
        (0.0, 1400, 2500), (3.8, 650, 2800, 0.8), (13.0, 650, 2800)],
    # Step rows measured off a rendered frame, not estimated: the first guess
    # was ~310px high and the pointer sat on step 04 while the line said six.
    "06-shows": [
        (0.0, 700, 3150), (2.2, 700, 3150), (3.2, 700, 3355, 0.6),
        (4.6, 700, 3355), (6.2, 700, 3738, 0.6), (10.0, 700, 3842, 0.8)],
    "07-refuses": [
        (0.0, 2158, 679), (2.6, 2158, 679), (5.5, 725, 1162, 0.8),
        (7.2, 1400, 1290, 0.6), (12.5, 1400, 1290)],
    "10-workflow": [
        (0.0, 400, 300), (2.6, 300, 300, 0.6), (5.8, 300, 750, 0.7),
        (13.6, 295, 1579, 1.0), (14.8, 1400, 800, 0.8),
        (19.6, 863, 337, 0.8)],
    "11-map": [
        (0.0, 1600, 1500), (4.3, 1600, 1700, 1.0), (11.3, 2530, 1678, 0.8),
        (13.2, 600, 2785, 0.9), (14.0, 900, 2919, 0.5),
        (17.2, 700, 3300, 0.9), (19.2, 600, 3654, 0.7),
        (21.0, 900, 3830, 0.8), (25.0, 900, 3830)],
    "12-travel": [
        (0.0, 1600, 1300), (5.2, 1000, 1450, 0.8), (9.0, 1000, 1937, 0.8),
        (11.0, 1000, 2250, 0.7), (15.3, 1600, 2780, 1.0),
        (23.0, 1600, 2780)],
    "13-whofor": [
        (0.0, 1400, 1079), (3.8, 1000, 1166, 0.7), (7.3, 1000, 1284, 0.6),
        (11.2, 1000, 1403, 0.6), (15.6, 1300, 2600, 1.2),
        (19.4, 1300, 2600)],
    "08-published": [
        (0.0, 1200, 950), (3.0, 1200, 950), (6.0, 2337, 1531, 0.9),
        (7.4, 2302, 1761, 0.6), (8.8, 2345, 2074, 0.6),
        (13.5, 1200, 1100, 1.2), (21.5, 1200, 1100)],
    "09-close": [
        (0.0, 400, 500), (2.0, 300, 750, 0.7), (8.5, 300, 750)],
}

# 3.0 cut too close to the last word: the line landed and the video was gone
# before it had time to sit.
ENDCARD_SECONDS = 5.5
ENDCARD = """<!doctype html><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;500&family=Inter:wght@400;500&display=swap" rel="stylesheet">
<style>
:root{--screen:#0a0a0c;--ink:#f4f1ea;--ink-2:#a9a49a;--ink-3:#6f6b64;
  --rule:#26262e;--bulb:#e8b84b}
*{box-sizing:border-box;margin:0}
html,body{width:1920px;height:1080px;overflow:hidden}
body{background:var(--screen);color:var(--ink);
  font:400 15px/1.5 Inter,-apple-system,sans-serif;-webkit-font-smoothing:antialiased;
  display:flex;flex-direction:column;align-items:center;justify-content:center}
.perf{position:absolute;top:0;left:0;right:0;height:16px;
  background:repeating-linear-gradient(90deg,transparent 0 13px,var(--rule) 13px 22px)}
.perf.b{top:auto;bottom:0}
.mark{font:400 62px/1 "Bebas Neue",Impact,sans-serif;letter-spacing:.07em;
  text-transform:uppercase}
.mark b{color:var(--bulb);font-weight:400}
.rule{width:132px;height:1px;background:var(--rule);margin:30px 0}
.url{font:500 27px/1.5 "IBM Plex Mono",Menlo,monospace;color:var(--bulb);
  letter-spacing:.015em}
.repo{font:400 18px/1.5 "IBM Plex Mono",Menlo,monospace;color:var(--ink-3);
  letter-spacing:.07em;margin-top:15px}
.tag{font:400 20px/1.6 Inter,sans-serif;color:var(--ink-2);margin-top:38px;
  max-width:60ch;text-align:center}
</style>
<div class="perf"></div><div class="perf b"></div>
<div class="mark">Taste <b>Atlas</b></div>
<div class="rule"></div>
<div class="url">__URL__</div>
<div class="repo">__REPO__</div>
<div class="tag">Every number on the site is a recorded run, and every claim
has the API call behind it on the evidence page.</div>
"""


def cursor_expr(points, cw, ch, cx, y0, y1, d):
    """Build ffmpeg overlay x/y expressions for a pointer walking `points`.

    Page coordinates are converted to video coordinates against the same
    moving crop the shot uses, so the pointer tracks its element through the
    pan instead of sliding off it.
    """
    k = VW / float(cw)
    hx, hy = CURSOR_HOTSPOT

    def leg(axis):
        # Innermost value is the final waypoint; wrap outwards in reverse.
        expr = "%.3f" % points[-1][1 if axis == "x" else 2]
        for i in range(len(points) - 1, 0, -1):
            t_at = points[i][0]
            move = points[i][3] if len(points[i]) > 3 else CURSOR_MOVE
            start = max(0.0, t_at - move)
            a = points[i - 1][1 if axis == "x" else 2]
            b = points[i][1 if axis == "x" else 2]
            moving = ("(%.3f+(%.3f)*(t-%.4f)/%.4f)"
                      % (a, b - a, start, max(move, 0.01)))
            expr = ("if(lt(t,%.4f),%.3f,if(lt(t,%.4f),%s,%s))"
                    % (start, a, t_at, moving, expr))
        return expr

    px, py = leg("x"), leg("y")
    xe = "(%s-%d)*%.6f-%d" % (px, cx, k, hx)
    ye = "((%s)-(%.3f+(%.3f)*t/%.4f))*%.6f-%d" % (py, y0, y1 - y0, d, k, hy)
    return xe, ye


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def duration(path):
    out = subprocess.run([FFPROBE, "-v", "quiet", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


def capture(base, tmp, need):
    shots = {}
    for name, (path, w, h, scale) in PAGES.items():
        if name not in need and not any(v in need for v in VARIANTS):
            continue
        dest = tmp / ("page-%s.png" % name)
        run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=%d" % scale,
             "--window-size=%d,%d" % (w, h),
             "--virtual-time-budget=20000",
             "--screenshot=%s" % dest, base + path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not dest.exists():
            sys.exit("capture failed for %s" % name)
        shots[name] = dest

    # Variants are derived from the hero page's own rendered DOM.
    if any(v in need for v in VARIANTS):
        dom = tmp / "hero-dom.html"
        out = subprocess.run([CHROME, "--headless", "--disable-gpu",
                              "--virtual-time-budget=20000", "--dump-dom",
                              base + "/"], capture_output=True, text=True).stdout
        dom.write_text(out, encoding="utf-8")
        static = re.sub(r"<script\b[^>]*>.*?</script>", "", out, flags=re.S | re.I)
        vw, vh, vs = VARIANT_WINDOW
        for vname, (find, repl) in VARIANTS.items():
            if vname not in need:
                continue
            src = tmp / (vname + ".html")
            if find not in static:
                sys.exit("variant %s: could not find %r in the dumped DOM"
                         % (vname, find))
            src.write_text(static.replace(find, repl, 1), encoding="utf-8")
            dest = tmp / ("page-%s.png" % vname)
            run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                 "--force-device-scale-factor=%d" % vs,
                 "--window-size=%d,%d" % (vw, vh),
                 "--virtual-time-budget=20000",
                 "--screenshot=%s" % dest, src.as_uri()],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not dest.exists():
                sys.exit("capture failed for variant %s" % vname)
            shots[vname] = dest
    return shots


def endcard(base, repo, tmp):
    src = tmp / "endcard.html"
    src.write_text(ENDCARD.replace("__URL__", base.replace("https://", ""))
                          .replace("__REPO__", repo), encoding="utf-8")
    dest = tmp / "endcard.png"
    run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-device-scale-factor=1", "--window-size=%d,%d" % (VW, VH),
         "--virtual-time-budget=12000", "--screenshot=%s" % dest, src.as_uri()],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vo", required=True, help="directory of narration mp3s")
    ap.add_argument("--base",
                    default="https://travels-well-722527905604.us-central1.run.app")
    ap.add_argument("--repo", default="github.com/4KInc/travels-well")
    ap.add_argument("--script", default="sixty", choices=sorted(SCRIPTS))
    ap.add_argument("--no-cursor", action="store_true",
                    help="render without the guide pointer")
    ap.add_argument("--pip", help="presenter video: one clip per shot in a "
                                  "directory (named like the shots), or a "
                                  "single file spanning the whole timeline")
    ap.add_argument("--out")
    args = ap.parse_args()
    shots = SCRIPTS[args.script]
    out_path = args.out or str(HERE / "docs" / "gallery" /
                               {"sixty": "demo-60.mp4",
                                "full": "demo-full.mp4",
                                "story": "demo.mp4",
                                "curtest": "curtest.mp4"}[args.script])

    vo = pathlib.Path(args.vo)
    clips = []
    for name, *_ in shots:
        f = vo / (name + ".mp3")
        if not f.exists():
            sys.exit("missing narration clip: %s" % f)
        clips.append(f)

    tmp = pathlib.Path(tempfile.mkdtemp())
    print("capturing pages ...")
    pages = capture(args.base, tmp, {sh[1] for sh in shots})
    card = endcard(args.base, args.repo, tmp)

    pip_dir = pip_file = None
    if args.pip:
        pp = pathlib.Path(args.pip)
        if pp.is_dir():
            pip_dir = pp
        elif pp.is_file():
            pip_file = pp
        else:
            sys.exit("--pip: no such file or directory: %s" % pp)

    print("cutting shots ...")
    parts, t = [], 0.0
    for (name, page, cw, ch, cx, y0, y1), clip in zip(shots, clips):
        d = duration(clip)
        # ffmpeg 9 dropped crop's eval option: w/h/x/y are timeline-evaluated
        # by default now, so an expression in t pans on its own. On ffmpeg 7
        # and older this needs ":eval=frame" appended or the pan sits still.
        y = "%d+(%d)*t/%.4f" % (y0, y1 - y0, d)
        out = tmp / ("shot-%s.mp4" % name)
        base = ("format=rgb24,crop=w=%d:h=%d:x=%d:y='%s',"
                "scale=%d:%d:flags=lanczos" % (cw, ch, cx, y, VW, VH))

        over = None
        if pip_dir:
            for ext in (".mp4", ".mov", ".webm", ".m4v"):
                cand = pip_dir / (name + ext)
                if cand.exists():
                    over = (cand, 0.0)
                    break
        elif pip_file:
            over = (pip_file, t)

        pts = CURSOR_PATHS.get(name) if not args.no_cursor else None

        cmd = [FFMPEG, "-y", "-v", "error",
               "-loop", "1", "-framerate", str(FPS), "-t", "%.4f" % d,
               "-i", str(pages[page])]
        graph = ["[0:v]%s[v0]" % base]
        last, idx = "v0", 1

        if pts:
            if not CURSOR.exists():
                sys.exit("cursor asset missing: %s" % CURSOR)
            cmd += ["-loop", "1", "-framerate", str(FPS), "-t", "%.4f" % d,
                    "-i", str(CURSOR)]
            xe, ye = cursor_expr(pts, cw, ch, cx, y0, y1, d)
            graph.append("[%s][%d:v]overlay=x='%s':y='%s'[v%d]"
                         % (last, idx, xe, ye, idx))
            last, idx = "v%d" % idx, idx + 1

        if over:
            src, seek = over
            cmd += ["-ss", "%.4f" % seek, "-i", str(src)]
            # Trimmed to the shot and frozen on its last frame if it runs
            # short, so a clip that does not quite reach leaves no hole.
            graph.append("[%d:v]scale=%d:-2,tpad=stop_mode=clone:stop_duration=%.4f,"
                         "trim=0:%.4f,setpts=PTS-STARTPTS,"
                         "pad=iw+%d:ih+%d:%d:%d:color=%s[pipsrc]"
                         % (idx, PIP_W, d, d, PIP_BORDER * 2, PIP_BORDER * 2,
                            PIP_BORDER, PIP_BORDER, PIP_BORDER_COLOR))
            graph.append("[%s][pipsrc]overlay=x=%d:y=H-h-%d:shortest=0[v%d]"
                         % (last, PIP_MARGIN, PIP_MARGIN, idx))
            last, idx = "v%d" % idx, idx + 1

        graph.append("[%s]format=yuv420p[v]" % last)
        cmd += ["-filter_complex", ";".join(graph), "-map", "[v]",
                "-t", "%.4f" % d,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-r", str(FPS), str(out)]
        run(cmd)
        parts.append(out)
        print("  %-14s %6.2f -> %6.2f  (%5.2fs)  %s%s"
              % (name, t, t + d, d, page,
                 ("  +cursor" if pts else "") + ("  +pip" if over else "")))
        t += d

    out = tmp / "shot-endcard.mp4"
    run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-framerate", str(FPS),
         "-t", "%.4f" % ENDCARD_SECONDS, "-i", str(card),
         "-vf", "format=rgb24,scale=%d:%d,format=yuv420p" % (VW, VH),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-r", str(FPS), str(out)])
    parts.append(out)
    print("  %-14s %6.2f -> %6.2f  (%5.2fs)" % ("endcard", t, t + ENDCARD_SECONDS,
                                                ENDCARD_SECONDS))
    total = t + ENDCARD_SECONDS

    vlist = tmp / "v.txt"
    vlist.write_text("".join("file '%s'\n" % p for p in parts))
    alist = tmp / "a.txt"
    alist.write_text("".join("file '%s'\n" % p for p in clips))

    silent = tmp / "silent.mp4"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(vlist), "-c", "copy", str(silent)])
    voice = tmp / "voice.m4a"
    run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", str(alist), "-c:a", "aac", "-b:a", "192k", str(voice)])

    dest = pathlib.Path(out_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print("muxing ...")
    # The narration stops before the end card, so the audio is padded rather
    # than the video truncated to it.
    run([FFMPEG, "-y", "-v", "error", "-i", str(silent), "-i", str(voice),
         "-filter_complex",
         "[0:v]fade=t=in:st=0:d=0.5,fade=t=out:st=%.3f:d=0.6[v];"
         "[1:a]apad,atrim=0:%.4f,afade=t=out:st=%.3f:d=0.6[a]"
         % (total - 0.6, total, total - 0.6),
         "-map", "[v]", "-map", "[a]",
         "-c:v", "libx264", "-preset", "slow", "-crf", "19",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart",
         "-c:a", "aac", "-b:a", "192k", str(dest)])

    print("\nwrote %s" % dest)
    print("  %.2fs, %d MB" % (duration(dest), dest.stat().st_size // (1024 * 1024)))


if __name__ == "__main__":
    main()
