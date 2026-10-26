# Running this during judging

Judging runs to **16 November 2026**. Everything here exists so the demo is
still working on the last day, and so that nothing a visitor does can break it
for the next visitor.

## What costs a Qloo call, and what does not

| Surface | Cost |
|---|---|
| `/` the landing page | **nothing** — a recorded run baked into the image |
| `/atlas` the Audience Map | **nothing** — every signature ships with the page |
| `/slate` the four presets | **nothing** — recorded runs |
| `/pitch` the prefilled example | **nothing** — recognised by fingerprint, served from cache |
| `/pitch` after you edit a box | live, roughly 40 calls |
| `/evidence`, `/about`, `/status` | nothing |

A judge who opens every page and never edits an input spends **zero** calls.
That is the design: the cost is only paid by someone who has already decided to
try their own audience.

## The guards

Three, in `app/budget.py`. None of them returns an error page — each one falls
back to a recorded run and says so.

- **`QUOTA_FLOOR = 1500`.** Below this many calls remaining in the month, live
  queries stop entirely. The monthly limit on this key measures 50,000
  (`x-month-ratelimit-limit`, 26 Oct 2026), so the floor is an absolute
  reserve rather than a fraction.
- **`PITCH_PER_IP_PER_HOUR = 5`.** One visitor cannot drain the month. The cap
  lifts an hour after their first run. Visitors are keyed on the **rightmost**
  `X-Forwarded-For` entry, which is measured behaviour rather than an
  assumption — against the deployed service on 26 Oct 2026:

  | request sent | header as received |
  |---|---|
  | no header | `<real>` |
  | `X-Forwarded-For: 1.2.3.4` | `1.2.3.4, <real>` |
  | `X-Forwarded-For: 1.2.3.4, 5.6.7.8, 9.9.9.9` | `1.2.3.4, 5.6.7.8, 9.9.9.9, <real>` |

  Cloud Run appends and a client cannot displace it, so the last entry is the
  one address in the chain that cannot be forged. Keying on the first — which
  this did until it was measured — let one visitor evade the cap entirely by
  varying the header per request. `/status` echoes `forwarded_chain` and
  `keyed_as` so the behaviour can be re-checked after any infrastructure
  change.
- **`LIVE_CALLS_GLOBAL_PER_HOUR = 200`.** A burst of traffic, or a crawler,
  cannot either.

Each refusal has its own message naming what still works. They are covered by
tests in `test_taste.py` under "budget guards", including that every message
mentions the recorded examples.

## Health

`GET /status` returns the following. **Use `/status`, not `/healthz`**: Google's front end intercepts `/healthz` before it reaches the
container, so from outside it 404s. The deploy check probes `/status`.


```json
{"ok": true, "key_present": true, "quota_remaining": 49700,
 "quota_floor": 1500, "cached_runs": ["hero", "mumbai-out", ...],
 "presets_all_cached": true, "missing_from_cache": [],
 "live_calls": 0, "served_cached": 2}
```

`presets_all_cached: false` is the one to watch — it means a recorded run did
not make it into the image and some page will spend calls it should not.
`quota_remaining` stays `null` until the first live call of a cold instance
reads the header; that is expected, not a fault.

## Deploying

```sh
set -a && . ./.env && set +a
GOOGLE_CLOUD_PROJECT=travels-well-hack MIN_INSTANCES=1 ./deploy.sh
```

`deploy.sh` will refuse to guess: it requires `GOOGLE_CLOUD_PROJECT` and
`QLOO_API_KEY` explicitly, activates the deploy service account, compares the
revision before and after, and exits non-zero if the revision did not change —
three separate deploys once reported success while shipping nothing.

`REGION` defaults to **us-central1**, which is where the service actually runs.
It previously defaulted to asia-south1, which would have stood up a second
service rather than updating the live one.

`MIN_INSTANCES=1` keeps an instance warm so a judge's first request is not a
cold start. It bills continuously; set it back to 0 after 16 November.

## Secrets

- `.deploy-key.json` and `.env` are gitignored and have **never** been
  committed — verified by scanning every commit in history for service-account
  files, PEM blocks, and the Qloo and Gemini key patterns.
- `.gcloudignore` excludes `.env` from the build context, so the key is never
  in the image. It arrives as a Cloud Run environment variable.
- `.gcloudignore` deliberately does **not** exclude `app/cache/`, which is how
  recorded runs reach the image while staying out of the public repository.
  Raw Qloo responses are not committed: the data-publishing rule for this
  hackathon is unresolved, and this is the conservative reading of it.

**After the final deploy**, revoke the deploy service-account key:

```sh
gcloud iam service-accounts keys list \
  --iam-account=travels-well-deploy@travels-well-hack.iam.gserviceaccount.com
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=travels-well-deploy@travels-well-hack.iam.gserviceaccount.com
rm .deploy-key.json
```

This is a human step on purpose and is listed in `docs/HUMAN_TODO.md`. Nothing
in this repository revokes it automatically.

## After 16 November

1. Revoke the deploy key as above.
2. Remove the `travels-well-deploy` service account.
3. Redeploy with `MIN_INSTANCES=0`, or delete the service.
