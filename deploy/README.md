# AI 教学评价系统 — Windows 服务器部署脚本

## 服务器信息

- IP: 115.159.212.98
- 登录: mstsc 远程桌面,用户名 mfq,密码 Passworld@910
- 开放端口: 3000-3100
- 安装目录: C:\mfq(仅当前用户,不需要管理员)
- 容量限制: 20G

## 端口规划

| 服务 | 端口 | 对外 | 说明 |
|------|------|------|------|
| 前端(nginx) | 3000 | ✅ 对外 | 浏览器访问入口 |
| 后端 | 8000 | ❌ 仅本机 | nginx 内部代理 |
| 算法服务 | 8001 | ❌ 仅本机 | 后端内部调用 |

## 部署步骤

### 第一步:把项目代码传到服务器

通过 mstsc 远程桌面连入服务器后,把整个项目文件夹拷到 `C:\mfq\ai-teaching-evaluation-system`。

方法:远程桌面连接时勾选"本地资源 → 详细信息 → 驱动器",连入后在服务器"此电脑"里能看到你的本地磁盘,直接拷贝;或用 U 盘/网盘传。

最终项目应在这个路径:
```
C:\mfq\ai-teaching-evaluation-system\backend\
C:\mfq\ai-teaching-evaluation-system\algorithm\
C:\mfq\ai-teaching-evaluation-system\frontend\
```

### 第二步:配置 API Key

编辑 `C:\mfq\ai-teaching-evaluation-system\algorithm\.env`,填入 LLM API Key:
```
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-你的真实Key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
```

编辑 `C:\mfq\ai-teaching-evaluation-system\backend\.env`(如果没有就从 .env.example 复制),填入:
```
ENVIRONMENT=production
SECRET_KEY=随便打一段至少32位的随机字符
```

### 第三步:运行安装脚本

打开 PowerShell(开始菜单搜 PowerShell),执行:
```powershell
cd C:\mfq\ai-teaching-evaluation-system\deploy
Set-ExecutionPolicy Bypass -Scope Process -Force
.\install.ps1
```

脚本会自动下载安装 Python 3.11、Node.js 22、nginx 到 `C:\mfq` 下(约 5-10 分钟),装好所有依赖并构建前端。

### 第四步:启动服务

```powershell
cd C:\mfq\ai-teaching-evaluation-system\deploy
.\start.ps1
```

### 第五步:访问

浏览器打开:`http://115.159.212.98:3000`

默认管理员账号在 `backend/app/seed.py` 里(通常 admin / admin123)。

## 常用命令

```powershell
cd C:\mfq\ai-teaching-evaluation-system\deploy
.\start.ps1        # 启动三服务
.\stop.ps1         # 停止三服务
.\status.ps1       # 查看运行状态
```

## 日志位置

```
C:\mfq\logs\algorithm.log    # 算法服务日志
C:\mfq\logs\backend.log      # 后端日志
C:\mfq\logs\nginx\access.log # nginx 访问日志
C:\mfq\logs\nginx\error.log  # nginx 错误日志
```

## 故障排查

### 访问不了
1. 确认服务在跑:`.\status.ps1`
2. 看日志:`Get-Content C:\mfq\logs\nginx\error.log -Tail 20`
3. 确认防火墙:服务器安全组/防火墙放了 3000 端口(你说 3000-3100 已开放)

### 后端连不上算法服务
三个服务在同一台机器,后端用 `http://127.0.0.1:8001` 调算法服务(同机回环,不经过防火墙)。看后端日志:`Get-Content C:\mfq\logs\backend.log -Tail 30`

### LLM 调用 503
算法服务日志显示 `LLM_API_KEY 未配置`:检查 `algorithm\.env` 文件是否存在且 Key 正确。

### 导入种子数据
```powershell
cd C:\mfq\ai-teaching-evaluation-system\backend
C:\mfq\Python311\python.exe -m app.seed --reset
```

## 安装目录结构

```
C:\mfq\
├── Python311\              # Python 3.11(绿色版)
├── nodejs\                 # Node.js 22(绿色版)
├── nginx\                  # nginx(绿色版)
├── logs\                   # 所有服务日志
└── ai-teaching-evaluation-system\   # 项目代码
    ├── backend\
    ├── algorithm\
    ├── frontend\
    └── deploy\             # 本脚本所在目录
```
