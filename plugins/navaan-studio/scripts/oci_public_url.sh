#!/usr/bin/env bash
# usage: oci_public_url.sh <local file> [object name] [hours]
# Uploads a file to your OCI bucket and prints a temporary pre-authenticated https URL (default 4 hours).
# Needed because the Instagram API fetches the video from a public URL. Requires the oci CLI and a configured profile.
# Env: NAVAAN_BUCKET (default navaan). Delete the object and the pre-authenticated request after publishing.
set -euo pipefail
F="${1:?usage: oci_public_url.sh <file> [object name] [hours]}"
OBJ="${2:-tmp/$(basename "$F")}"
HOURS="${3:-4}"
BUCKET="${NAVAAN_BUCKET:-navaan}"
NS="$(oci os ns get --query data --raw-output)"
oci os object put -ns "$NS" -bn "$BUCKET" --file "$F" --name "$OBJ" --force >/dev/null
EXP="$(python3 -c "import datetime;print((datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=$HOURS)).strftime('%Y-%m-%dT%H:%M:%SZ'))")"
REG="$(oci os ns get-metadata -ns "$NS" --query 'data."default-s3-compartment-id"' --raw-output >/dev/null 2>&1; oci iam region-subscription list --query 'data[?"is-home-region"]|[0]."region-name"' --raw-output)"
ACC="$(oci os preauth-request create -ns "$NS" -bn "$BUCKET" --name "navaan-$(date +%s)" --access-type ObjectRead --object-name "$OBJ" --time-expires "$EXP" --query 'data."access-uri"' --raw-output)"
echo "https://objectstorage.${REG}.oraclecloud.com${ACC}"
