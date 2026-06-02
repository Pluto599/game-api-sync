# game-api-sync（JetBrains Rider / Junie）

飞书 Wiki 为唯一权威源。文档快照由 ECS 提供；成员**不安装 lark-cli**。

协作 baseline 见 `.junie/game-api-sync/baseline.md`。环境变量与 API 见 `env-setup.md`、`ecs-api.md`、`workflows.md`。glob 见 `registry-globs.md`。

## Agent：调用 ECS 前必须先执行（勿让用户手动）

在 Terminal（PowerShell）中**自动运行**（见 `.junie/game-api-sync/env-setup.md`）：

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }
```

## 使用时机

- 对齐某模块代码到飞书文档
- 对比文档与当前实现（只读）
- 飞书改完文档后刷新 ECS 快照
- 把代码变更写成飞书正文草稿（模式 A 用 h2，标题带「agent生成，待审查」）
- 拉取模块 snapshot 或模块列表

## 前置条件

1. Agent 已在本终端执行上述环境变量（非用户手动）
2. 当前 Git 分支为开发者有意工作的分支（不切换、不开 PR）

## 指令

### 对齐代码到文档

1. 确认模块名
2. `GET {API_SYNC_BASE}/api/snapshot?module=<模块名>`，Header `Authorization: Bearer {API_SYNC_TOKEN}`
3. 按 `registry-globs.md` 合并 glob、用户指定与目录排查；漏网文件更新 `wiki-registry.yaml`
4. 只改范围内**已有**协议文件；禁止 `Generated/`
5. 列出变更摘要；用户自行 commit

### 对比文档与实现（只读）

1. 同上确定 `files` 后 `POST /jobs/api-compare`
2. 展示 `report_md` 与 `defects`；不改代码

### 刷新 ECS 缓存

`POST /jobs/refresh-cache`，Body 含 `module` 或空对象全量

### 同步文档草稿到飞书

1. 先自动执行环境变量（见 `env-setup.md`）。
2. 必读 `doc-write-format.md`：模式 A → **h2 主题**、禁止 h1 子主题、禁止 caption 当分区、**禁止 docx_draft 含【合并位置】**；enum+type → **两个 pre（无 caption）**；禁止实例行。ECS 按 `repo` 插入 **h1 客户端/服务端** 分区末尾。
3. `POST /jobs/api-doc-sync`（`docx_draft` 与 `summary` 至少其一）；回复贴出 **docx_draft** 全文（不含【合并位置】）。

### 禁止

本机 `lark-cli`、自动 PR、切换分支、`Generated/`
