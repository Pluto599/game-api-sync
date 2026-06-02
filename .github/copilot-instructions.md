# game-api-sync（VS Code / GitHub Copilot）

飞书 Wiki 为唯一权威源。文档快照由 ECS 提供；成员**不安装 lark-cli**。

协作 baseline 见 `.github/game-api-sync/baseline.md`。环境变量与 API 见 `env-setup.md`、`ecs-api.md`、`workflows.md`。

## Agent：调用 ECS 前必须先执行（勿让用户手动）

在 PowerShell 终端**自动运行**（见 `.github/game-api-sync/env-setup.md`）：

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }
```

## 使用时机

- 对齐某模块代码到飞书文档
- 对比文档与当前实现（只读）
- 飞书改完文档后刷新 ECS 快照
- 把代码变更写成飞书待审核草稿
- 拉取模块 snapshot 或模块列表

## 前置条件

1. Agent 已在本终端执行上述环境变量（非用户手动）
2. 当前 Git 分支为开发者有意工作的分支（不切换、不开 PR）

## 指令

### 对齐代码到文档

1. 确认模块名；必要时 `GET /api/snapshot/modules`
2. `GET /api/snapshot?module=<模块名>`
3. 读 `config/wiki-registry.yaml` 的 `client_glob` 或 `server_glob`
4. 只改**已有**协议文件；禁止 `Generated/`
5. 列出变更摘要；用户自行 commit

### 对比文档与实现（只读）

1. 读取 registry 对应源文件全文
2. `POST /jobs/api-compare`（`module`、`repo`、`files`）
3. 展示 `report_md` 与 `defects`；不改代码

### 刷新 ECS 缓存

`POST /jobs/refresh-cache`，Body：`{"module":"<模块名>"}` 或 `{}`

### 同步文档草稿到飞书

`POST /jobs/api-doc-sync`，Body：`module`、`repo`、`summary`（必填）、`files_changed`

### 禁止

本机 `lark-cli`、自动 PR、切换分支、`Generated/`
