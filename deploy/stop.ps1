# stop.ps1 — 停止三服务
. "$PSScriptRoot\paths.ps1"
$cfg = $paths

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  停止 AI 教学评价系统" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 停止 nginx
Write-Host "[1/3] 停止 nginx..." -NoNewline
$nginxProcs = Get-Process -Name "nginx" -ErrorAction SilentlyContinue
if ($nginxProcs) {
    # nginx 优雅停止:nginx -s quit
    Push-Location $cfg.NginxDir
    try {
        & "$($cfg.NginxDir)\nginx.exe" -s quit 2>&1 | Out-Null
        Start-Sleep -Seconds 1
    } catch { }
    Pop-Location
    # 兜底强杀
    Get-Process -Name "nginx" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host " 已停止" -ForegroundColor Green
} else {
    Write-Host " 未运行" -ForegroundColor Gray
}

# 停止后端(匹配 8000 端口的 python 进程)
Write-Host "[2/3] 停止后端服务..." -NoNewline
$stopped = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
    if ($_.CommandLine -like "*uvicorn*app.main:app*") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
}
if ($stopped) { Write-Host " 已停止" -ForegroundColor Green }
else { Write-Host " 未运行" -ForegroundColor Gray }

# 停止算法服务(匹配 8001 端口的 python 进程)
Write-Host "[3/3] 停止算法服务..." -NoNewline
$stopped = $false
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
    if ($_.CommandLine -like "*uvicorn*src.main:app*") {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        $stopped = $true
    }
}
if ($stopped) { Write-Host " 已停止" -ForegroundColor Green }
else { Write-Host " 未运行" -ForegroundColor Gray }

Write-Host ""
Write-Host "全部停止完成" -ForegroundColor Green
Write-Host ""
