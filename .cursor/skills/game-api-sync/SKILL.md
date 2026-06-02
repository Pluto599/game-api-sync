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

1. **Agent 先在终端执行环境变量**（见 `references/env-setup.md`，每次调用 ECS 前必做，勿让用户手动）
2. 当前 Git 分支是开发者**有意工作的分支**（不切换分支、不开 PR）

## 指令

**每一步调用 ECS 前**，若尚未在本终端执行过环境变量，先运行 `references/env-setup.md` 中的三行 PowerShell。

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

用户说「根据当前代码变更，生成飞书文档更新草稿」时：

1. 先执行 `references/env-setup.md` 中的环境变量。
2. **必读** `references/doc-write-format.md`（完整版见仓库 `docs/feishu-doc-write-format.md`）。
3. 从代码 diff 生成 **DocxXML**（`h1`/`h2` + `pre lang="TypeScript"` + `caption` 客户端/服务端），**不要**贴 C#/C++ 源码。
4. 判定 `target`：`api_docs` 或 `type_constraints`。
5. `POST /jobs/api-doc-sync`，Body 含 `module`、`repo`、`summary`（必填）、`files_changed`。
6. 在回复中贴出完整 DocxXML 草稿与建议合并的 h1 位置；callout 仅作待审核标记。

### 禁止

- 本机 `lark-cli`、自动 PR、切换分支、写入 `Generated/`

## 参考资料

- `references/doc-write-format.md` — **代码→飞书** 写文档格式（必读）
- `references/env-setup.md` — Agent 自动执行的环境变量
- `references/ecs-api.md` — ECS API 与请求示例
- `references/workflows.md` — 五种入口与 JSON Body
