# stop.ps1 - Stop three services (paths hardcoded)
$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Stop AI Teaching Eval System" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. nginx
Write-Host "[1/3] Stopping nginx..." -NoNewline
Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep 1
$left = Get-Process nginx -ErrorAction SilentlyContinue
if ($left) { $left | Stop-Process -Force -ErrorAction SilentlyContinue; Write-Host " stopped" -ForegroundColor Green }
else { Write-Host " stopped" -ForegroundColor Green }

# 2. Backend
Write-Host "[2/3] Stopping backend..." -NoNewline
$found = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.CommandLine -like "*uvicorn*app.main:app*") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $found = $true
    }
}
if ($found) { Write-Host " stopped" -ForegroundColor Green } else { Write-Host " not running" -ForegroundColor Gray }

# 3. Algorithm
Write-Host "[3/3] Stopping algorithm..." -NoNewline
$found = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.CommandLine -like "*uvicorn*src.main:app*") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $found = $true
    }
}
if ($found) { Write-Host " stopped" -ForegroundColor Green } else { Write-Host " not running" -ForegroundColor Gray }

Write-Host ""
Write-Host "All stopped" -ForegroundColor Green
Write-Host ""
