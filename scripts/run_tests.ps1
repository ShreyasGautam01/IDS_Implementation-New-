$ErrorActionPreference = "Stop"

if (Test-Path .\.venv\Scripts\python.exe) {
    & .\.venv\Scripts\python.exe -m pytest -q
} else {
    python -m pytest -q
}
