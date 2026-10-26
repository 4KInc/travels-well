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


# How many trailing X-Forwarded-For entries were appended by infrastructure we
# control. On Cloud Run this is exactly one: Google's front end appends the
# real peer address to whatever the client sent. Measured 26 Oct 2026 against
# the deployed service:
#
#   sent nothing                 -> ["<real>"]
#   sent "1.2.3.4"               -> ["1.2.3.4", "<real>"]
#   sent "1.2.3.4, 5.6.7.8, ..." -> ["1.2.3.4", "5.6.7.8", "...", "<real>"]
#
# The appended entry is always last and a client cannot displace it, so the
# rightmost entry is the one address in the chain that cannot be forged.
TRUSTED_APPENDED_HOPS = 1


def client_key(forwarded_for, socket_addr, trusted_hops=TRUSTED_APPENDED_HOPS):
    """Which visitor a request counts against.

    Read from the RIGHT, not the left. The leftmost entry is whatever the
    client claimed, so keying on it lets anyone evade the per-IP cap by
    sending a different X-Forwarded-For on each request. The rightmost is the
    address Cloud Run observed and appended itself.

    Behind a different number of trusted proxies, pass `trusted_hops`. With no
    header at all -- local development, where nothing is in front of the
    server -- the socket address is the client.
    """
    chain = [x.strip() for x in (forwarded_for or "").split(",") if x.strip()]
    if not chain:
        return socket_addr or "unknown"
    hops = max(1, int(trusted_hops))
    # Shorter chain than expected: take the leftmost rather than inventing one.
    return chain[-hops] if len(chain) >= hops else chain[0]


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
