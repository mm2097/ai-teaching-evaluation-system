# start.ps1 — 启动三服务
# 启动算法服务(8001) → 后端(8000) → 前端 nginx(3000)
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\paths.ps1"
$cfg = $paths

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  启动 AI 教学评价系统" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 检查是否已在运行
$existing = Get-Process -Name "python","nginx" -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "$($cfg.MfqRoot)*"
}
if ($existing) {
    Write-Host "[警告] 检测到已有服务在运行,先停止再启动" -ForegroundColor Yellow
    & "$PSScriptRoot\stop.ps1"
    Start-Sleep -Seconds 2
}

# ============================================================
# 1. 启动算法服务(8001)
# ============================================================
Write-Host "[1/3] 启动算法服务 (端口 8001)..." -ForegroundColor Yellow
$algoLog = "$($cfg.LogsDir)\algorithm.log"
$algoWorkDir = "$($cfg.ProjectRoot)\algorithm"
$algoCmd = "$($cfg.PythonExe) -m uvicorn src.main:app --host 127.0.0.1 --port 8001"

Start-Process -FilePath $cfg.PythonExe `
    -ArgumentList "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8001" `
    -WorkingDirectory $algoWorkDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $algoLog `
    -RedirectStandardError $algoLog

# 等算法服务起来
Write-Host "  等待算法服务就绪..." -NoNewline
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8001/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Write-Host "." -NoNewline
}
if ($ready) {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " 超时" -ForegroundColor Red
    Write-Host "  算法服务未就绪,继续启动后端(后端会重试连接)" -ForegroundColor Yellow
}

# ============================================================
# 2. 启动后端(8000)
# ============================================================
Write-Host "[2/3] 启动后端服务 (端口 8000)..." -ForegroundColor Yellow
$backendLog = "$($cfg.LogsDir)\backend.log"
$backendWorkDir = "$($cfg.ProjectRoot)\backend"

Start-Process -FilePath $cfg.PythonExe `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $backendWorkDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $backendLog `
    -RedirectStandardError $backendLog

# 等后端起来
Write-Host "  等待后端就绪..." -NoNewline
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
    Write-Host "." -NoNewline
}
if ($ready) {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host " 超时" -ForegroundColor Red
    Write-Host "  后端未就绪,请查日志: $backendLog" -ForegroundColor Yellow
}

# ============================================================
# 3. 启动 nginx(3000)
# ============================================================
Write-Host "[3/3] 启动前端 nginx (端口 3000)..." -ForegroundColor Yellow
Push-Location $cfg.NginxDir
# 停掉残留 nginx
Get-Process -Name "nginx" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Start-Process -FilePath "$($cfg.NginxDir)\nginx.exe" `
    -WorkingDirectory $cfg.NginxDir `
    -WindowStyle Hidden
Pop-Location
Start-Sleep -Seconds 2

# 验证 nginx
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:3000" -UseBasicParsing -TimeoutSec 3
    if ($resp.StatusCode -eq 200) {
        Write-Host "  nginx 启动成功" -ForegroundColor Green
    }
} catch {
    Write-Host "  [警告] nginx 可能未正常启动,查日志: $($cfg.LogsDir)\nginx\error.log" -ForegroundColor Yellow
}

# ============================================================
# 完成
# ============================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  启动完成!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "访问地址: http://115.159.212.98:3000" -ForegroundColor Cyan
Write-Host ""
Write-Host "服务状态: .\status.ps1"
Write-Host "停止服务: .\stop.ps1"
Write-Host "查看日志: Get-Content $($cfg.LogsDir)\backend.log -Tail 20"
Write-Host ""
