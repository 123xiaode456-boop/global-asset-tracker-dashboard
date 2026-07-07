param(
  [Parameter(Mandatory = $true)]
  [string[]]$Path,

  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"
$py = "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

function Resolve-ImportPath {
  param([string[]]$Items)

  $resolved = @()
  foreach ($item in $Items) {
    if (Test-Path -LiteralPath $item -PathType Leaf) {
      $resolved += (Resolve-Path -LiteralPath $item).Path
      continue
    }

    $matches = @(Get-ChildItem -Path $item -File -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) {
      throw "No import files matched: $item"
    }

    foreach ($match in $matches) {
      $resolved += $match.FullName
    }
  }

  return $resolved
}

Push-Location $ProjectRoot
try {
  $resolvedPath = @(Resolve-ImportPath -Items $Path)
  & $py -m asset_tracker import @resolvedPath --archive-raw
}
finally {
  Pop-Location
}
