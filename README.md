# game-api-sync

飞书 Wiki 为权威接口文档。中央服务部署在 ECS，成员机**无需**安装 `lark-cli`。

仓库：[https://github.com/Pluto599/game-api-sync](https://github.com/Pluto599/game-api-sync)

## 仓库角色


| 仓库                      | 职责                                                             |
| ----------------------- | -------------------------------------------------------------- |
| **本仓（中央仓）**             | ECS API 服务、`scripts/` 对比/写回逻辑、飞书 `modules` 注册表、CI 可复用 Workflow |
| **client / server 游戏仓** | 协议源代码、`module_map` 路径配置、Agent 协作规则、合并后 CI 写回飞书草稿               |


中央仓目录概览：

```
api-server/          # FastAPI 服务（仅 ECS）
config/              # wiki-registry.yaml、message_aliases.yaml
scripts/             # 对比、写回、glob 门禁、CI 入口
deploy/              # ECS 安装脚本
.github/workflows/   # 可复用 CI + client/server 示例 workflow
.cursor/             # Cursor 规则与 Skill（复制到游戏仓）
.github/skills/      # Copilot Skill（复制到游戏仓）
tests/               # 中央仓单元测试
docs/                # 飞书写文档格式说明（可选阅读）
```

---

## 一、用法

### 1. 在 IDE 主动请求 ECS 刷新数据缓存

**场景**：飞书文档刚改完，或对齐/对比前需要**最新**快照；由 ECS 执行 `lark-cli` 拉取与解析，本机不装 `lark-cli`。默认会先比对飞书 `revision_id`，与缓存一致则**不**全量拉取；强制刷新 Body 加 `"force": true`。

**你怎么做**：

在 IDE 中说：

> 请刷新 ECS 上【战斗】模块的接口文档缓存

全量刷新可说：请刷新 ECS 全部模块的接口文档缓存

---

### 2. 在 IDE 主动对比文档与当前实现差异

**场景**：对齐或开 PR 前，先了解飞书文档与**当前分支**代码差在哪里；Agent 生成 **Markdown 对比文档**，并列出实现缺陷（若有）。

**你怎么做**：

1. 打开 client 或 server 仓库，切到当前工作分支。
2. Agent 先 `POST /jobs/refresh-cache`（**当前模块**；默认 **revision 比对**，飞书未改则跳过全量拉取；用户说「飞书刚改/强制刷新」时传 `"force":true`）。
3. 在 IDE 中说：
  > 对比【战斗】模块飞书文档与当前仓库实现的差异，生成对比报告并指出实现缺陷
4. Agent 执行：
  - `GET .../api/snapshot?module=战斗`；
  - 按 `config/wiki-registry.yaml` 读取本仓协议源文件；
  - `POST .../jobs/api-compare`（Body：`module`、`repo`、`files` 路径→文件全文）；返回 `report_md` 与 `defects`；
  - 输出：**对比报告**（按章节/方向/消息分组，字段名+类型级差异）+ **缺陷列表**。

---

### 3. 在 IDE 主动对齐代码

**场景**：有人在飞书更新了「战斗」等模块的接口说明；ECS 刷新该模块快照（定时或 webhook 触发）。

**你怎么做**（client / server **各自仓库、各自分支**，互不影响）：

1. `git checkout` 到你要提交的功能分支（例如 `feature/battle-v2`）。
2. 打开 **client** 或 **server** 仓库（一次只对一个仓）。
3. 在 Cursor / Copilot / Rider 中说：
  > 根据最新飞书接口文档，对齐本仓库【战斗】模块的协议代码
4. Agent 按 Skill / `.cursor/rules/` 或 `.github/copilot-instructions.md` 执行：
  - `GET $env:API_SYNC_BASE/api/snapshot?module=战斗` 取文档解析结果（AST/字段列表）；
  - 读本仓 `config/wiki-registry.yaml` 的 `client_glob` 或 `server_glob`，定位**已有** `.cs` / `.h` 等文件；
  - 就地改 struct / enum / 序列化逻辑，**不**创建 `Generated/`；
  - 输出变更摘要；由你自行 `git commit`（是否开 PR 由你决定）。

---

### 4. IDE 主动同步文档草稿到飞书

**场景**：你在当前分支改完协议代码，希望把变更写回飞书正文草稿（标题带 **agent生成，待审查**），由负责人审阅后合并。

**你怎么做**：

1. 在 **client** 或 **server** 当前分支完成代码修改。
2. 本机需有中央仓克隆（用于调用 `scripts/agent_doc_draft.py`）。
3. 在 IDE 中说：
  > 根据当前代码变更，生成飞书文档更新草稿
4. Agent 在游戏仓根目录运行：

```powershell
python <中央仓>/scripts/agent_doc_draft.py `
  --module 战斗 --repo client `
  --paths Assets/Scripts/Battle/Foo.cs `
  --apply-glob
```

- `--git-since origin/main` 可代替 `--paths` 自动取变更文件。
- `--apply-glob` 自动补齐 `wiki-registry.yaml` 中漏网路径；**须核对 git diff**。
- 输出 JSON 含 `drafts[].api_doc_sync_body`；Agent 再 `POST /jobs/api-doc-sync`（或加 `--sync`）。

ECS 写入飞书正文（模式 A 插入 **h1 客户端/服务端** 分区末尾）；负责人按 `docs/feishu-doc-write-format.md` 审阅。

---

### 5. PR 合并后自动同步飞书文档（GitHub Actions）

**场景**：协议 PR **合并到任意目标分支**后，由 CI 自动对比飞书快照与 PR 变更的协议代码；仅在**代码领先于文档**时，把变更写成飞书正文草稿（标题含 **CI生成，待审查**），供负责人审阅合并。PR 打开/更新阶段**不跑 Actions**；对比请在 IDE 主动发起。

**与用法 4 的区别**：


|      | 用法 4（IDE）                                      | 用法 5（CI）                |
| ---- | ---------------------------------------------- | ----------------------- |
| 触发   | 你在 IDE 里主动说「写回飞书草稿」                            | PR **合并**且变更命中协议路径      |
| 草稿标记 | agent生成，待审查                                    | CI生成，待审查                |
| 生成方式 | `agent_doc_draft.py` + `code_to_docx`（与 CI 同源） | `code_to_docx.py` 确定性生成 |


**你怎么做**：

1. 在功能分支改协议代码，开 PR（**CI 不再跑 compare、不出对比报告**；对比请在 IDE 主动发起）。
2. PR **合并**（目标分支任意）→ Actions 跑 **sync**：
  - 仅 PR 中变更且落在某模块 glob 内的协议文件才处理；
  - 漏网协议文件（orphan）会警告或失败（可配 `orphan_policy: fail`）；
  - 对比结果为 **code 领先** 时调用 `POST /jobs/api-doc-sync` 追加草稿；
  - **doc 领先**（飞书已更新）或 **无协议结构变更** 时跳过写回。
3. 在飞书搜索 **「CI生成，待审查」**，核对字段后合并进正式章节并去掉标记。

**CI 不会做的事**：不自动改代码、不自动改 `wiki-registry.yaml`、不覆盖已有正式文档段落（只 append 草稿）。`_status: draft` 的模块在 CI 中跳过写回。

实现细节见下文 [§六](#六github-actions-实现说明)。

---

## 二、同步到游戏仓库的文件

client / server 游戏仓**不需要** fork 或 submodule 整个中央仓。按需从中央仓拷贝下列文件，并在本仓维护 `module_map` 路径。

### 必拷 


| 路径（中央仓 → 游戏仓同路径）              | 用途               | 维护说明                                                                                                                             |
| ----------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `config/wiki-registry.yaml`   | 模块注册 + 协议路径 glob | `**modules`**（飞书 `obj_token`）须与中央仓 / ECS 一致；`**module_map**` 按本仓实际目录改 `client_glob` 或 `server_glob`（client 仓只维护前者，server 仓只维护后者） |
| `config/message_aliases.yaml` | 对比时中文章节名 ↔ 英文类型名 | 宜与中央仓同步；对比 API 的 `files` 须含此文件全文                                                                                                 |


### IDE / Agent 协作


| 路径                                        | 适用             |
| ----------------------------------------- | -------------- |
| `.cursor/rules/api-protocol-baseline.mdc` | Cursor         |
| `.cursor/skills/game-api-sync/`（整目录）      | Cursor         |
| `.github/copilot-instructions.md`         | GitHub Copilot |
| `.github/skills/game-api-sync/`（整目录）      | GitHub Copilot |


两套 Skill 内容同源，分别服务 Cursor 与 Copilot；复制后**无需**再改路径。

### CI 写回飞书（可选但推荐）


| 路径                                           | 说明                                                                                                                                                                                     |
| -------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.github/workflows/sync-feishu-api-docs.yml` | 从中央仓 [client 示例](.github/workflows/sync-feishu-api-docs.client.yml) 或 [server 示例](.github/workflows/sync-feishu-api-docs.server.yml) 复制到游戏仓并重命名；按需调整 `on.pull_request.paths` 以匹配本仓协议目录 |
| GitHub Secret `**API_SYNC_TOKEN`**           | Settings → Secrets → Actions；与 ECS 服务同一 Token                                                                                                                                          |


CI **不会**拷贝中央仓 `scripts/`：Workflow 合并时会 `checkout` `Pluto599/game-api-sync` 到 `_api-sync` 再执行 `scripts/ci/run_sync_job.py`。

### 开发机可选


| 路径                                    | 说明                                                                                       |
| ------------------------------------- | ---------------------------------------------------------------------------------------- |
| 中央仓克隆（任意目录）                           | 用法 4 调用 `agent_doc_draft.py`、`check_glob_for_align.py` 时需要 `<中央仓>` 路径                    |
| `deploy/vscode-settings.example.json` | 可选：在 VS Code / Cursor 终端注入 `API_SYNC_BASE` / `API_SYNC_TOKEN`（Agent 仍会按 Skill 自动 export） |


### 不要拷进游戏仓


| 路径                      | 原因                                                 |
| ----------------------- | -------------------------------------------------- |
| `api-server/`、`deploy/` | 仅 ECS 部署                                           |
| `scripts/`              | CI 运行时拉取；本地 IDE 通过中央仓路径调用                          |
| `tests/`                | 中央仓单元测试                                            |
| `docs/`                 | 非必须；格式要点已写在 Skill `references/doc-write-format.md` |


### 同步后必做检查

1. 打开 `config/wiki-registry.yaml`，按本仓目录修正 `**module_map`** 中的 glob（server 宜显式文件列表，勿含共享 `protocol.h` 全量）。
2. 为各模块填写 `_status`（`draft` / `candidate` / `verified`），路径未定优先用**显式路径列表**。
3. 飞书 Wiki 新增/调整模块时，从中央仓更新 `**modules`** 段并同步到 ECS（`modules` 与 glob 无关，三处宜一致）。
4. 配置 CI Secret 后，用一次协议 PR 合并验证 Actions sync 是否正常。

---

## 三、`config/wiki-registry.yaml` 与 glob

中央仓与 **client / server 游戏仓** 各有一份 `config/wiki-registry.yaml`。其中两类配置不要混用：


| 区块           | 作用                                                      | 谁维护                            |
| ------------ | ------------------------------------------------------- | ------------------------------ |
| `modules`    | 飞书叶子文档 `api_docs_obj` / `type_constraints_obj`（快照、写回草稿） | 与 Wiki 结构同步，中央仓 / ECS / 游戏仓宜一致 |
| `module_map` | 本仓协议**代码路径** `client_glob` / `server_glob`              | **各游戏仓**按实际目录维护                |


### glob 是什么

`client_glob` / `server_glob` 是路径**通配符或文件列表**，用来回答：「对比 / 对齐【战斗】等模块时，默认扫描哪些 `.cs` / `.h` 源文件？」

实现见 `scripts/registry_globs.py`（`collect_module_files`）。支持：

- **单个通配符字符串**：`Assets/Scripts/Protocol/Battle/**/*.cs`
- **YAML 数组（推荐，目录未定时）**：显式列出每个协议文件路径
- **单文件路径**：无 `*` 时按普通路径解析

在 **client** 仓只填/只读 `client_glob`；在 **server** 仓只填/只读 `server_glob`。

### 示例（`module_map`）

```yaml
module_map:
  战斗:
    _status: draft          # 可选：draft | candidate | verified
    _notes: "目录未定，先用显式列表"
    client_glob:
      - Assets/Scripts/Net/Protocol/Battle/EnterBattle.cs
      - Assets/Scripts/Net/Protocol/Battle/PlayerReady.cs
    server_glob:
      - src/protocol/battle/battle_packet.h
  联机大厅:
    client_glob: "Assets/Scripts/**/*Room*.{cs}"
    server_glob:
      - src/protocol/room/create_room.h
      - src/handlers/room_handler.cpp
```

项目未完成、路径不准时：**优先用显式路径列表**，不要用宽泛的 `*Battle*`（易扫到 UI、测试代码）。

### Agent 怎么用 glob（对比 / 对齐）

glob 是**默认范围**，不是唯一依据。Agent 须（详见 `.cursor/skills/game-api-sync/references/registry-globs.md` 或 `.github/skills/game-api-sync/references/registry-globs.md`）：

1. 读取本仓 `module_map.<模块>.client_glob` 或 `server_glob` 并解析命中文件；
2. **结合用户要求**（@ 文件、指定目录、排除项），优先级高于 glob；
3. glob 命中 0 个或过多时，**自行列目录 / 搜索**消息名后再合并范围；
4. 用户或 Agent 发现**不在 glob 中的协议文件**时，**更新**本仓 `wiki-registry.yaml`（同一变更内完成，勿只改代码不更新 registry）；
5. **对比**时把最终文件全文放进 `POST /jobs/api-compare` 的 `files`（须含 `config/message_aliases.yaml`）。

`_status: draft` 时：先列出将改动的文件清单，经确认后再改代码。

### 与 ECS 的关系

- **刷新快照 / 写回飞书**：只依赖 `modules.*_obj`，与 glob 无关。
- **api-compare**：`files` 须含协议源文件 + `**config/message_aliases.yaml`**（游戏仓 alias；CI/本地优先读 cwd 下该文件，ECS 从 body 嵌入读取）；支持 scoped、`target` 分流。
- ECS 上 `/opt/api-sync/config/wiki-registry.yaml` 的 `**modules**` 需与中央仓一致；`**module_map**` 以**各游戏仓**为准（ECS 不依赖游戏仓 glob）。

---

## 四、权威飞书文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

---

## 五、管理员：ECS 部署

公网：`120.27.249.20`  
仓库：`https://github.com/Pluto599/game-api-sync`

```bash
cd /tmp && rm -rf game-api-sync

# git clone 或 Workbench 上传后解压
git clone https://github.com/Pluto599/game-api-sync.git
# unzip -o game-api-sync.zip -d /tmp

bash /tmp/game-api-sync/deploy/install-to-ecs.sh /tmp/game-api-sync
lark-cli auth login --recommend
pip3 install -q pyyaml
python3 /opt/api-sync/scripts/refresh_all_snapshots.py
bash /tmp/game-api-sync/deploy/setup-cron.sh
```

若公网 `POST /jobs/` 只返回 `api-sync ok`：Nginx 里可能有 `return 200 'api-sync ok'` 占位，需改为反代 uvicorn：

```bash
sudo cp /tmp/game-api-sync/deploy/nginx-api-sync.conf /etc/nginx/sites-available/api-sync
sudo nginx -t && sudo systemctl reload nginx
```

验证：`curl -s http://127.0.0.1/openapi.json | head -c 80` 应看到 `openapi`，不是 `api-sync ok`。

**一次性配置（代码已就绪，部署后做）：**

- **飞书 webhook**（可选）：开放平台 → 事件订阅 → `http://120.27.249.20/webhook/feishu`；文档更新后自动刷新 ECS 快照（无群通知）。

`install-to-ecs.sh` 会同步到 ECS 的仅有：`config/wiki-registry.yaml`、`config/message_aliases.yaml`、`scripts/`、`api-server/main.py`——与游戏仓拷贝范围不同。

---

## 六、GitHub Actions 实现说明

用法见 [§一·5. PR 合并后自动同步飞书文档](#5-pr-合并后自动同步飞书文档github-actions)。

中央仓提供可复用 Workflow `[.github/workflows/api-doc-sync-reusable.yml](.github/workflows/api-doc-sync-reusable.yml)`；游戏仓 thin workflow 见 [client 示例](.github/workflows/sync-feishu-api-docs.client.yml) / [server 示例](.github/workflows/sync-feishu-api-docs.server.yml)。


| 阶段           | 行为                                                                                    |
| ------------ | ------------------------------------------------------------------------------------- |
| **PR 打开/更新** | 不触发 Actions（对比请在 IDE 主动发起）                                                            |
| **PR 合并**    | 路径门禁 → 仅 PR 变更的协议文件 → `classify_diff` 为 **code 领先** 时 `code_to_docx` + `api-doc-sync` |


脚本入口：`[scripts/ci/run_sync_job.py](scripts/ci/run_sync_job.py)`。CI 侧先用 **TTL（默认 6h）** 决定是否调用 refresh；ECS 收到 refresh 后还会做 `**revision_id` 比对**，未变则跳过全量拉取（响应 `skipped`）。IDE 默认每次对比/对齐前调用 refresh（同样 revision 比对；强制刷新传 `"force":true`）。

相关配置：`[config/message_aliases.yaml](config/message_aliases.yaml)`、`[docs/feishu-doc-write-format.md](docs/feishu-doc-write-format.md)` §4.3（pre 英文类型名）。