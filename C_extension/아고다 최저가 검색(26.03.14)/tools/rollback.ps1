param(
  [Parameter(Mandatory = $true)]
  [string]$Name
)

$root = Split-Path -Parent $PSScriptRoot
$snapshotPath = Join-Path $root "snapshots\$Name"
$metaPath = Join-Path $snapshotPath "meta.json"

if (-not (Test-Path $snapshotPath)) {
  throw "Snapshot not found: $Name"
}

if (-not (Test-Path $metaPath)) {
  throw "Snapshot metadata not found: $Name"
}

$meta = Get-Content -Raw $metaPath | ConvertFrom-Json

foreach ($file in $meta.files) {
  $sourcePath = Join-Path $snapshotPath $file
  $targetPath = Join-Path $root $file
  $targetDir = Split-Path -Parent $targetPath

  if ($targetDir -and -not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
  }

  Copy-Item -Path $sourcePath -Destination $targetPath -Force
}

Write-Host "Rolled back snapshot: $Name"
