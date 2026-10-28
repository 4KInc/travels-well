#!/usr/bin/env python3
"""Rebuild docs/gallery from the live site.

DEV-ONLY. Needs Chrome and macOS sips; neither is imported by the app or in
the container. The runtime stays stdlib-only.

Captures headless at 2x so the images survive Devpost scaling, then crops each
one to the thing it is for. Run it after any wording change: the gallery has
gone stale twice already because the copy moved and the pictures did not.

    python3 make_gallery.py [--base URL]
"""
from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import subprocess
import tempfile
import time

HERE = pathlib.Path(__file__).parent
OUT = HERE / "docs" / "gallery"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# name: (path, window w, window h, crop h, crop y offset, device scale)
SHOTS = {
    "0-hero-full":          ("/",        1400, 1800, None, None, 2),
    "1-hero-side-by-side":  ("/",        1400, 1800, 2050,  960, 2),
    "2-evidence-verdicts":  ("/evidence",1400, 2000, 1900,  540, 2),
    "3-location-matrix":    ("/evidence",1400, 2000, 1500, 2430, 2),
    "5-audience-map":       ("/atlas",   1400, 1700, 1800,  420, 2),
    "6-refusal":            ("/slate?preset=newyork-refused", 1400, 1500, 1500, 380, 2),
    "7-hero-mobile":        ("/",         390, 1500, 2700,  900, 3),
}


def shoot(url, w, h, scale, dest):
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=%d" % scale,
                    "--window-size=%d,%d" % (w, h),
                    "--virtual-time-budget=18000",
                    "--screenshot=%s" % dest, url],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def crop(src, dest, height, offset, width):
    subprocess.run(["/usr/bin/sips", "-c", str(height), str(width),
                    "--cropOffset", str(offset), "0", str(src), "--out", str(dest)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def to_jpeg(src, dest):
    subprocess.run(["/usr/bin/sips", "-s", "format", "jpeg",
                    "-s", "formatOptions", "82", str(src), "--out", str(dest)],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base",
                    default="https://travels-well-722527905604.us-central1.run.app")
    args = ap.parse_args()
    tmp = pathlib.Path(tempfile.mkdtemp())
    OUT.mkdir(parents=True, exist_ok=True)

    for name, (path, w, h, ch, cy, scale) in SHOTS.items():
        raw = tmp / ("%s-raw.png" % name)
        shoot(args.base + path, w, h, scale, raw)
        if not raw.exists():
            print("  %-24s FAILED to capture" % name); continue
        final = raw
        if ch:
            final = tmp / ("%s-crop.png" % name)
            crop(raw, final, ch, cy, w * scale)
        ext = ".png" if name.endswith("mobile") else ".jpg"
        dest = OUT / (name + ext)
        if ext == ".jpg":
            to_jpeg(final, dest)
        else:
            shutil.copy(final, dest)
        os.chmod(dest, 0o644)
        print("  %-24s %6.0f KB" % (dest.name, dest.stat().st_size / 1024))

    # The trace needs <details> open, which headless cannot click. Serve a
    # temporary local copy with the attribute set, and always put it back.
    hero = HERE / "app" / "hero.html"
    backup = hero.read_text()
    try:
        hero.write_text(backup.replace('<details class="trace">',
                                       '<details class="trace" open>'))
        env = dict(os.environ, PORT="8091", QLOO_API_KEY="")
        srv = subprocess.Popen(["python3", "app/server.py"], cwd=str(HERE), env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        raw = tmp / "trace-raw.png"
        shoot("http://127.0.0.1:8091/", 1400, 2400, 2, raw)
        srv.terminate(); srv.wait(timeout=10)
    finally:
        hero.write_text(backup)
    assert '<details class="trace" open>' not in hero.read_text(), "hero.html not restored"
    if raw.exists():
        c = tmp / "trace-crop.png"
        crop(raw, c, 1700, 2850, 2800)
        to_jpeg(c, OUT / "4-agent-trace.jpg")
        os.chmod(OUT / "4-agent-trace.jpg", 0o644)
        print("  %-24s %6.0f KB" % ("4-agent-trace.jpg",
              (OUT / "4-agent-trace.jpg").stat().st_size / 1024))
    print("hero.html restored cleanly")


if __name__ == "__main__":
    main()
