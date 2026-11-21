<#
.SYNOPSIS
  Build a self-contained Windows x64 portable desktop bundle for omaishort.

.DESCRIPTION
  Produces dist\omaishort-win-x64.zip containing:
    - python\       Embedded Python 3.11 (64-bit) with all API dependencies installed
    - bin\          Static ffmpeg.exe (extracted from imageio-ffmpeg)
    - app\          Clean omaishort backend, schema, prompts, assets, samples, and built Studio UI
    - Omaishort.bat One-click launcher (auto-creates local .env + SQLite DB on first run)
    - Omaishort-CLI.bat Helper for CLI commands (--reverse, --chatgpt-login, --muse-login, etc.)
    - HUONG-DAN.txt Quick-start instructions in Vietnamese

  Never bundles .env, data/, .venv/, tests/, or Cloudflare D1 admin keys.
#>
param(
  [string]$PythonVersion = "3.11.9",
  [string]$OutName = "omaishort-win-x64",
  [switch]$SkipWebBuild,
  [switch]$NoZip
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DistRoot = Join-Path $RepoRoot "dist"
$CacheDir = Join-Path $DistRoot ".cache"
$StageDir = Join-Path $DistRoot $OutName
$ZipPath  = Join-Path $DistRoot "$OutName.zip"

New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

Write-Host "==> [1/6] Building Studio web UI (apps/web/dist)..." -ForegroundColor Cyan
$WebDir = Join-Path $RepoRoot "apps\web"
if (-not $SkipWebBuild) {
  Push-Location $WebDir
  try {
    if (-not (Test-Path (Join-Path $WebDir "node_modules"))) {
      npm ci
    }
    npm run build
  } finally {
    Pop-Location
  }
}
$WebDist = Join-Path $WebDir "dist"
if (-not (Test-Path (Join-Path $WebDist "index.html"))) {
  throw "Missing $WebDist\index.html. Run without -SkipWebBuild."
}

Write-Host "==> [2/6] Preparing clean staging folder: $StageDir" -ForegroundColor Cyan
if (Test-Path $StageDir) {
  Remove-Item -Recurse -Force $StageDir
}
New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
$PyDir  = Join-Path $StageDir "python"
$BinDir = Join-Path $StageDir "bin"
$AppDir = Join-Path $StageDir "app"
New-Item -ItemType Directory -Force -Path $PyDir, $BinDir, $AppDir | Out-Null

Write-Host "==> [3/6] Downloading & unpacking Python $PythonVersion embeddable (amd64)..." -ForegroundColor Cyan
$PyZipName = "python-$PythonVersion-embed-amd64.zip"
$PyZipPath = Join-Path $CacheDir $PyZipName
$PyUrl     = "https://www.python.org/ftp/python/$PythonVersion/$PyZipName"
if (-not (Test-Path $PyZipPath)) {
  Invoke-WebRequest -Uri $PyUrl -OutFile $PyZipPath
}
Expand-Archive -Path $PyZipPath -DestinationPath $PyDir -Force

# Enable site-packages and add bundled app + schema paths to python311._pth
$PthFile = Get-ChildItem -Path $PyDir -Filter "python*._pth" | Select-Object -First 1
if (-not $PthFile) {
  throw "Could not locate python*._pth inside $PyDir"
}
$PthLines = Get-Content $PthFile.FullName | ForEach-Object {
  if ($_ -match "^#\s*import site") { "import site" } else { $_ }
}
$PthLines += "..\app\apps\api"
$PthLines += "..\app\packages\schema"
Set-Content -Path $PthFile.FullName -Value $PthLines -Encoding ASCII

$PyExe = Join-Path $PyDir "python.exe"
$GetPipPath = Join-Path $CacheDir "get-pip.py"
if (-not (Test-Path $GetPipPath)) {
  Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $GetPipPath
}
Write-Host "==> [4/6] Installing pip & API dependencies into embedded Python..." -ForegroundColor Cyan
& $PyExe $GetPipPath --no-warn-script-location --quiet
if ($LASTEXITCODE -ne 0) { throw "get-pip.py failed" }

$ReqFile = Join-Path $RepoRoot "apps\api\requirements.txt"
& $PyExe -m pip install --no-cache-dir --no-warn-script-location -r $ReqFile
if ($LASTEXITCODE -ne 0) { throw "pip install requirements failed" }

# Extract bundled static ffmpeg.exe from imageio-ffmpeg into bin\ffmpeg.exe
Write-Host "==> [5/6] Bundling static FFmpeg binary..." -ForegroundColor Cyan
$FfmpegSource = (& $PyExe -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())").Trim()
if (-not $FfmpegSource -or -not (Test-Path $FfmpegSource)) {
  throw "Could not resolve static ffmpeg from imageio-ffmpeg"
}
Copy-Item -Path $FfmpegSource -Destination (Join-Path $BinDir "ffmpeg.exe") -Force

Write-Host "==> [6/6] Copying clean app runtime (excluding .env, data, .venv, caches)..." -ForegroundColor Cyan
function Copy-CleanTree([string]$Source, [string]$Dest) {
  New-Item -ItemType Directory -Force -Path $Dest | Out-Null
  $ExcludeDirs = @("__pycache__", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache")
  Get-ChildItem -Path $Source -Force | ForEach-Object {
    if ($_.PSIsContainer) {
      if ($ExcludeDirs -contains $_.Name) { return }
      Copy-CleanTree $_.FullName (Join-Path $Dest $_.Name)
    } else {
      if ($_.Extension -in @(".pyc", ".pyo", ".db", ".sqlite", ".log")) { return }
      if ($_.Name -eq ".env") { return }
      Copy-Item -Path $_.FullName -Destination (Join-Path $Dest $_.Name) -Force
    }
  }
}

Copy-CleanTree (Join-Path $RepoRoot "apps\api\omaishort")             (Join-Path $AppDir "apps\api\omaishort")
Copy-Item (Join-Path $RepoRoot "apps\api\bootstrap.py")               (Join-Path $AppDir "apps\api\bootstrap.py") -Force
Copy-Item (Join-Path $RepoRoot "apps\api\run.py")                     (Join-Path $AppDir "apps\api\run.py") -Force
Copy-CleanTree (Join-Path $RepoRoot "packages\schema\omaishort_schema") (Join-Path $AppDir "packages\schema\omaishort_schema")
Copy-CleanTree $WebDist                                               (Join-Path $AppDir "apps\web\dist")
Copy-CleanTree (Join-Path $RepoRoot "prompts")                        (Join-Path $AppDir "prompts")
Copy-CleanTree (Join-Path $RepoRoot "assets")                         (Join-Path $AppDir "assets")
Copy-CleanTree (Join-Path $RepoRoot "samples")                        (Join-Path $AppDir "samples")

# Write 1-click launcher: Omaishort.bat
$LauncherBat = @'
@echo off
setlocal
chcp 65001 >nul
title omaishort Studio (Local Engine)
set "BASE=%~dp0"
if "%BASE:~-1%"=="\" set "BASE=%BASE:~0,-1%"
set "OMAISHORT_PORTABLE=1"
set "OMAISHORT_ROOT=%BASE%\app"
set "OMAISHORT_WEB_DIST=%BASE%\app\apps\web\dist"
set "OMAISHORT_ENV_FILE=%BASE%\.env"
set "DATA_DIR=%BASE%\data"
set "FFMPEG_PATH=%BASE%\bin\ffmpeg.exe"
set "PATH=%BASE%\bin;%BASE%\python;%PATH%"
echo Dang khoi dong omaishort Studio...
"%BASE%\python\python.exe" -m omaishort.desktop
if errorlevel 1 (
  echo.
  echo [LOI] omaishort dung dot ngot. Xem log ben tren.
  pause
)
'@
Set-Content -Path (Join-Path $StageDir "Omaishort.bat") -Value $LauncherBat -Encoding ASCII

# Write CLI helper: Omaishort-CLI.bat
$CliBat = @'
@echo off
setlocal
chcp 65001 >nul
set "BASE=%~dp0"
if "%BASE:~-1%"=="\" set "BASE=%BASE:~0,-1%"
set "OMAISHORT_PORTABLE=1"
set "OMAISHORT_ROOT=%BASE%\app"
set "OMAISHORT_ENV_FILE=%BASE%\.env"
set "DATA_DIR=%BASE%\data"
set "FFMPEG_PATH=%BASE%\bin\ffmpeg.exe"
set "PATH=%BASE%\bin;%BASE%\python;%PATH%"
"%BASE%\python\python.exe" -m omaishort %*
'@
Set-Content -Path (Join-Path $StageDir "Omaishort-CLI.bat") -Value $CliBat -Encoding ASCII

# Write end-user Vietnamese guide
$GuideTxt = @'
==========================================================
  omaishort — Ung dung tao video ngan 1080x1920 (Windows)
==========================================================

1. CHAY NGAY (KHONG CAN CAI PYTHON HAY FFMPEG)
   - Giai nen toan bo thu muc nay ra o cung (khong chay truc tiep trong file .zip).
   - Bam dup vao file: Omaishort.bat
   - Cua so Studio se tu mo tai http://127.0.0.1:8765/work
   - Lan dau chay, ung dung tu tao file .env va database SQLite rieng trong thu muc data\.

2. TAO TAI KHOAN & SU DUNG
   - Dang ky 1 tai khoan cuc bo tren may ban (luu rieng trong data\omaishort.db).
   - Chon Drama / News / Kien thuc, dan noi dung (hoac tai 1 video mau de "Dich nguoc video mau").
   - Video xuat ra 1080x1920 @ 30fps nam trong data\jobs\<id>\render\short.mp4.

3. TUY CHON NANG CAO (MO FILE .env DE DIEN KEY NEU CO)
   - Dung ChatGPT / Muse / Grok bang tai khoan ca nhan: vao trang Account trong Studio -> bam Dang nhap.
   - Hoac dien API key vao file .env (OPENAI_API_KEY, GEMINI_API_KEY, XAI_API_KEY, HF_TOKEN, ELEVENLABS_API_KEY, REA_VLM_*), roi tat va mo lai Omaishort.bat.

4. DUNG QUA DONG LENH (CLI)
   - Dich nguoc video mau:
     Omaishort-CLI.bat --reverse path\to\sample.mp4 --language vi
   - Tao video tu mau:
     Omaishort-CLI.bat app\samples\confession-60s.md --template tpl_xxxxxxxxxx
'@
Set-Content -Path (Join-Path $StageDir "HUONG-DAN.txt") -Value $GuideTxt -Encoding UTF8

# Smoke test embedded Python imports & FFmpeg before zipping
Write-Host "==> Running portable smoke test..." -ForegroundColor Cyan
$env:OMAISHORT_PORTABLE = "1"
$env:OMAISHORT_ROOT = $AppDir
$env:OMAISHORT_WEB_DIST = (Join-Path $AppDir "apps\web\dist")
$env:FFMPEG_PATH = (Join-Path $BinDir "ffmpeg.exe")
& $PyExe -c "import omaishort.main, omaishort.desktop; print('OK:', omaishort.desktop.WEB_DIST)"
if ($LASTEXITCODE -ne 0) { throw "Portable Python import smoke test failed" }
& (Join-Path $BinDir "ffmpeg.exe") -version | Select-Object -First 1

if (-not $NoZip) {
  Write-Host "==> Creating zip archive: $ZipPath" -ForegroundColor Cyan
  if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
  Compress-Archive -Path "$StageDir\*" -DestinationPath $ZipPath -CompressionLevel Optimal
  $Hash = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  $SizeMB = [Math]::Round((Get-Item $ZipPath).Length / 1MB, 1)
  "$Hash  $OutName.zip" | Set-Content -Path (Join-Path $DistRoot "SHA256SUMS.txt") -Encoding ASCII
  Write-Host ""
  Write-Host "DONE! Portable package ready:" -ForegroundColor Green
  Write-Host "  Zip:    $ZipPath ($SizeMB MB)"
  Write-Host "  SHA256: $Hash"
} else {
  Write-Host "DONE! Staged folder ready at: $StageDir" -ForegroundColor Green
}
