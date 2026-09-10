# status.ps1 — 查看三服务运行状态
. "$PSScriptRoot\paths.ps1"
$cfg = $paths

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  AI 教学评价系统 - 服务状态" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

function Test-Port {
    param($Port)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", $Port)
        $tcp.Close()
        return $true
    } catch { return $false }
}

function Get-ServiceStatus {
    param($Name, $Port, $HealthUrl)
    $portOpen = Test-Port -Port $Port
    $healthOk = $false
    $healthDetail = ""
    if ($portOpen -and $HealthUrl) {
        try {
            $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
            $healthOk = ($resp.StatusCode -eq 200)
            $healthDetail = $resp.Content.Substring(0, [Math]::Min(80, $resp.Content.Length))
        } catch {
            $healthDetail = $_.Exception.Message.Substring(0, [Math]::Min(60, $_.Exception.Message.Length))
        }
    }
    if ($healthOk) {
        Write-Host "  [$Name] 运行中 ✓" -ForegroundColor Green
        Write-Host "    端口 $Port 开放,健康检查通过" -ForegroundColor Gray
        Write-Host "    响应: $healthDetail" -ForegroundColor DarkGray
    } elseif ($portOpen) {
        Write-Host "  [$Name] 端口开放但健康检查未过 ?" -ForegroundColor Yellow
        Write-Host "    端口 $Port 开放,但接口未响应" -ForegroundColor Gray
        if ($healthDetail) { Write-Host "    $healthDetail" -ForegroundColor DarkGray }
    } else {
        Write-Host "  [$Name] 未运行 ✗" -ForegroundColor Red
        Write-Host "    端口 $Port 未开放" -ForegroundColor Gray
    }
    Write-Host ""
}

Get-ServiceStatus -Name "算法服务 (8001)" -Port 8001 -HealthUrl "http://127.0.0.1:8001/health"
Get-ServiceStatus -Name "后端服务 (8000)" -Port 8000 -HealthUrl "http://127.0.0.1:8000/api/health"
Get-ServiceStatus -Name "前端 nginx (3000)" -Port 3000 -HealthUrl "http://127.0.0.1:3000"

Write-Host "进程列表:"
Write-Host "  ---"
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='nginx.exe'" |
    Where-Object { $_.CommandLine -like "*$($cfg.MfqRoot)*" -or $_.CommandLine -like "*uvicorn*" -or $_.Name -eq "nginx.exe" }
if ($procs) {
    foreach ($p in $procs) {
        $cmd = if ($p.CommandLine.Length -gt 80) { $p.CommandLine.Substring(0, 80) + "..." } else { $p.CommandLine }
        Write-Host "  PID $($p.ProcessId)  $($p.Name)" -ForegroundColor Gray
        Write-Host "    $cmd" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  (无相关进程)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "日志目录: $($cfg.LogsDir)"
Write-Host ""
