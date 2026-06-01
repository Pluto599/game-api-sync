# game-api-sync（VS Code / GitHub Copilot）

本仓库若含 `.cursor/rules/` 与 `.cursor/skills/game-api-sync/`，协议协作规范以 Cursor 规则与 Skill 为准。

## 核心约束

- 飞书 Wiki 为唯一权威源；路径见 `config/wiki-registry.yaml`
- 用 `API_SYNC_BASE`、`API_SYNC_TOKEN` 访问 ECS；**禁止**本机 `lark-cli`
- **禁止**新建 `Generated/`；只改已有协议源文件
- 不自动开 PR、不切换分支

## 对齐代码

1. 确认当前 Git 分支
2. `Invoke-RestMethod -Headers @{ Authorization = "Bearer $env:API_SYNC_TOKEN" } "$env:API_SYNC_BASE/api/snapshot?module=<模块名>"`
3. 按 `wiki-registry.yaml` 的 `client_glob` / `server_glob` 修改现有文件
4. 用户自行 commit

触发语：根据最新飞书接口文档，对齐本仓库【战斗】模块的协议代码
