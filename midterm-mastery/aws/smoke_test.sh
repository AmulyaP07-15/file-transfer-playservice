#!/usr/bin/env bash
# Quick check that the deployed service works before I bother with the load test.
# Three things through the ALB.
#   1. health comes back 200
#   2. hello.txt downloads and has the text I expect
#   3. 1mb.bin downloads and matches my local copy exactly (sha256)
# It reads the ALB address from terraform output unless I pass it as argument 1.
#
# usage
#   aws/smoke_test.sh [ALB_DNS_or_URL]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MM="$(dirname "$HERE")"
ROOT="$(dirname "$MM")"
FILES="$MM/testfiles"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# ALB address, use the argument if given, otherwise ask terraform
if [ "$#" -ge 1 ]; then
	HOST="$1"
else
	HOST="$(terraform -chdir="$ROOT/terraform" output -raw alb_dns_name 2>/dev/null)"
	[ -n "$HOST" ] || { echo "Could not read alb_dns_name from terraform, pass the ALB dns as an argument" >&2; exit 1; }
fi
case "$HOST" in http://*|https://*) ;; *) HOST="http://$HOST" ;; esac

pass=0
fail=0
check() {
	if [ "$1" = 0 ]; then
		echo "  ok  $2"
		pass=$((pass + 1))
	else
		echo "  no  $2"
		fail=$((fail + 1))
	fi
}

echo "Smoke test against $HOST"

# 1. health
code="$(curl -s -o /dev/null -w '%{http_code}' "$HOST/health" || true)"
[ "$code" = 200 ]
check $? "GET health gave $code"

# 2. hello.txt, just check the text is in there
curl -s -o "$TMP/hello.txt" "$HOST/files?name=hello.txt" || true
if grep -q "hello there" "$TMP/hello.txt" 2>/dev/null; then
	check 0 "hello.txt content"
else
	check 1 "hello.txt content"
fi

# 3. 1mb.bin, compare hashes so I know the bytes are exactly right not just a 200
curl -s -o "$TMP/1mb.bin" "$HOST/files?name=1mb.bin" || true
if [ -f "$FILES/1mb.bin" ]; then
	a="$(shasum -a 256 "$FILES/1mb.bin" | awk '{print $1}')"
	b="$(shasum -a 256 "$TMP/1mb.bin" 2>/dev/null | awk '{print $1}')"
	if [ -n "$b" ] && [ "$a" = "$b" ]; then
		check 0 "1mb.bin matches exactly"
	else
		check 1 "1mb.bin does not match, local $a got ${b:-none}"
	fi
else
	check 1 "1mb.bin original missing, run make_test_files.sh"
fi

echo
if [ "$fail" = 0 ]; then
	echo "All smoke tests passed"
else
	echo "$fail checks failed, $pass passed"
	exit 1
fi
