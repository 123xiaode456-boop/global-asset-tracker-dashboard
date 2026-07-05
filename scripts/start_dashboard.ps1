param(
  [int]$Port = 8507,
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$env:STREAMLIT_BROWSER_GATHER_USAGE_STATS = "false"
$venvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path -LiteralPath $venvPy) {
  $py = $venvPy
}
else {
  $py = "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}

Push-Location $ProjectRoot
try {
  & $py -m streamlit run streamlit_app.py --server.port $Port --server.headless true --browser.gatherUsageStats false
}
finally {
  Pop-Location
}
