#!/usr/bin/env bash
set -eu
git clone --quiet --depth 1 "${AUTOSHIFT_REPO:-https://github.com/auto-shift/autoshiftv2.git}" autoshiftv2
