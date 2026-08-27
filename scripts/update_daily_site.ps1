param(
  [Parameter(Mandatory = $true)]
  [string[]]$Path,

  [switch]$Publish,

  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

function Resolve-InputFile {
  param([string[]]$Items)

  $resolved = @()
  foreach ($item in $Items) {
    if (Test-Path -LiteralPath $item -PathType Leaf) {
      $resolved += (Resolve-Path -LiteralPath $item).Path
      continue
    }

    $matches = @(Get-ChildItem -Path $item -File -ErrorAction SilentlyContinue)
    if ($matches.Count -eq 0) {
      throw "No input files matched: $item"
    }

    foreach ($match in $matches) {
      $resolved += $match.FullName
    }
  }

  return $resolved
}

function Get-DatasetDate {
  param([string]$FileName)

  if ($FileName -notmatch "(?<yy>\d{2})-(?<mm>\d{2})-(?<dd>\d{2})") {
    throw "Cannot detect dataset date from filename: $FileName"
  }

  return "20$($Matches.yy)-$($Matches.mm)-$($Matches.dd)"
}

function Get-Python {
  param([string]$Root)

  $venvPython = Join-Path $Root ".venv\Scripts\python.exe"
  if (Test-Path -LiteralPath $venvPython) {
    return $venvPython
  }

  return "C:\Users\janzh\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}

$py = Get-Python -Root $ProjectRoot
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

Push-Location $ProjectRoot
try {
  $inputFiles = @(Resolve-InputFile -Items $Path)
  $inboxFiles = @()
  $datasetDates = @()

  foreach ($file in $inputFiles) {
    $fileName = [System.IO.Path]::GetFileName($file)
    $datasetDate = Get-DatasetDate -FileName $fileName
    $datasetDates += $datasetDate
    $inboxDir = Join-Path $ProjectRoot (Join-Path "data\inbox" $datasetDate)
    New-Item -ItemType Directory -Force -Path $inboxDir | Out-Null
    $destination = Join-Path $inboxDir $fileName

    $sourceFull = (Resolve-Path -LiteralPath $file).Path
    $destFull = $null
    if (Test-Path -LiteralPath $destination -PathType Leaf) {
      $destFull = (Resolve-Path -LiteralPath $destination).Path
    }

    if ($sourceFull -ne $destFull) {
      Copy-Item -LiteralPath $sourceFull -Destination $destination -Force
    }

    $inboxFiles += (Resolve-Path -LiteralPath $destination).Path
    Write-Host "inbox: $destination"
  }

  & (Join-Path $ProjectRoot "scripts\import_daily.ps1") -Path $inboxFiles -ProjectRoot $ProjectRoot
  if ($LASTEXITCODE -ne 0) {
    throw "Import failed with exit code $LASTEXITCODE"
  }

  $latestDatasetDate = @($datasetDates | Sort-Object | Select-Object -Last 1)[0]
  $priceStartDate = ([datetime]::ParseExact($latestDatasetDate, "yyyy-MM-dd", $null)).AddDays(-400).ToString("yyyy-MM-dd")
  $db = Join-Path $ProjectRoot "data\processed\signals.sqlite"
  $fetchArgs = @(
    "-m", "asset_tracker",
    "fetch-prices",
    "--db", $db,
    "--dataset-type", "core",
    "--asset-kind", "domestic-futures",
    "--missing-only",
    "--start", $priceStartDate
  )
  & $py @fetchArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Price fetch failed with exit code $LASTEXITCODE"
  }

  $domesticMainFetchArgs = @(
    "-m", "asset_tracker",
    "fetch-prices",
    "--db", $db,
    "--dataset-type", "domestic_main",
    "--asset-kind", "domestic-futures",
    "--missing-only",
    "--start", $priceStartDate
  )
  & $py @domesticMainFetchArgs
  if ($LASTEXITCODE -ne 0) {
    throw "Domestic main price fetch failed with exit code $LASTEXITCODE"
  }

  & $py (Join-Path $ProjectRoot "src\export_static_site.py") --site-dir (Join-Path $ProjectRoot "site-v2") --commodity-only
  if ($LASTEXITCODE -ne 0) {
    throw "Static export failed with exit code $LASTEXITCODE"
  }

  @"
import json
from pathlib import Path
data_dir = Path("site-v2/data")
manifest_path = data_dir / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
date = manifest["datesByType"]["core"][-1]
snapshot_path = data_dir / manifest["files"]["snapshots"][f"core|{date}"]
snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
rows = len(snapshot["latestRows"])
betting_dates = manifest["datesByType"].get("betting", [])
betting_date = betting_dates[-1] if betting_dates else None
betting_path = data_dir / manifest["files"]["snapshots"][f"betting|{betting_date}"] if betting_date else None
betting_rows = len(json.loads(betting_path.read_text(encoding="utf-8"))["latestRows"]) if betting_path else 0
initial_bytes = manifest_path.stat().st_size + snapshot_path.stat().st_size
futures_path = data_dir / manifest["files"]["futuresByDate"].get(date, "")
if futures_path.is_file():
    initial_bytes += futures_path.stat().st_size
print(
    f"verified: core_date={date} core_rows={rows} "
    f"betting_date={betting_date or '-'} betting_rows={betting_rows} initial_bytes={initial_bytes}"
)
"@ | & $py -
  if ($LASTEXITCODE -ne 0) {
    throw "Static data verification failed with exit code $LASTEXITCODE"
  }

  if ($Publish) {
    & $py (Join-Path $ProjectRoot "scripts\publish_site_data_main.py") --branch main --message "Update v2 lazy-loaded site" --directory "site-v2=site-v2"
    if ($LASTEXITCODE -ne 0) {
      throw "Main data publish failed with exit code $LASTEXITCODE"
    }

    & $py (Join-Path $ProjectRoot "scripts\publish_site_data_main.py") --branch gh-pages --message "Deploy v2 lazy-loaded site" --directory "site-v2=v2" --exclude "site-v2/data/app-data.json"
    if ($LASTEXITCODE -ne 0) {
      throw "GitHub Pages data publish failed with exit code $LASTEXITCODE"
    }
  }
}
finally {
  Pop-Location
}
