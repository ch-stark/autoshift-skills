#!/usr/bin/env bash
# Copy each shared/ reference into every skill that carries it. Skills must be self-contained,
# so the copies are committed; tests/validate.py fails when one drifts.
set -euo pipefail
cd "$(dirname "$0")/.."
for src in shared/*.md; do
  for dst in skills/*/references/"$(basename "$src")"; do
    [ -e "$dst" ] && cp "$src" "$dst"
  done
done
