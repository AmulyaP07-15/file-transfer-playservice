#!/usr/bin/env bash
# Copies midterm-mastery/testfiles up to the S3 bucket under the tmp prefix, so
# the AWS backend can serve them. On AWS the backend reads files from S3 under
# tmp, not from local disk. It reads the bucket name from
# terraform/terraform.tfvars unless I pass one as the first argument.
#
# usage
#   aws/upload_test_files.sh [BUCKET]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MM="$(dirname "$HERE")"
ROOT="$(dirname "$MM")"
FILES="$MM/testfiles"
TFVARS="$ROOT/terraform/terraform.tfvars"
PREFIX="tmp/"
REGION="${REGION:-us-west-2}"

# bucket name, use the argument if given, otherwise read files_bucket from tfvars
if [ "$#" -ge 1 ]; then
	BUCKET="$1"
else
	[ -f "$TFVARS" ] || { echo "No $TFVARS and no bucket argument" >&2; exit 1; }
	BUCKET="$(grep -E '^[[:space:]]*files_bucket' "$TFVARS" | head -1 | sed -E 's/.*=[[:space:]]*"?([^"[:space:]]+)"?.*/\1/')"
	[ -n "$BUCKET" ] || { echo "Could not read files_bucket from $TFVARS" >&2; exit 1; }
fi

[ -d "$FILES" ] || { echo "No $FILES, run scripts/make_test_files.sh first" >&2; exit 1; }

echo "Uploading $FILES to s3://$BUCKET/$PREFIX in region $REGION"
for f in hello.txt 10kb.bin 100kb.bin 1mb.bin 4mb.bin; do
	[ -f "$FILES/$f" ] || { echo "missing $FILES/$f" >&2; exit 1; }
	aws s3 cp "$FILES/$f" "s3://$BUCKET/$PREFIX$f" --region "$REGION"
done

# list what is in the bucket now as a quick confirmation
echo "Now in the bucket"
aws s3 ls "s3://$BUCKET/$PREFIX" --region "$REGION"
