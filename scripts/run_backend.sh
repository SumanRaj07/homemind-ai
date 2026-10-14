#!/usr/bin/env bash
# Start the HomeMind AI backend (loopback only).
set -euo pipefail
cd "$(dirname "$0")/.."
exec python -m homemind.api.app
