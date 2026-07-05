param(
  [Parameter(Mandatory = $true)]
  [string]$Asset,

  [Parameter(Mandatory = $true)]
  [string]$Symbol,

  [string]$Source = "yfinance",
  [string]$Note = "",
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$py = "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

Push-Location $ProjectRoot
try {
  & $py -m asset_tracker map-symbol $Asset $Symbol --source $Source --note $Note
}
finally {
  Pop-Location
}
