---
name: game-api-sync
description: >-
  飞书权威接口文档与 ECS 快照：刷新缓存、对比文档与代码差异、对齐协议代码、写回飞书 callout 草稿。
  在 client/server 仓库处理协议对齐、api-sync、wiki-registry 或用户提到飞书接口文档时使用。
---

# game-api-sync

飞书 Wiki 为唯一权威源。文档快照由 ECS 提供；成员**不安装 lark-cli**。

## 使用时机

- 用户要对齐某模块代码到飞书文档
- 用户要对比文档与当前实现（只读报告）
- 飞书刚改完文档，需要刷新 ECS 快照后再对齐
- 用户要把代码变更写成飞书待审核草稿
- 需要列出 ECS 已有快照模块或拉取某模块 snapshot

## 前置条件

1. 环境变量 `API_SYNC_BASE`、`API_SYNC_TOKEN` 已配置（见 `references/ecs-api.md`）
2. 当前 Git 分支是开发者**有意工作的分支**（不切换分支、不开 PR）

## 指令

### 对齐代码到文档

1. 确认模块名；必要时 `GET /api/snapshot/modules`
2. `GET /api/snapshot?module=<模块名>` 取快照
3. 读 `config/wiki-registry.yaml` 中本仓 `client_glob` 或 `server_glob`
4. 只改**已有**协议源文件；**禁止** `Generated/`
5. 列出变更摘要；由用户自行 commit

### 对比文档与实现（只读）

1. 读取 registry 对应源文件
2. `POST /jobs/api-compare`（Body：`module`、`repo`、`files` 路径→全文）
3. 展示 `report_md` 与 `defects`；**不改代码**

### 刷新 ECS 缓存

`POST /jobs/refresh-cache`，Body：`{"module":"<模块名>"}` 或 `{}` 全量

### 同步文档草稿到飞书

`POST /jobs/api-doc-sync`，Body：`module`、`repo`、`summary`（必填）、`files_changed`

### 禁止

- 本机 `lark-cli`、自动 PR、切换分支、写入 `Generated/`

## 参考资料

- `references/ecs-api.md` — ECS API 与 PowerShell
- `references/workflows.md` — 五种入口与 JSON Body
