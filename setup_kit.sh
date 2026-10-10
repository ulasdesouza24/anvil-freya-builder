#!/bin/sh
# Copies the public files of the hackathon kit into kit/, so that the builder works only inside its own folder.
# It never copies a brief, an output or a trace of another builder.
#   sh setup_kit.sh [path of the unzipped kit]   (default: ~/Desktop/freya-kit/build-the-builder)
set -e
SRC="${1:-$HOME/Desktop/freya-kit/build-the-builder}"
DST="$(cd "$(dirname "$0")" && pwd)/kit"
rm -rf "$DST"
mkdir -p "$DST/docs" "$DST/tools" "$DST/examples"
cp "$SRC/README.md" "$SRC/VERSION" "$SRC/freya.py" "$SRC/public-test-set.json" "$DST/"
cp "$SRC"/docs/*.md "$DST/docs/"
cp "$SRC/tools/run_cases.py" "$SRC/tools/score.py" "$DST/tools/"
cp "$SRC/examples/base-agent.json" "$DST/examples/"
echo "kit $(cat "$DST/VERSION") copied to $DST"
