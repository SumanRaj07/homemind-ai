#!/usr/bin/env bash
# Start the HomeMind AI web UI (expects the backend on 127.0.0.1:8000).
set -euo pipefail
cd "$(dirname "$0")/.."
exec streamlit run frontend/app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
