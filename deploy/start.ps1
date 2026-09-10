# start.ps1 - Start three services (algorithm 8001 -> backend 8000 -> nginx 3000)
# Paths hardcoded - no dependency on paths.ps1

$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$MfqRoot     = "C:\mfq"
$ProjectRoot = "C:\mfq\ai-teaching-evaluation-system"
$PythonExe   = "C:\mfq\Python311\python.exe"
$NginxDir    = "C:\mfq\nginx"
$LogsDir     = "C:\mfq\logs"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Start AI Teaching Eval System" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Stop existing
Get-Process nginx -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*uvicorn*src.main:app*" -or $_.CommandLine -like "*uvicorn*app.main:app*"
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# ============================================================
# 1. Algorithm service (8001)
# ============================================================
Write-Host "[1/3] Starting algorithm (port 8001)..." -ForegroundColor Yellow
Start-Process -FilePath $PythonExe `
    -ArgumentList "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8001" `
    -WorkingDirectory "$ProjectRoot\algorithm" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$LogsDir\algorithm.out.log" `
    -RedirectStandardError "$LogsDir\algorithm.err.log"

Write-Host "  Waiting..." -NoNewline
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Write-Host "." -NoNewline
}
if ($ready) { Write-Host " OK" -ForegroundColor Green }
else { Write-Host " TIMEOUT (check $LogsDir\algorithm.err.log)" -ForegroundColor Red }

# ============================================================
# 2. Backend (8000)
# ============================================================
Write-Host "[2/3] Starting backend (port 8000)..." -ForegroundColor Yellow
Start-Process -FilePath $PythonExe `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory "$ProjectRoot\backend" `
    -WindowStyle Hidden `
    -RedirectStandardOutput "$LogsDir\backend.out.log" `
    -RedirectStandardError "$LogsDir\backend.err.log"

Write-Host "  Waiting..." -NoNewline
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Write-Host "." -NoNewline
}
if ($ready) { Write-Host " OK" -ForegroundColor Green }
else { Write-Host " TIMEOUT (check $LogsDir\backend.err.log)" -ForegroundColor Red }

# ============================================================
# 3. nginx (3000)
# ============================================================
Write-Host "[3/3] Starting nginx (port 3000)..." -ForegroundColor Yellow
Push-Location $NginxDir
Start-Process -FilePath "$NginxDir\nginx.exe" -WorkingDirectory $NginxDir -WindowStyle Hidden
Pop-Location
Start-Sleep -Seconds 2

try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 3
    if ($r.StatusCode -eq 200) { Write-Host "  nginx OK" -ForegroundColor Green }
} catch {
    Write-Host "  nginx FAILED (check conf for BOM)" -ForegroundColor Red
    Write-Host "  Fix: run the BOM-removal command" -ForegroundColor Yellow
}

# ============================================================
# Done
# ============================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Started!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Visit: http://115.159.212.98:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stop : .\stop.ps1"
Write-Host "Logs : $LogsDir\*.log"
Write-Host ""
