$ErrorActionPreference = "Stop"

py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
& .\.venv\Scripts\python.exe -m pip install -e .

Write-Host "Environment ready. Copy configs/default.yaml to configs/local.yaml and set the dataset path/columns."
