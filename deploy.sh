#!/usr/bin/env bash
# Deploy the public demo to Cloud Run.
#
# Two safeguards learned the hard way on a previous project:
#   * the target project is stated explicitly and never inherited from the
#     gcloud default, because building into the wrong project is silent;
#   * --set-env-vars REPLACES rather than merges, so every variable the live
#     service needs is listed here in one place.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT explicitly, do not rely on the gcloud default}"
REGION="${REGION:-us-central1}"   # where travels-well actually runs; asia-south1 would fork a second service
SERVICE="${SERVICE:-travels-well}"
: "${QLOO_API_KEY:?QLOO_API_KEY must be set in the deploying shell}"

# A user session expires every few hours and did so three times during
# development, each time printing success-shaped output while shipping
# nothing. With the key present, deploys stop depending on anyone being
# logged in -- which matters because judging runs 2-16 November.
KEY="$(dirname "$0")/.deploy-key.json"
PREV_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
restore_account() {
  # Leave the shell as we found it: activating a service account switches the
  # active gcloud account for everything that follows, which is a trap.
  if [ -n "${PREV_ACCOUNT:-}" ] && [ "$PREV_ACCOUNT" != "(unset)" ]; then
    gcloud config set account "$PREV_ACCOUNT" --quiet >/dev/null 2>&1 || true
  fi
}
if [ -f "$KEY" ]; then
  echo "using the deploy service account"
  gcloud auth activate-service-account --key-file="$KEY" --quiet >/dev/null
  trap restore_account EXIT
fi

DEFAULT_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
if [ "$DEFAULT_PROJECT" != "$GOOGLE_CLOUD_PROJECT" ]; then
  echo "note: gcloud default is '$DEFAULT_PROJECT', deploying to '$GOOGLE_CLOUD_PROJECT'"
fi

echo "deploying $SERVICE to $GOOGLE_CLOUD_PROJECT / $REGION"
# Verify afterwards that the revision actually changed: a failed deploy can
# still print reassuring output.
BEFORE="$(gcloud run services describe "$SERVICE" --project "$GOOGLE_CLOUD_PROJECT" \
          --region "$REGION" --format='value(status.latestReadyRevisionName)' 2>/dev/null || echo none)"
gcloud run deploy "$SERVICE" \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region "$REGION" \
  --source . \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --concurrency 40 \
  --max-instances 3 \
  --min-instances "${MIN_INSTANCES:-1}" \
  --timeout 120 \
  --set-env-vars "QLOO_API_KEY=${QLOO_API_KEY},QLOO_BASE=${QLOO_BASE:-https://hackathon.api.qloo.com}"

# Take the URL from the service itself. Deriving it from the project number
# needed `gcloud projects describe`, which calls an API the deploy service
# account cannot reach -- so every deploy succeeded and then reported failure.
URL="$(gcloud run services describe "$SERVICE" --project "$GOOGLE_CLOUD_PROJECT" \
       --region "$REGION" --format='value(status.url)')"
echo
AFTER="$(gcloud run services describe "$SERVICE" --project "$GOOGLE_CLOUD_PROJECT" \
         --region "$REGION" --format='value(status.latestReadyRevisionName)' 2>/dev/null || echo none)"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "WARNING: revision did not change ($AFTER). Nothing was deployed."
  exit 1
fi
echo "revision $BEFORE -> $AFTER"
echo "live at: $URL"
echo "checking it answers cold..."
curl -fsS "$URL/status" && echo
curl -fsS "$URL/api/run?preset=mumbai-out" >/dev/null && echo "preset path OK"

# Every page a judge can reach must answer, and the landing page must answer
# quickly: it is the first thing seen and MIN_INSTANCES=1 exists to keep it
# warm. A 404 here means a nav link ships broken.
FAILED=0
for path in / /pitch /atlas /slate /evidence /about /healthz; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$URL$path")"
  printf '  %-12s %s\n' "$path" "$code"
  [ "$code" = "200" ] || FAILED=1
done
LOAD="$(curl -s -o /dev/null -w '%{time_total}' "$URL/")"
echo "  landing page cold load: ${LOAD}s"
awk -v t="$LOAD" 'BEGIN{ if (t+0 > 3.0) { print "  !! slower than 3s"; exit 1 } }' || FAILED=1

# The whole point of the recorded runs: a judge who only reads costs nothing.
CACHED_OK="$(curl -fsS "$URL/healthz" | tr -d ' ' | grep -c '"presets_all_cached":true' || true)"
if [ "$CACHED_OK" != "1" ]; then
  echo "  !! a recorded run is missing from the image; pages will spend quota"
  FAILED=1
else
  echo "  all recorded runs present in the image"
fi

if [ "$FAILED" != "0" ]; then
  echo "DEPLOY VERIFICATION FAILED"
  exit 1
fi
echo "all routes OK"
