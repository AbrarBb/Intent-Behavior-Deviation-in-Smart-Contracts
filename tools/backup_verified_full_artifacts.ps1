# Backup canonical verified-full artifacts (default Stage 2 stem).
# Usage:
#   .\tools\backup_verified_full_artifacts.ps1
#   .\tools\backup_verified_full_artifacts.ps1 -Destination "artifacts\stage2_slither_only_backup"

param(
    [string]$Destination = "artifacts\stage2_slither_only_backup"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

$files = @(
    "artifacts\ml_dataset_verified_full.npz",
    "artifacts\ml_dataset_verified_full_meta.csv",
    "artifacts\ml_dataset_verified_full.csv",
    "artifacts\ml_dataset_verified_full_config.json"
)

$missing = @()
foreach ($f in $files) {
    if (-not (Test-Path -LiteralPath $f)) { $missing += $f }
}
if ($missing.Count -gt 0) {
    Write-Warning "Some files are missing (backup may be partial):"
    $missing | ForEach-Object { Write-Warning "  $_" }
}

New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($f in $files) {
    if (Test-Path -LiteralPath $f) {
        Copy-Item -LiteralPath $f -Destination $Destination -Force
    }
}

Write-Host "Backed up to: $((Resolve-Path $Destination).Path)"
