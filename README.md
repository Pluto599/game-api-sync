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
2. 可选：先走功能 D 刷新该模块缓存。
3. 在 IDE 中说：
  对比【战斗】模块飞书文档与当前仓库实现的差异，生成对比报告并指出实现缺陷
4. Agent 执行：
  `GET .../api/snapshot?module=战斗`；  
   按 `config/wiki-registry.yaml` 读取本仓协议源文件；  
   `POST .../jobs/api-compare`（Body：`module`、`repo`、`files` 路径→文件全文）；返回 `report_md` 与 `defects`；  
   输出：**对比报告**（字段/类型/命名差异表）+ **缺陷列表**（如缺少字段、类型错误等）。

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

### 4. 自动 API Review

**场景**：你在 client 或 server 开 Pull Request；CI 把 PR 信息发给 ECS；ECS 对比**飞书最新快照**与 **PR 分支上的协议代码**，在 PR 下留言差异报告（缺字段、类型不一致等）。

**你怎么做**：

1. 照常开发、commit，向 GitHub 开 PR。
2. 等待 Actions 跑完，查看 PR 里的 **API Review** 评论。
3. 按评论改代码或先去飞书改文档，再 push。

---

### 5. IDE 主动同步文档草稿到飞书

**场景**：你在当前分支改完协议代码，希望把变更写回飞书，但不直接改正文，而是生成**待审核**草稿。

**你怎么做**：

1. 在 **client** 或 **server** 当前分支完成代码修改。
2. 在 IDE 中说：
  > 根据当前代码变更，生成飞书文档更新草稿
3. Agent 调用 ECS：`POST /jobs/api-doc-sync`，Body 示例：

```json
{
  "module": "战斗",
  "repo": "client",
  "summary": "变更说明（必填）",
  "files_changed": ["Assets/Scripts/Battle/Foo.cs"]
}
```

ECS 在飞书文档末尾追加**黄色待审核 callout**；负责人按 `docs/feishu-doc-write-format.md` 将 DocxXML 合并进正文。

---

## 二、权威飞书文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

## 三、管理员：ECS 部署

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

**一次性配置（代码已就绪，部署后做）：**

- **飞书 webhook**：开放平台 → 事件订阅 → `http://120.27.249.20/webhook/feishu`；可选环境变量 `FEISHU_NOTIFY_CHAT_ID`（群 chat_id）用于文档更新通知。
- **PR Review**：将 `deploy/api-review.yml` 复制到 client/server 的 `.github/workflows/`，仓库 Secret 添加 `API_SYNC_TOKEN`。

## 四、本仓库结构

```text
.cursor/rules/api-protocol-baseline.mdc
.cursor/skills/game-api-sync/SKILL.md
.cursor/skills/game-api-sync/references/
.github/copilot-instructions.md
.github/game-api-sync/
.junie/guidelines.md
.junie/game-api-sync/
config/wiki-registry.yaml
```

三套 IDE 配置内容对齐：Cursor 用 **Rules + Skills**；VS Code 用 **copilot-instructions + game-api-sync/**；Rider 用 **guidelines + game-api-sync/**。