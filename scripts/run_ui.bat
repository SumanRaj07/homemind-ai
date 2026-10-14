@echo off
REM Start the HomeMind AI web UI (expects the backend on 127.0.0.1:8000).
cd /d "%~dp0\.."
streamlit run frontend\app.py --server.address 127.0.0.1 --browser.gatherUsageStats false
