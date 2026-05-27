# game-api-sync（JetBrains Rider / Junie）

飞书 Wiki 为唯一权威源。用环境变量 `API_SYNC_BASE`、`API_SYNC_TOKEN` 访问 ECS 快照，**禁止**本机 `lark-cli`、**禁止**新建 `Generated/`、**禁止**自动开 PR。

## 对齐代码到文档

用户要求对齐某模块时：

1. 确认当前 Git 分支，不切换分支。
2. 拉取快照：`GET {API_SYNC_BASE}/api/snapshot?module=<模块名>`，Header：`Authorization: Bearer {API_SYNC_TOKEN}`
3. 读项目根目录 `config/wiki-registry.yaml` 的 `client_glob` 或 `server_glob`，只改已有协议源文件。
4. 对照快照就地修改；列出修改文件，由用户自行 commit。

## 触发语示例

根据最新飞书接口文档，对齐本仓库【战斗】模块的协议代码

同时遵守根目录 `AGENTS.md`。
