"""Tests for the shared core. Run: python3 test_taste.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from taste.abstain import Verdict, check_input, check_market, check_pair
from taste.evidence import Trace, UnsupportedClaim
from taste.params import ParamGuard
from taste.rank import Ranking

passed = failed = 0


def check(label, cond):
    global passed, failed
    if cond:
        passed += 1
        print("  pass  %s" % label)
    else:
        failed += 1
        print("  FAIL  %s" % label)


print("rank")
a = Ranking("A", {"x": 0.9, "y": 0.5, "z": 0.1})
b = Ranking("B", {"x": 9.0, "y": 5.0, "z": 1.0, "w": 7.0})
check("different set sizes produce zero shift when order agrees",
      all(abs(v) < 1e-9 for v in a.shift_against(b).values()))
check("tau is 1.0 for identical ordering", a.agreement_with(b) == 1.0)
check("entity absent from one market is excluded", "w" not in a.shift_against(b))
try:
    Ranking("empty", {})
    check("empty ranking rejected", False)
except ValueError:
    check("empty ranking rejected", True)

print("params")
g = ParamGuard()
kept, dropped, warns = g.check("urn:entity:artist",
                               {"filter.type": "urn:entity:artist",
                                "filter.release_year.min": 2000})
check("movie-only parameter dropped for artists", "filter.release_year.min" in dropped)
check("valid parameter kept", "filter.type" in kept)
g.record("urn:entity:artist", "filter.tags", honoured=False)
_, _, warns2 = g.check("urn:entity:artist", {"filter.tags": "x"})
check("measured-ignored parameter raises a warning",
      any("IGNORED" in w for w in warns2))

print("abstain")
check("too few resolved inputs abstains",
      check_input(["a"] * 3, ["a"] * 25)[0] == Verdict.ABSTAIN_INPUT)
check("thin market abstains", check_market("Tokyo", 4, 25)[0] == Verdict.ABSTAIN_COVERAGE)
check("thin overlap abstains", check_pair("A", "B", 7)[0] == Verdict.ABSTAIN_OVERLAP)
check("healthy market answers", check_market("Tokyo", 20, 25)[0] == Verdict.ANSWER)

print("evidence")
t = Trace()
cid = t.record_call("/v2/insights", {"filter.type": "urn:entity:movie"}, 200, 20)
t.claim("Parasite ranks higher in Berlin than in New York", [cid])
try:
    t.claim("unsupported assertion", [])
    check("claim without a call is refused", False)
except UnsupportedClaim:
    check("claim without a call is refused", True)
try:
    t.claim("bad reference", ["c99"])
    check("claim citing an unknown call is refused", False)
except UnsupportedClaim:
    check("claim citing an unknown call is refused", True)
t.abstention("abstain_market_coverage", "Mumbai too thin to rank")
check("abstention is recorded, not dropped", t.summary()["abstentions"] == 1)


print("pitch separation flag")
from taste import pitch as _pitch


class _FakeQloo:
    """Returns a chosen affinity spread per signal set, so the flatness
    branches can be driven exactly."""

    def __init__(self, by_signal):
        self.by_signal = by_signal
        self.calls = 0

    def insights(self, params, allow_error=False):
        self.calls += 1
        sig = params["signal.interests.entities"]
        lo, hi = self.by_signal[sig]
        ids = params["filter.results.entities"].split(",")
        n = len(ids)
        step = (hi - lo) / (n - 1) if n > 1 else 0
        return 200, {"results": {"entities": [
            {"entity_id": e, "name": e, "query": {"affinity": lo + i * step}}
            for i, e in enumerate(ids)]}}


SLATE = ["m%d" % i for i in range(12)]
CAT = ["c%d" % i for i in range(8)]
WHOLE = ",".join(CAT)
HALF_A = ",".join(CAT[0::2])
HALF_B = ",".join(CAT[1::2])
CONTIG_A, CONTIG_B = ",".join(CAT[:4]), ",".join(CAT[4:])

# The case that was mislabelled: the re-probe improves the spread, but the
# result is still nowhere near the floor.
fake = _FakeQloo({WHOLE: (0.80, 0.876),        # spread 0.076
                  HALF_A: (0.80, 0.882),       # spread 0.082 -- better, still flat
                  HALF_B: (0.80, 0.850),
                  CONTIG_A: (0.80, 0.860), CONTIG_B: (0.80, 0.855)})
_, _, _, flat, hold = _pitch.profile(fake, SLATE, CAT, "urn:entity:movie")
check("re-probe improves but stays below the floor -> still flagged", flat is True)
check("top-five hold is reported as a count out of five",
      isinstance(hold, int) and 0 <= hold <= 5)

# A genuinely separated reading must not be flagged.
fake2 = _FakeQloo({WHOLE: (0.20, 0.90),        # spread 0.70, above the floor
                   HALF_A: (0.20, 0.90), HALF_B: (0.20, 0.90),
                   CONTIG_A: (0.20, 0.90), CONTIG_B: (0.20, 0.90)})
_, _, _, flat2, _ = _pitch.profile(fake2, SLATE, CAT, "urn:entity:movie")
check("a reading above the floor is not flagged", flat2 is False)

# Too small to split: the flag must still fire on a flat reading rather than
# defaulting to False because no cross-check ran.
SMALL = ["c0", "c1", "c2", "c3"]
fake3 = _FakeQloo({",".join(SMALL): (0.80, 0.86)})
_, _, _, flat3, hold3 = _pitch.profile(fake3, SLATE, SMALL, "urn:entity:movie")
check("flat reading too small to cross-check is still flagged", flat3 is True)
check("no top-five hold is reported when the catalogue cannot be split",
      hold3 is None)


print("llm placements")
_rows = [{"title": "A"}, {"title": "B"}, {"title": "C"}, {"title": "D"},
         {"title": "E"}, {"title": "F"}, {"title": "G"}]
_by_id = {"e1": {"name": "W"}, "e2": {"name": "A"}}
# W was withheld, so it never appears in rows and has no rank.
_pl = _pitch.placements_for(["A", "F", "W", "ZZ"], _rows, ["e1"], _by_id)
_got = {d["title"]: d for d in _pl}
check("a shared top-five pick is marked shared, with no rank claimed",
      _got["A"]["shared"] is True and "grounded_place" not in _got["A"])
check("a pick outside the top five reports its place out of the ranked count",
      _got["F"]["grounded_place"] == 6 and _got["F"]["of_ranked"] == 7)
check("a WITHHELD pick reports withheld instead of a rank",
      _got["W"]["withheld"] is True and _got["W"].get("grounded_place") is None)
check("a pick the grounded reading never scored claims no place",
      _got["ZZ"]["grounded_place"] is None and _got["ZZ"]["withheld"] is False)

print("budget guards")
import importlib
import app.budget as _b
importlib.reload(_b)
_bud = _b.Budget()
_ok = [_bud.allow_pitch("1.2.3.4")[0] and (_bud.record_pitch("1.2.3.4") or True)
       for _ in range(_b.PITCH_PER_IP_PER_HOUR)]
check("a visitor gets exactly the configured number of custom runs",
      all(_ok) and len(_ok) == _b.PITCH_PER_IP_PER_HOUR)
_allowed, _why = _bud.allow_pitch("1.2.3.4")
check("the next one is refused, naming the per-IP cap",
      _allowed is False and _why == "pitch_per_ip_cap")
check("a different visitor is unaffected", _bud.allow_pitch("5.6.7.8")[0] is True)
_bud2 = _b.Budget()
_bud2.quota_remaining = _b.QUOTA_FLOOR - 1
check("below the quota floor live runs stop", _bud2.allow_pitch("9.9.9.9")[1] == "quota_floor")
check("every refusal has a message that mentions the cached examples",
      all("recorded example" in _b.message_for(r)
          for r in ("quota_floor", "pitch_per_ip_cap", "per_ip_hourly_cap")))

print("\n%d passed, %d failed" % (passed, failed))
sys.exit(1 if failed else 0)
