"""Quota and abuse guards.

Two different risks. The monthly Qloo quota is shared across everything, and
judging runs to 16 November, so a demo that burns the quota in week one is
dead when it matters most. And a public URL with no login will be hit by
crawlers.

Neither guard is allowed to break the demo: when a limit is reached the app
serves the cached preset and says so, rather than showing an error.
"""
from __future__ import annotations

import threading
import time

# Raised once a run cost 10 Qloo calls instead of 65. The quota floor below is
# the real protection: when the month runs low every answer serves from a
# recorded run, so the demo degrades rather than dying.
LIVE_CALLS_PER_IP_PER_HOUR = 20
LIVE_CALLS_GLOBAL_PER_HOUR = 200
# Measured 26 Oct 2026: the hackathon key's monthly limit is 50,000, not the
# 10,000 assumed when this floor was chosen. 1,500 is kept anyway -- it is an
# absolute reserve for the cached presets, not a fraction of the month.
QUOTA_FLOOR = 1500         # stop live calls entirely below this many remaining
PITCH_PER_IP_PER_HOUR = 5  # a custom pitch costs ~40 calls; the URL is public


def client_key(forwarded_for, socket_addr):
    """Which visitor a request counts against.

    On Cloud Run the Google frontend sets X-Forwarded-For as
    "<client>, <proxy>...", so the first entry is the client. The socket
    address is only ever the frontend, which would put every visitor in one
    bucket, so it is a local-development fallback and nothing else.

    A client can send its own X-Forwarded-For and Cloud Run appends to it,
    which means this first entry is not trustworthy against someone who wants
    to evade the per-IP cap. That is accepted deliberately: the per-IP cap is
    there to stop one honest visitor draining the month by accident, and
    LIVE_CALLS_GLOBAL_PER_HOUR is the backstop that a forged header cannot get
    past. The expensive failure is a drained quota, and the global cap bounds
    it regardless.
    """
    first = (forwarded_for or "").split(",")[0].strip()
    return first or socket_addr or "unknown"


class Budget:
    def __init__(self):
        self._lock = threading.Lock()
        self._per_ip = {}
        self._pitch_per_ip = {}
        self._global = []
        self.quota_remaining = None
        self.live_calls = 0
        self.served_cached = 0

    def _prune(self, stamps, now):
        return [t for t in stamps if now - t < 3600]

    def allow_pitch(self, ip):
        """A pitch is six times the cost of a preset, and the demo URL sits in
        a public repository. Judging runs to 16 November, so one visitor must
        not be able to drain the month."""
        now = time.time()
        with self._lock:
            if self.quota_remaining is not None and self.quota_remaining < QUOTA_FLOOR:
                return False, "quota_floor"
            mine = self._prune(self._pitch_per_ip.get(ip, []), now)
            self._pitch_per_ip[ip] = mine
            if len(mine) >= PITCH_PER_IP_PER_HOUR:
                return False, "pitch_per_ip_cap"
        return self.allow_live(ip)

    def record_pitch(self, ip, quota_remaining=None):
        with self._lock:
            self._pitch_per_ip.setdefault(ip, []).append(time.time())
        self.record_live(ip, quota_remaining)

    def allow_live(self, ip):
        """Returns (allowed, reason). A refusal is a routing decision, not an
        error: the caller falls back to cache."""
        now = time.time()
        with self._lock:
            if self.quota_remaining is not None and self.quota_remaining < QUOTA_FLOOR:
                return False, "quota_floor"
            self._global = self._prune(self._global, now)
            if len(self._global) >= LIVE_CALLS_GLOBAL_PER_HOUR:
                return False, "global_hourly_cap"
            mine = self._prune(self._per_ip.get(ip, []), now)
            self._per_ip[ip] = mine
            if len(mine) >= LIVE_CALLS_PER_IP_PER_HOUR:
                return False, "per_ip_hourly_cap"
            return True, None

    def record_live(self, ip, quota_remaining=None):
        now = time.time()
        with self._lock:
            self._per_ip.setdefault(ip, []).append(now)
            self._global.append(now)
            self.live_calls += 1
            if quota_remaining is not None:
                self.quota_remaining = quota_remaining

    def record_cached(self):
        with self._lock:
            self.served_cached += 1

    def snapshot(self):
        with self._lock:
            return {"quota_remaining": self.quota_remaining,
                    "quota_floor": QUOTA_FLOOR,
                    "live_calls": self.live_calls,
                    "served_cached": self.served_cached}


# A refusal is shown to a visitor, so it says what they can still do rather
# than naming the counter that stopped them. Judging runs to 16 November and
# every one of these paths leaves the recorded examples working.
MESSAGES = {
    "quota_floor":
        "Live queries are paused to protect the demo for the rest of judging. "
        "Every recorded example still works and costs nothing \u2014 the landing "
        "page, the Audience Map and all four Slate presets are unaffected.",
    "pitch_per_ip_cap":
        "You have run %d custom rankings in the last hour, which is the cap on "
        "a shared hackathon key. It lifts an hour after your first run. The "
        "recorded examples work in the meantime."
        % PITCH_PER_IP_PER_HOUR,
    "per_ip_hourly_cap":
        "You have made a lot of live queries in the last hour. The cap lifts "
        "an hour after the first one; the recorded examples still work.",
    "global_hourly_cap":
        "The demo is busy: live queries across all visitors have hit the "
        "hourly cap. It clears within the hour, and every recorded example "
        "works now.",
}


def message_for(reason):
    return MESSAGES.get(reason, MESSAGES["global_hourly_cap"])
