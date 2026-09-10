# status.ps1 - Check three services status
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = $PSScriptRoot }
. "$ScriptDir\paths.ps1"
$cfg = $paths

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Service Status" -ForegroundColor Cyan
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

function Show-Status {
    param($Name, $Port, $HealthUrl)
    $portOpen = Test-Port -Port $Port
    $healthOk = $false
    $detail = ""
    if ($portOpen -and $HealthUrl) {
        try {
            $resp = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 3
            $healthOk = ($resp.StatusCode -eq 200)
            $detail = $resp.Content.Substring(0, [Math]::Min(80, $resp.Content.Length))
        } catch {
            $detail = $_.Exception.Message.Substring(0, [Math]::Min(60, $_.Exception.Message.Length))
        }
    }
    if ($healthOk) {
        Write-Host "  [$Name] RUNNING OK" -ForegroundColor Green
        Write-Host "    port $Port open, health check passed" -ForegroundColor Gray
        Write-Host "    resp: $detail" -ForegroundColor DarkGray
    } elseif ($portOpen) {
        Write-Host "  [$Name] PORT OPEN, health check failed" -ForegroundColor Yellow
        if ($detail) { Write-Host "    $detail" -ForegroundColor DarkGray }
    } else {
        Write-Host "  [$Name] NOT RUNNING" -ForegroundColor Red
        Write-Host "    port $Port closed" -ForegroundColor Gray
    }
    Write-Host ""
}

Show-Status -Name "Algorithm (8001)" -Port 8001 -HealthUrl "http://127.0.0.1:8001/health"
Show-Status -Name "Backend    (8000)" -Port 8000 -HealthUrl "http://127.0.0.1:8000/api/health"
Show-Status -Name "Frontend   (3000)" -Port 3000 -HealthUrl "http://127.0.0.1:3000"

Write-Host "Processes:"
$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='nginx.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*$($cfg.MfqRoot)*" -or $_.CommandLine -like "*uvicorn*" -or $_.Name -eq "nginx.exe" }
if ($procs) {
    foreach ($p in $procs) {
        $cmd = if ($p.CommandLine -and $p.CommandLine.Length -gt 80) { $p.CommandLine.Substring(0, 80) + "..." } else { $p.CommandLine }
        Write-Host "  PID $($p.ProcessId)  $($p.Name)" -ForegroundColor Gray
        Write-Host "    $cmd" -ForegroundColor DarkGray
    }
} else {
    Write-Host "  (none)" -ForegroundColor Gray
}
Write-Host ""
Write-Host "Logs: $($cfg.LogsDir)"
Write-Host ""
