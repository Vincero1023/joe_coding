param(
  [Parameter(Mandatory = $true)]
  [string]$Name,

  [string]$Note = "",

  [string[]]$Files = @(
    "background.js",
    "popup.js",
    "popup.html",
    "popup.css",
    "catalog.js",
    "manifest.json",
    "README.md"
  )
)

$root = Split-Path -Parent $PSScriptRoot
$snapshotRoot = Join-Path $root "snapshots"
$snapshotPath = Join-Path $snapshotRoot $Name
$createdAt = (Get-Date).ToString("yyyy-MM-ddTHH:mm:ssK")

if (Test-Path $snapshotPath) {
  throw "Snapshot already exists: $Name"
}

New-Item -ItemType Directory -Path $snapshotPath -Force | Out-Null

$copiedFiles = @()
foreach ($file in $Files) {
  $sourcePath = Join-Path $root $file
  if (-not (Test-Path $sourcePath)) {
    continue
  }

  $targetPath = Join-Path $snapshotPath $file
  $targetDir = Split-Path -Parent $targetPath
  if ($targetDir -and -not (Test-Path $targetDir)) {
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
  }

  Copy-Item -Path $sourcePath -Destination $targetPath -Force
  $copiedFiles += $file
}

$meta = [ordered]@{
  name = $Name
  note = $Note
  createdAt = $createdAt
  files = $copiedFiles
}

$metaPath = Join-Path $snapshotPath "meta.json"
$meta | ConvertTo-Json -Depth 4 | Set-Content -Path $metaPath -Encoding UTF8

$filesText = if ($copiedFiles.Count) {
  ($copiedFiles | ForEach-Object { '`' + $_ + '`' }) -join ", "
} else {
  "(none)"
}

$rollbackCommand = '`powershell -ExecutionPolicy Bypass -File .\tools\rollback.ps1 -Name ' + $Name + '`'

$logPath = Join-Path $root "STEP_LOG.md"
$entry = @"
## $Name
- Created: $createdAt
- Note: $Note
- Files: $filesText
- Rollback: $rollbackCommand

"@

Add-Content -Path $logPath -Value $entry -Encoding UTF8

Write-Host "Created snapshot: $Name"
