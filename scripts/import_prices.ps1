param(
  [Parameter(Mandatory=$true)]
  [string]$Asset,

  [Parameter(Mandatory=$true)]
  [string]$Csv,

  [string]$Source = "manual_csv",
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$py = "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$db = Join-Path $ProjectRoot "data\processed\signals.sqlite"
$argsList = @("-m", "asset_tracker", "import-prices", $Asset, $Csv, "--source", $Source, "--db", $db)

Push-Location $ProjectRoot
try {
  & $py @argsList
}
finally {
  Pop-Location
}
