#!/usr/bin/env bash
# Makes the files the experiments download, into midterm-mastery/testfiles.
# The protocol tops out around 4 MB (64 byte chunks, at most 65,536 chunks,
# which is 4,194,304 bytes), so I keep the big file at 4,000,000 bytes to stay
# safely under that limit instead of right on it.
#
# usage
#   scripts/make_test_files.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MM="$(dirname "$HERE")"
OUT="$MM/testfiles"
mkdir -p "$OUT"

# tiny text file I can read with my own eyes to confirm things work
echo "hello there" >"$OUT/hello.txt"

# random bytes for the binary ones, random so nothing gets compressed on the way
make_bin() {
	head -c "$2" /dev/urandom >"$OUT/$1"
	echo "  $1 ($2 bytes)"
}

echo "Writing test files to $OUT"
make_bin 10kb.bin 10240
make_bin 100kb.bin 102400
make_bin 1mb.bin 1048576
make_bin 4mb.bin 4000000

# print the hashes so I have a record of what the originals were
echo "Done, sha256"
if command -v shasum >/dev/null 2>&1; then
	( cd "$OUT" && shasum -a 256 hello.txt 10kb.bin 100kb.bin 1mb.bin 4mb.bin )
fi
