# game-api-sync（JetBrains Rider / Junie）

协议协作规范见 `.cursor/rules/api-protocol-baseline.mdc`（若已复制到本仓）。

## 核心约束

- 飞书 Wiki 为唯一权威源；`config/wiki-registry.yaml`
- `API_SYNC_BASE`、`API_SYNC_TOKEN` 访问 ECS；禁止本机 `lark-cli`
- 禁止 `Generated/`；只改已有源文件；不自动 PR

## 对齐代码

1. 确认当前分支
2. `GET {API_SYNC_BASE}/api/snapshot?module=<模块名>`，Header `Authorization: Bearer {API_SYNC_TOKEN}`
3. 按 registry glob 修改现有协议文件；用户自行 commit

触发语：根据最新飞书接口文档，对齐本仓库【战斗】模块的协议代码
