# Agent 环境变量（Rider / Junie，每次调用 ECS 前自动执行）

**禁止**要求用户手动设置。在 Rider **Terminal（PowerShell）** 中由 Agent **先执行**：

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }
```

随后用 `Invoke-RestMethod` 与 `$h` 访问 ECS（Windows）。Linux/macOS 终端可 export 同名变量后等价调用 HTTP。
