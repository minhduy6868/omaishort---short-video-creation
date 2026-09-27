$ErrorActionPreference = "Stop"
$repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$python = Join-Path $repo "apps\api\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing $python. Create the API venv first (see README)."
}
Set-Location (Join-Path $repo "apps\api")
& $python -m omaishort.desktop
