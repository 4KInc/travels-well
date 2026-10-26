"""The clone-and-run path: no key, no recorded runs.

Someone checking this out from GitHub has neither a Qloo key nor the recorded
runs, because raw Qloo responses are not committed. That is the most common
first experience of this repository, so it is the one with a test. The server
must start, every page must answer, and the pages must say which command
builds the recordings -- not leak a stack trace or a TypeError.

Run: python3 test_startup.py
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
passed = failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print("  pass  %s" % label)
    else:
        failed += 1
        print("  FAIL  %s" % label)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def main():
    cache = HERE / "app" / "cache"
    stash = Path(tempfile.mkdtemp()) / "cache"
    moved = cache.exists()
    if moved:
        shutil.move(str(cache), str(stash))

    port = free_port()
    env = dict(os.environ, PORT=str(port), QLOO_API_KEY="")
    proc = subprocess.Popen([sys.executable, "app/server.py"], cwd=str(HERE),
                            env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    try:
        base = "http://127.0.0.1:%d" % port
        for _ in range(60):
            try:
                get(base + "/healthz")
                break
            except Exception:
                time.sleep(0.25)

        print("fresh checkout: no key, no recorded runs")
        check("the server starts at all", proc.poll() is None)

        for path in ("/", "/pitch", "/atlas", "/slate", "/evidence", "/about"):
            status, _ = get(base + path)
            check("%s still answers" % path, status == 200)

        status, body = get(base + "/healthz")
        health = json.loads(body)
        check("health reports the server is up", status == 200 and health["ok"])
        check("health admits the key is absent", health["key_present"] is False)
        check("health admits the recordings are missing",
              health["presets_all_cached"] is False and health["missing_from_cache"])

        status, body = get(base + "/api/hero")
        check("the hero API refuses with an explanation, not a traceback",
              status == 503 and "missing" in json.loads(body).get("error", "")
              and "Traceback" not in body)

        _, page = get(base + "/")
        check("the landing page names the command that builds the recordings",
              "warm_cache.py" in page and "hero_build.py" in page)
        check("and says why they are not in the repository",
              "data-publishing" in page or "not committed" in page)

        out = proc.stdout
        proc.terminate()
        proc.wait(timeout=10)
        log = out.read().decode(errors="replace")
        check("nothing raised on the way through",
              "Traceback" not in log)
    finally:
        if proc.poll() is None:
            proc.kill()
        if moved:
            if cache.exists():
                shutil.rmtree(cache)
            shutil.move(str(stash), str(cache))

    print("\n%d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
