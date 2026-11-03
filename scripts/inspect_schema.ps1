param(
    [string]$Config = "configs/local.yaml",
    [string]$Dataset = ""
)
$ErrorActionPreference = "Stop"

if (Test-Path .\.venv\Scripts\ids-reliability.exe) {
    if ([string]::IsNullOrWhiteSpace($Dataset)) {
        & .\.venv\Scripts\ids-reliability.exe --config $Config inspect-schema
    } else {
        & .\.venv\Scripts\ids-reliability.exe --config $Config inspect-schema --dataset $Dataset
    }
} else {
    if ([string]::IsNullOrWhiteSpace($Dataset)) {
        python -m ids_reliability --config $Config inspect-schema
    } else {
        python -m ids_reliability --config $Config inspect-schema --dataset $Dataset
    }
}
