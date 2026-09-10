# install.ps1 - Environment setup (current user only, no admin needed)
# Run: cd deploy; Set-ExecutionPolicy Bypass -Scope Process -Force; .\install.ps1

# Continue on errors - native tools (pip/npm) write warnings to stderr which
# would abort the script under "Stop". We handle real failures explicitly.
$ErrorActionPreference = "Continue"

# --- Force TLS 1.2 (Win Server defaults to TLS 1.0, causes HTTPS hangs) ---
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# --- Download helper ---
function Download-File {
    param($Url, $OutFile, $TimeoutSec = 120)
    Write-Host "    GET $Url"
    Invoke-WebRequest -Uri $Url -OutFile $OutFile -UseBasicParsing -TimeoutSec $TimeoutSec
    if (-not (Test-Path $OutFile)) { throw "Download failed (no file): $Url" }
    $sizeMB = [math]::Round((Get-Item $OutFile).Length / 1MB, 1)
    Write-Host "    done ($sizeMB MB)"
}

# --- Run native command via cmd /c to isolate stderr from PS error stream ---
function Invoke-Native {
    param([string]$CmdLine)
    cmd /c "$CmdLine 2>&1" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Command failed (exit $LASTEXITCODE): $CmdLine" }
}

# --- Path resolution ---
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = $PSScriptRoot }
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }
$MfqRoot = "C:\mfq"
$ProjectRoot = Split-Path -Parent $ScriptDir

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  AI Teaching Eval System - Install" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Install dir : $MfqRoot"
Write-Host "Project dir : $ProjectRoot"
Write-Host ""

New-Item -ItemType Directory -Force -Path $MfqRoot | Out-Null
New-Item -ItemType Directory -Force -Path "$MfqRoot\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$MfqRoot\logs\nginx" | Out-Null
New-Item -ItemType Directory -Force -Path "$MfqRoot\temp" | Out-Null

# ============================================================
# 1. Python 3.11 (embeddable)
# ============================================================
$PythonDir = "$MfqRoot\Python311"
$PythonExe = "$PythonDir\python.exe"
if ((Test-Path $PythonExe) -and (Test-Path "$PythonDir\Scripts\pip.exe")) {
    Write-Host "[1/5] Python 3.11 exists, skip" -ForegroundColor Green
} else {
    Write-Host "[1/5] Installing Python 3.11..." -ForegroundColor Yellow
    $pyUrl = "https://mirrors.huaweicloud.com/python/3.11.9/python-3.11.9-embed-amd64.zip"
    $pyZip = "$MfqRoot\temp\python.zip"
    Write-Host "  Downloading Python embeddable (~11MB)..."
    Download-File -Url $pyUrl -OutFile $pyZip -TimeoutSec 120
    Write-Host "  Extracting..."
    Expand-Archive -Path $pyZip -DestinationPath $PythonDir -Force
    Remove-Item $pyZip -Force

    # Enable site-packages in embed _pth file (required for pip)
    $pthFile = Get-ChildItem "$PythonDir\python*._pth" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pthFile) {
        $content = Get-Content $pthFile.FullName
        $content = $content -replace '^#\s*import site', 'import site'
        $content | Set-Content $pthFile.FullName -Encoding ascii
    }

    # Install pip
    Write-Host "  Installing pip..."
    $getPipUrl = "https://mirrors.aliyun.com/pypi/get-pip.py"
    $getPip = "$MfqRoot\temp\get-pip.py"
    Download-File -Url $getPipUrl -OutFile $getPip -TimeoutSec 60
    Invoke-Native "`"$PythonExe`" `"$getPip`" --quiet"
    Remove-Item $getPip -Force
    Invoke-Native "`"$PythonExe`" -m pip install --upgrade pip --quiet -i https://pypi.tuna.tsinghua.edu.cn/simple"
    Write-Host "  Python done" -ForegroundColor Green
}

# ============================================================
# 2. Node.js 22 (portable)
# ============================================================
$NodeDir = "$MfqRoot\nodejs"
$NodeExe = "$NodeDir\node.exe"
$NpmCmd = "$NodeDir\npm.cmd"
if (Test-Path $NodeExe) {
    Write-Host "[2/5] Node.js exists, skip" -ForegroundColor Green
} else {
    Write-Host "[2/5] Installing Node.js 22..." -ForegroundColor Yellow
    $nodeUrl = "https://mirrors.huaweicloud.com/nodejs/v22.18.0/node-v22.18.0-win-x64.zip"
    $nodeZip = "$MfqRoot\temp\node.zip"
    Write-Host "  Downloading (~30MB)..."
    Download-File -Url $nodeUrl -OutFile $nodeZip -TimeoutSec 180
    Write-Host "  Extracting..."
    Expand-Archive -Path $nodeZip -DestinationPath "$MfqRoot\temp\node-extract" -Force
    $extracted = Get-ChildItem "$MfqRoot\temp\node-extract" -Directory | Select-Object -First 1
    Move-Item $extracted.FullName $NodeDir -Force
    Remove-Item "$MfqRoot\temp\node-extract" -Recurse -Force
    Remove-Item $nodeZip -Force
    # npm config: current user + China mirror
    cmd /c "`"$NpmCmd`" config set cache `"$MfqRoot\npm-cache`" --global 2>&1" | Out-Null
    cmd /c "`"$NpmCmd`" config set registry https://registry.npmmirror.com --global 2>&1" | Out-Null
    Write-Host "  Node.js done" -ForegroundColor Green
}

# ============================================================
# 3. nginx (portable)
# ============================================================
$NginxDir = "$MfqRoot\nginx"
if (Test-Path "$NginxDir\nginx.exe") {
    Write-Host "[3/5] nginx exists, skip" -ForegroundColor Green
} else {
    Write-Host "[3/5] Installing nginx..." -ForegroundColor Yellow
    $nginxUrl = "https://mirrors.huaweicloud.com/nginx/nginx-1.27.5.zip"
    $nginxZip = "$MfqRoot\temp\nginx.zip"
    Write-Host "  Downloading..."
    try {
        Download-File -Url $nginxUrl -OutFile $nginxZip -TimeoutSec 120
    } catch {
        Write-Host "    primary failed, trying fallback..." -ForegroundColor Yellow
        $nginxUrl = "https://mirrors.huaweicloud.com/nginx/nginx-1.26.3.zip"
        Download-File -Url $nginxUrl -OutFile $nginxZip -TimeoutSec 120
    }
    Expand-Archive -Path $nginxZip -DestinationPath "$MfqRoot\temp\nginx-extract" -Force
    $extracted = Get-ChildItem "$MfqRoot\temp\nginx-extract" -Directory | Select-Object -First 1
    Move-Item $extracted.FullName $NginxDir -Force
    Remove-Item "$MfqRoot\temp\nginx-extract" -Recurse -Force
    Remove-Item $nginxZip -Force
    Write-Host "  nginx done" -ForegroundColor Green
}

# ============================================================
# 4. Python dependencies (Tsinghua mirror)
# ============================================================
$pipIndex = "https://pypi.tuna.tsinghua.edu.cn/simple"
Write-Host "[4/5] Installing Python deps..." -ForegroundColor Yellow

Write-Host "  Backend deps (chromadb/reportlab etc, 3-5 min)..."
Push-Location "$ProjectRoot\backend"
Invoke-Native "`"$PythonExe`" -m pip install -r requirements.txt -i $pipIndex --quiet"
Pop-Location

Write-Host "  Algorithm deps..."
Push-Location "$ProjectRoot\algorithm"
Invoke-Native "`"$PythonExe`" -m pip install -r requirements.txt -i $pipIndex --quiet"
Pop-Location
Write-Host "  Python deps done" -ForegroundColor Green

# ============================================================
# 5. Build frontend
# ============================================================
Write-Host "[5/5] Building frontend..." -ForegroundColor Yellow
Push-Location "$ProjectRoot\frontend"
Write-Host "  npm install (2-3 min)..."
cmd /c "`"$NpmCmd`" install --registry=https://registry.npmmirror.com 2>&1" | Select-Object -Last 5
if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] npm install had errors" -ForegroundColor Yellow }
Write-Host "  Building production bundle..."
cmd /c "`"$NpmCmd`" run build-only 2>&1" | Select-Object -Last 5
if ($LASTEXITCODE -ne 0) { Write-Host "  [WARN] build had errors" -ForegroundColor Yellow }
Pop-Location

if (Test-Path "$ProjectRoot\frontend\dist\index.html") {
    Write-Host "  Frontend build done" -ForegroundColor Green
} else {
    Write-Host "  [WARN] Frontend build may have failed, check dist/" -ForegroundColor Red
}

# ============================================================
# 6. Generate nginx config
# ============================================================
Write-Host "Generating nginx config..." -ForegroundColor Yellow
$nginxConfDir = "$NginxDir\conf"
$distPath = "$ProjectRoot\frontend\dist".Replace("\", "/")

$confContent = @"
worker_processes  1;

events {
    worker_connections  1024;
}

http {
    include       mime.types;
    default_type  application/octet-stream;
    sendfile      on;
    keepalive_timeout  65;
    client_max_body_size 20m;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1024;

    server {
        listen      3000;
        server_name _;

        root  $distPath;
        index index.html;

        location /api/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host `$host;
            proxy_set_header X-Real-IP `$remote_addr;
            proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto `$scheme;
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }

        location / {
            try_files `$uri `$uri/ /index.html;
        }
    }
}
"@

$nginxMainConf = "$nginxConfDir\nginx.conf"
# Write UTF-8 WITHOUT BOM (nginx chokes on BOM: "unknown directive")
[System.IO.File]::WriteAllText($nginxMainConf, $confContent, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "  nginx config written" -ForegroundColor Green

# ============================================================
# 7. Save paths for start/stop/status scripts
# ============================================================
$config = @"
`$paths = @{
    MfqRoot     = '$MfqRoot'
    ProjectRoot = '$ProjectRoot'
    PythonExe   = '$PythonExe'
    NodeExe     = '$NodeExe'
    NginxDir    = '$NginxDir'
    LogsDir     = '$MfqRoot\logs'
}
"@
$config | Out-File -FilePath "$ScriptDir\paths.ps1" -Encoding utf8 -Force

# ============================================================
# Done
# ============================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  Install complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Ensure algorithm\.env has LLM_API_KEY"
Write-Host "  2. Ensure backend\.env has SECRET_KEY (32+ chars) and ENVIRONMENT=production"
Write-Host "  3. Start: .\start.ps1"
Write-Host "  4. Visit: http://115.159.212.98:3000"
Write-Host ""
$pyVer = cmd /c "`"$PythonExe`" --version 2>&1"
$nodeVer = cmd /c "`"$NodeExe`" --version 2>&1"
Write-Host "Installed: Python $pyVer, Node $nodeVer"
$usedMB = [math]::Round((Get-ChildItem $MfqRoot -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "Disk used: $usedMB MB"
Write-Host ""
