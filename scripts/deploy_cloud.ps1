<#
.SYNOPSIS
  Apply D1 schema and deploy the omaishort Cloudflare Worker (apps/cloud).

.DESCRIPTION
  Runs Worker unit tests, applies apps/cloud/schema.sql to Cloudflare D1 (omaishort-db),
  optionally sets AUTH_SECRET on the Worker, and deploys apps/cloud via wrangler.
#>
param(
  [switch]$SetAuthSecret,
  [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CloudDir = Join-Path $RepoRoot "apps\cloud"

if (-not $SkipTests) {
  Write-Host "==> [1/3] Running Cloudflare Worker tests..." -ForegroundColor Cyan
  node --test (Join-Path $CloudDir "test_worker.mjs")
  if ($LASTEXITCODE -ne 0) { throw "Worker tests failed" }
}

Push-Location $CloudDir
try {
  Write-Host "==> [2/3] Applying schema.sql to Cloudflare D1 (omaishort-db)..." -ForegroundColor Cyan
  npx wrangler d1 execute omaishort-db --remote --file=schema.sql
  if ($LASTEXITCODE -ne 0) { throw "D1 migration failed" }

  if ($SetAuthSecret) {
    Write-Host "==> Setting AUTH_SECRET secret on omaishort-db Worker..." -ForegroundColor Cyan
    npx wrangler secret put AUTH_SECRET
    if ($LASTEXITCODE -ne 0) { throw "Setting AUTH_SECRET failed" }
  }

  Write-Host "==> [3/3] Deploying omaishort-db Worker..." -ForegroundColor Cyan
  npx wrangler deploy
  if ($LASTEXITCODE -ne 0) { throw "Worker deploy failed" }

  Write-Host ""
  Write-Host "DONE! Verify /v1/health at your Worker URL (e.g. https://omaishort-db.<subdomain>.workers.dev/v1/health)." -ForegroundColor Green
  Write-Host "Then set GitHub Repository Variable OMAISHORT_CLOUD_API_URL to that Worker URL before tagging a desktop release." -ForegroundColor Yellow
} finally {
  Pop-Location
}
