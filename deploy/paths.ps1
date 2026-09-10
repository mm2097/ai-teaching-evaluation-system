# paths.ps1 — 安装路径配置(install.ps1 运行后会覆盖此文件)
# 如果用户没跑过 install.ps1,用默认值兜底
if (-not $paths) {
    $script:MfqRoot = "C:\mfq"
    $script:ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
    $script:paths = @{
        MfqRoot     = $script:MfqRoot
        ProjectRoot = $script:ProjectRoot
        PythonExe   = "$($script:MfqRoot)\Python311\python.exe"
        NodeExe     = "$($script:MfqRoot)\nodejs\node.exe"
        NginxDir    = "$($script:MfqRoot)\nginx"
        LogsDir     = "$($script:MfqRoot)\logs"
    }
}
