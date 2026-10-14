# Build the HomeMind AI Windows desktop distribution.
# Run on Windows 11 in PowerShell, from the repository root.
#
# This script has NOT been executed in the Linux dev environment.
# Do not distribute the exe until the smoke test below passes on Windows.
$ErrorActionPreference = "Stop"

Write-Host "=== 1. Virtual environment ==="
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller

Write-Host "=== 2. Tests (mocked model, no Ollama needed) ==="
$env:HOMEMIND_PROVIDER = "mock"
pytest -q
if ($LASTEXITCODE -ne 0) { throw "tests failed" }

Write-Host "=== 3. Build desktop exe ==="
pyinstaller desktop/homemind.spec
if ($LASTEXITCODE -ne 0) { throw "pyinstaller failed" }

Write-Host "=== 4. Smoke test (do this manually) ==="
Write-Host "  a. Run dist\HomeMindAI.exe"
Write-Host "  b. Create a conversation and send a chat message (needs Ollama + model)"
Write-Host "  c. Stop Ollama -> the UI must show a clear error, no cloud fallback"
Write-Host "  d. Close the app -> confirm no python/HomeMindAI process remains (Task Manager)"
Write-Host "  e. Reopen -> previous conversations must still be there (data preserved)"
Write-Host ""
Write-Host "Build finished: dist\HomeMindAI.exe"
