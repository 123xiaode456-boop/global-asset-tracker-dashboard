param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$py = "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
$db = Join-Path $ProjectRoot "data\processed\signals.sqlite"

Push-Location $ProjectRoot
try {
  & $py -m asset_tracker refresh-names --db $db
}
finally {
  Pop-Location
}
