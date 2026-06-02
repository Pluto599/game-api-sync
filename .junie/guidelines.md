# game-api-sync（JetBrains Rider / Junie）

飞书 Wiki 为唯一权威源。文档快照由 ECS 提供；成员**不安装 lark-cli**。

协作 baseline 见 `.junie/game-api-sync/baseline.md`。详细 API 与五种入口见同目录下 `ecs-api.md`、`workflows.md`。

## 使用时机

- 对齐某模块代码到飞书文档
- 对比文档与当前实现（只读）
- 飞书改完文档后刷新 ECS 快照
- 把代码变更写成飞书待审核草稿
- 拉取模块 snapshot 或模块列表

## 前置条件

1. 已配置 `API_SYNC_BASE`、`API_SYNC_TOKEN`（见 `.junie/game-api-sync/ecs-api.md`）
2. 当前 Git 分支为开发者有意工作的分支（不切换、不开 PR）

## 指令

### 对齐代码到文档

1. 确认模块名
2. `GET {API_SYNC_BASE}/api/snapshot?module=<模块名>`，Header `Authorization: Bearer {API_SYNC_TOKEN}`
3. 读 `config/wiki-registry.yaml` 的 `client_glob` 或 `server_glob`
4. 只改**已有**协议文件；禁止 `Generated/`
5. 列出变更摘要；用户自行 commit

### 对比文档与实现（只读）

1. 读取 registry 对应源文件全文
2. `POST /jobs/api-compare`
3. 展示 `report_md` 与 `defects`；不改代码

### 刷新 ECS 缓存

`POST /jobs/refresh-cache`，Body 含 `module` 或空对象全量

### 同步文档草稿到飞书

`POST /jobs/api-doc-sync`，`summary` 必填

### 禁止

本机 `lark-cli`、自动 PR、切换分支、`Generated/`
