param(
  [string]$Asset,
  [string]$DatasetType,
  [string]$AssetKind,
  [string]$Start,
  [string]$End,
  [int]$Limit,
  [switch]$ForceRefresh,
  [switch]$MissingOnly,
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$py = "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

$argsList = @("-m", "asset_tracker", "fetch-prices")
if ($Asset) { $argsList += @("--asset", $Asset) }
if ($DatasetType) { $argsList += @("--dataset-type", $DatasetType) }
if ($AssetKind) { $argsList += @("--asset-kind", $AssetKind) }
if ($Start) { $argsList += @("--start", $Start) }
if ($End) { $argsList += @("--end", $End) }
if ($Limit) { $argsList += @("--limit", "$Limit") }
if ($ForceRefresh) { $argsList += @("--force-refresh") }
if ($MissingOnly) { $argsList += @("--missing-only") }

Push-Location $ProjectRoot
try {
  & $py @argsList
}
finally {
  Pop-Location
}
