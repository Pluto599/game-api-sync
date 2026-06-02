# game-api-sync

飞书 Wiki 为权威接口文档。中央服务在 ECS，无需安装 lark-cli。

仓库：[https://github.com/Pluto599/game-api-sync](https://github.com/Pluto599/game-api-sync)

---

## 一、用法

### 1. 在 IDE 主动请求 ECS 刷新数据缓存

**场景**：飞书文档刚改完，或对齐/对比前需要**最新**快照；由 ECS 执行 `lark-cli` 拉取与解析，本机不装 `lark-cli`。

**你怎么做**：

1. 在 IDE 中说：
  请刷新 ECS 上【战斗】模块的接口文档缓存  
    全量刷新可说：请刷新 ECS 全部模块的接口文档缓存）

---

### 2. 在 IDE 主动对比文档与当前实现差异

**场景**：对齐或开 PR 前，先了解飞书文档与**当前分支**代码差在哪里；Agent 生成 **Markdown 对比文档**，并列出实现缺陷（若有）。

**你怎么做**：

1. 打开 client 或 server 仓库，切到当前工作分支。
2. 可选：先刷新该模块 ECS 缓存。
3. 在 IDE 中说：
  对比【战斗】模块飞书文档与当前仓库实现的差异，生成对比报告并指出实现缺陷
4. Agent 执行：
  `GET .../api/snapshot?module=战斗`；  
   按 `config/wiki-registry.yaml` 读取本仓协议源文件；  
   `POST .../jobs/api-compare`（Body：`module`、`repo`、`files` 路径→文件全文）；返回 `report_md` 与 `defects`；  
   输出：**对比报告**（按章节/方向/消息分组，字段名+类型级差异）+ **缺陷列表**。

---

### 3. 在 IDE 主动对齐代码

**场景**：有人在飞书更新了「战斗」等模块的接口说明；ECS 刷新该模块快照（定时或后续由 webhook 触发）。

**你怎么做**（client / server **各自仓库、各自分支**，互不影响）：

1. `git checkout` 到你要提交的功能分支（例如 `feature/battle-v2`）。
2. 打开 **client** 或 **server** 仓库（一次只对一个仓）。
3. 在 Cursor / Copilot / Rider 中说：
  > 根据最新飞书接口文档，对齐本仓库战斗模块代码
4. Agent 按 Skill / `.cursor/rules/` 执行：
  - `GET $env:API_SYNC_BASE/api/snapshot?module=战斗` 取文档解析结果（AST/字段列表）；
  - 读本仓 `config/wiki-registry.yaml` 的 `client_glob` 或 `server_glob`，定位**已有** `.cs` / `.h` 等文件；
  - 就地改 struct / enum / 序列化逻辑，**不**创建 `Generated/`；
  - 输出变更摘要；由你自行 `git commit`（是否开 PR 由你决定）。

---

### 4. IDE 主动同步文档草稿到飞书

**场景**：你在当前分支改完协议代码，希望把变更写回飞书正文草稿（标题带 **agent生成，待审查**），由负责人审阅后合并。

**你怎么做**：

1. 在 **client** 或 **server** 当前分支完成代码修改。
2. 在 IDE 中说：
  > 根据当前代码变更，生成飞书文档更新草稿
3. Agent 调用 ECS：`POST /jobs/api-doc-sync`，Body 示例：

```json
{
  "module": "战斗",
  "repo": "client",
  "summary": "变更说明",
  "files_changed": ["Assets/Scripts/Battle/Foo.cs"],
  "docx_draft": "<h1>进入战斗（agent生成，待审查）</h1><pre>...</pre>"
}
```

ECS 写入飞书正文（模式 A 插入 **h1 客户端/服务端** 分区末尾；否则 append 文末）；自动剔除【合并位置】段。负责人按 `docs/feishu-doc-write-format.md` 审阅。

---

## 二、`config/wiki-registry.yaml` 与 glob

中央仓与 **client / server 游戏仓** 各有一份 `config/wiki-registry.yaml`。其中两类配置不要混用：

| 区块 | 作用 | 谁维护 |
|------|------|--------|
| `modules` | 飞书叶子文档 `api_docs_obj` / `type_constraints_obj`（快照、写回草稿） | 与 Wiki 结构同步，三处宜一致 |
| `module_map` | 本仓协议**代码路径** `client_glob` / `server_glob` | **各游戏仓**按实际目录维护 |

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
    server_glob: "**/*room*/**/*.{h,hpp,cpp}"
```

项目未完成、路径不准时：**优先用显式路径列表**，不要用宽泛的 `*Battle*`（易扫到 UI、测试代码）。

### Agent 怎么用 glob（对比 / 对齐）

glob 是**默认范围**，不是唯一依据。Agent 须（详见 `.cursor/skills/game-api-sync/references/registry-globs.md`）：

1. 读取本仓 `module_map.<模块>.client_glob` 或 `server_glob` 并解析命中文件；
2. **结合用户要求**（@ 文件、指定目录、排除项），优先级高于 glob；
3. glob 命中 0 个或过多时，**自行列目录 / 搜索**消息名后再合并范围；
4. 用户或 Agent 发现**不在 glob 中的协议文件**时，**更新**本仓 `wiki-registry.yaml`（同一变更内完成，勿只改代码不更新 registry）；
5. **对比**时把最终文件全文放进 `POST /jobs/api-compare` 的 `files`（可不只靠 glob 自动收集）。

`_status: draft` 时：先列出将改动的文件清单，经确认后再改代码。

### 与 ECS 的关系

- **刷新快照 / 写回飞书**：只依赖 `modules.*_obj`，与 glob 无关。
- **api-compare**：由 Agent 组 `files`；glob 指引 Agent 读哪些文件，CI 不再自动跑 PR Review。
- ECS 上 `/opt/api-sync/config/wiki-registry.yaml` 的 `modules` 需与游戏仓一致；`module_map` 以**各游戏仓**为准。

### 复制到 client/server 时

从中央仓拷贝 `config/wiki-registry.yaml` 后，**务必**按本仓目录改好 `client_glob` / `server_glob`，并保留/填写 `_status`。不必复制中央仓整份 `docs/`，但建议同步 `.cursor/skills/game-api-sync/references/registry-globs.md`（或 Copilot/Junie 下的 `registry-globs.md`）。

---

## 三、权威飞书文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

## 四、管理员：ECS 部署

公网：`120.27.249.20`  
仓库：`https://github.com/Pluto599/game-api-sync`

```bash
cd /tmp && rm -rf game-api-sync
git clone https://github.com/Pluto599/game-api-sync.git
bash /tmp/game-api-sync/deploy/install-to-ecs.sh /tmp/game-api-sync
lark-cli auth login --recommend
pip3 install -q pyyaml
python3 /opt/api-sync/scripts/refresh_all_snapshots.py
bash /tmp/game-api-sync/deploy/setup-cron.sh
```

**若公网 `POST /jobs/*` 只返回 `api-sync ok`：** Nginx 里可能有 `return 200 'api-sync ok'` 占位，需改为反代 uvicorn：

```bash
sudo cp /tmp/game-api-sync/deploy/nginx-api-sync.conf /etc/nginx/sites-available/api-sync
sudo nginx -t && sudo systemctl reload nginx
```

验证：`curl -s http://127.0.0.1/openapi.json | head -c 80` 应看到 `openapi`，不是 `api-sync ok`。

**一次性配置（代码已就绪，部署后做）：**

- **飞书 webhook**（可选）：开放平台 → 事件订阅 → `http://120.27.249.20/webhook/feishu`；文档更新后自动刷新 ECS 快照（无群通知）。

## 五、本仓库结构

```text
.cursor/rules/api-protocol-baseline.mdc
.cursor/skills/game-api-sync/SKILL.md
.cursor/skills/game-api-sync/references/（含 registry-globs.md：glob + 用户路径 + 更新 registry）
.github/copilot-instructions.md
.github/game-api-sync/
.junie/guidelines.md
.junie/game-api-sync/
config/wiki-registry.yaml
scripts/（diff_api、extract_code；单测见 tests/）
```

三套 IDE 配置内容对齐：Cursor 用 **Rules + Skills**；VS Code 用 **copilot-instructions + game-api-sync/**；Rider 用 **guidelines + game-api-sync/**。