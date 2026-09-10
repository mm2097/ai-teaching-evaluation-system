# install.ps1 — 环境安装脚本(仅当前用户,不需要管理员)
# 在服务器上运行:cd deploy; Set-ExecutionPolicy Bypass -Scope Process -Force; .\install.ps1

$ErrorActionPreference = "Stop"
$MfqRoot = "C:\mfq"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  AI 教学评价系统 - 环境安装" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "安装目录: $MfqRoot"
Write-Host "项目目录: $ProjectRoot"
Write-Host ""

# 创建目录
New-Item -ItemType Directory -Force -Path $MfqRoot | Out-Null
New-Item -ItemType Directory -Force -Path "$MfqRoot\logs" | Out-Null
New-Item -ItemType Directory -Force -Path "$MfqRoot\logs\nginx" | Out-Null
New-Item -ItemType Directory -Force -Path "$MfqRoot\temp" | Out-Null

# ============================================================
# 1. 安装 Python 3.11(embeddable 绿色版,仅当前用户)
# ============================================================
# embed 版没有 pip,需用 get-pip.py 手动装;装完和正式版功能一致
$PythonDir = "$MfqRoot\Python311"
if (Test-Path "$PythonDir\python.exe" -and (Test-Path "$PythonDir\Scripts\pip.exe")) {
    Write-Host "[1/5] Python 3.11 已存在,跳过" -ForegroundColor Green
} else {
    Write-Host "[1/5] 安装 Python 3.11..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip"
    $pyZip = "$MfqRoot\temp\python.zip"
    Write-Host "  下载 Python embeddable(约 11MB)..."
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyZip -UseBasicParsing
    Write-Host "  解压中..."
    Expand-Archive -Path $pyZip -DestinationPath $PythonDir -Force
    Remove-Item $pyZip -Force

    # embed 版的 python311._pth 默认禁用了 site-packages,要改开才能装 pip
    $pthFile = Get-ChildItem "$PythonDir\python*._pth" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($pthFile) {
        $content = Get-Content $pthFile.FullName
        # 取消 #import site 的注释
        $content = $content -replace '^#\s*import site', 'import site'
        $content | Set-Content $pthFile.FullName -Encoding ascii
    }

    # 装 pip
    Write-Host "  安装 pip..."
    $getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
    $getPip = "$MfqRoot\temp\get-pip.py"
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPip -UseBasicParsing
    & "$PythonDir\python.exe" $getPip 2>&1 | Out-Null
    Remove-Item $getPip -Force
    & "$PythonDir\python.exe" -m pip install --upgrade pip 2>&1 | Out-Null
    Write-Host "  Python 安装完成: $(& "$PythonDir\python.exe" --version)" -ForegroundColor Green
}

# ============================================================
# 2. 安装 Node.js 22(绿色版,仅当前用户)
# ============================================================
$NodeDir = "$MfqRoot\nodejs"
if (Test-Path "$NodeDir\node.exe") {
    Write-Host "[2/5] Node.js 已存在,跳过" -ForegroundColor Green
} else {
    Write-Host "[2/5] 安装 Node.js 22..." -ForegroundColor Yellow
    $nodeUrl = "https://nodejs.org/dist/v22.18.0/node-v22.18.0-win-x64.zip"
    $nodeZip = "$MfqRoot\temp\node.zip"
    Write-Host "  下载中(约 30MB)..."
    Invoke-WebRequest -Uri $nodeUrl -OutFile $nodeZip -UseBasicParsing
    Write-Host "  解压中..."
    Expand-Archive -Path $nodeZip -DestinationPath "$MfqRoot\temp\node-extract" -Force
    # 解压后是 node-v22.18.0-win-x64 目录,移动到 nodejs
    $extracted = Get-ChildItem "$MfqRoot\temp\node-extract" -Directory | Select-Object -First 1
    Move-Item $extracted.FullName $NodeDir -Force
    Remove-Item "$MfqRoot\temp\node-extract" -Recurse -Force
    Remove-Item $nodeZip -Force
    # npm 配置:仅当前用户
    & "$NodeDir\npm.cmd" config set cache "$MfqRoot\npm-cache" --global 2>&1 | Out-Null
    Write-Host "  Node.js 安装完成: $(& "$NodeDir\node.exe" --version)" -ForegroundColor Green
}

# ============================================================
# 3. 安装 nginx(绿色版)
# ============================================================
$NginxDir = "$MfqRoot\nginx"
if (Test-Path "$NginxDir\nginx.exe") {
    Write-Host "[3/5] nginx 已存在,跳过" -ForegroundColor Green
} else {
    Write-Host "[3/5] 安装 nginx..." -ForegroundColor Yellow
    $nginxUrl = "https://nginx.org/download/nginx-1.27.5.zip"
    $nginxZip = "$MfqRoot\temp\nginx.zip"
    Write-Host "  下载中..."
    try {
        Invoke-WebRequest -Uri $nginxUrl -OutFile $nginxZip -UseBasicParsing
    } catch {
        # 备用地址
        $nginxUrl = "https://nginx.org/download/nginx-1.26.3.zip"
        Invoke-WebRequest -Uri $nginxUrl -OutFile $nginxZip -UseBasicParsing
    }
    Expand-Archive -Path $nginxZip -DestinationPath "$MfqRoot\temp\nginx-extract" -Force
    $extracted = Get-ChildItem "$MfqRoot\temp\nginx-extract" -Directory | Select-Object -First 1
    Move-Item $extracted.FullName $NginxDir -Force
    Remove-Item "$MfqRoot\temp\nginx-extract" -Recurse -Force
    Remove-Item $nginxZip -Force
    Write-Host "  nginx 安装完成" -ForegroundColor Green
}

# ============================================================
# 4. 安装 Python 依赖(后端 + 算法服务)
# ============================================================
$PythonExe = "$MfqRoot\Python311\python.exe"
Write-Host "[4/5] 安装 Python 依赖..." -ForegroundColor Yellow

Write-Host "  后端依赖..."
Push-Location "$ProjectRoot\backend"
& $PythonExe -m pip install --upgrade pip 2>&1 | Out-Null
& $PythonExe -m pip install -r requirements.txt 2>&1 | Out-Null
Pop-Location

Write-Host "  算法服务依赖..."
Push-Location "$ProjectRoot\algorithm"
& $PythonExe -m pip install -r requirements.txt 2>&1 | Out-Null
Pop-Location
Write-Host "  Python 依赖安装完成" -ForegroundColor Green

# ============================================================
# 5. 构建前端
# ============================================================
$NodeExe = "$MfqRoot\nodejs\node.exe"
$NpmCmd = "$MfqRoot\nodejs\npm.cmd"
Write-Host "[5/5] 构建前端..." -ForegroundColor Yellow

Push-Location "$ProjectRoot\frontend"
Write-Host "  安装 npm 依赖(首次较慢)..."
& $NpmCmd install 2>&1 | Out-Null
Write-Host "  构建生产版本..."
& $NpmCmd run build-only 2>&1 | Out-Null
Pop-Location

if (Test-Path "$ProjectRoot\frontend\dist\index.html") {
    Write-Host "  前端构建完成" -ForegroundColor Green
} else {
    Write-Host "  [警告] 前端构建可能失败,请检查 dist 目录" -ForegroundColor Red
    Write-Host "  可手动执行: cd frontend; npm run build-only" -ForegroundColor Yellow
}

# ============================================================
# 6. 生成 nginx 配置
# ============================================================
Write-Host "生成 nginx 配置..." -ForegroundColor Yellow
$nginxBin = "$NginxDir\nginx.exe"
$nginxConfDir = "$NginxDir\conf"
$nginxConf = "$nginxConfDir\aies.conf"
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

    # gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1024;

    server {
        listen      3000;
        server_name _;

        root  $distPath;
        index index.html;

        # 反向代理 /api -> 后端 8000
        location /api/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_http_version 1.1;
            proxy_set_header Host `$host;
            proxy_set_header X-Real-IP `$remote_addr;
            proxy_set_header X-Forwarded-For `$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto `$scheme;
            # SSE 流式支持
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 300s;
            proxy_send_timeout 300s;
        }

        # SPA 路由回退
        location / {
            try_files `$uri `$uri/ /index.html;
        }
    }
}
"@

# nginx 默认主配置 include conf.d,但绿色版默认没有 include。
# 直接把配置写成 nginx.conf,覆盖默认的。
$nginxMainConf = "$nginxConfDir\nginx.conf"
$confContent | Out-File -FilePath $nginxMainConf -Encoding utf8 -Force
Write-Host "  nginx 配置已写入: $nginxMainConf" -ForegroundColor Green

# ============================================================
# 7. 生成启动/停止/状态脚本辅助文件
# ============================================================
Write-Host "生成服务脚本..." -ForegroundColor Yellow

# 记录安装路径,供 start/stop/status 脚本读取
$config = @"
@{
    MfqRoot     = '$MfqRoot'
    ProjectRoot = '$ProjectRoot'
    PythonExe   = '$PythonExe'
    NodeExe     = '$NodeExe'
    NginxDir    = '$NginxDir'
    LogsDir     = '$MfqRoot\logs'
}
"@
$config | Out-File -FilePath "$PSScriptRoot\paths.ps1" -Encoding utf8 -Force

# ============================================================
# 完成
# ============================================================
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host "  安装完成!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "下一步:" -ForegroundColor Cyan
Write-Host "  1. 确认已配置 algorithm\.env 里的 LLM_API_KEY"
Write-Host "  2. 确认已配置 backend\.env 里的 SECRET_KEY(>=32字符) 和 ENVIRONMENT=production"
Write-Host "  3. 启动服务: .\start.ps1"
Write-Host "  4. 访问: http://115.159.212.98:3000"
Write-Host ""
Write-Host "安装内容:"
Write-Host "  Python: $(& $PythonExe --version)"
Write-Host "  Node:   $(& $NodeExe --version)"
Write-Host "  nginx:  $NginxDir"
Write-Host "  占用空间: $([math]::Round((Get-ChildItem $MfqRoot -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum / 1MB, 1)) MB"
Write-Host ""
