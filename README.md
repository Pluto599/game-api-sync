# game-api-sync

飞书 Wiki 为权威接口文档。中央服务在 ECS，无需安装 lark-cli。

仓库：<https://github.com/Pluto599/game-api-sync>

---

## 一、配置

### 1. 环境变量

在任意 PowerShell 窗口先执行（当前窗口立即生效）：

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
```

若希望**每次打开终端自动带上**，任选下面一种方式持久化。

#### 写入 PowerShell Profile（推荐，本机所有 PowerShell 终端生效）

1. 查看 Profile 路径：

```powershell
echo $PROFILE
```

2. 若文件不存在则创建，并追加两行（把路径换成上一步输出的路径）：

```powershell
if (!(Test-Path $PROFILE)) { New-Item -Path $PROFILE -ItemType File -Force }
notepad $PROFILE
```

在打开的记事本**末尾**加入：

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
```

保存后**新开一个** PowerShell 窗口，执行 `$env:API_SYNC_BASE` 应显示 URL。

#### 写入 IDE 终端配置（仅在该 IDE 打开项目时生效）

**Cursor / VS Code**

1. 打开游戏仓库或本仓根目录。
2. `Ctrl+Shift+P` → 输入 `Preferences: Open Workspace Settings (JSON)`（或用户设置 JSON）。
3. 在 `settings.json` 增加（路径按你机器修改）：

```json
"terminal.integrated.env.windows": {
  "API_SYNC_BASE": "http://120.27.249.20",
  "API_SYNC_TOKEN": "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
}
```

4. 关闭并重新打开集成终端。

**JetBrains Rider**

1. `Run` → `Edit Configurations` 可给运行配置加环境变量；若要对**终端**全局生效：
2. `Help` → `Edit Custom Properties` 不适用；更简单做法是在 Rider 内置 Terminal 启动前于 Profile 写入，或使用 `.env` 插件。
3. 推荐：在 Rider **Settings** → **Tools** → **Terminal** → **Environment variables** 中添加：

| 名称 | 值 |
|------|-----|
| `API_SYNC_BASE` | `http://120.27.249.20` |
| `API_SYNC_TOKEN` | `ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33` |

4. 新开 Terminal 标签页后生效。

---

### 2. 验证连通

在 **PowerShell** 中运行（不要用 cmd；`curl -H` 在 PowerShell 里会报错）：

```powershell
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }
Invoke-RestMethod "$env:API_SYNC_BASE/health"
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot/modules"
```

成功时：第一行 `ok` 为 `True`；第二行 `modules` 列出约 8 个模块名（控制台中文可能乱码，属显示问题，不影响 API）。

---

### 3. 复制 IDE 规则到游戏仓库（client / server）

**不要**把整个 `game-api-sync` 克隆进游戏仓。从中央仓复制下列路径到 **client 或 server 仓库根目录**（与 `Assets/`、`src/` 同级），保持相对路径不变：

- `.cursor/skills/game-api-sync/`
- `.github/copilot-instructions.md`
- `.junie/guidelines.md`
- `AGENTS.md`
- `config/wiki-registry.yaml`

负责人还需在**该游戏仓**的 `config/wiki-registry.yaml` 里，把各模块的 `client_glob` / `server_glob` 改成真实协议文件路径后 commit。

| IDE | 读取的规则文件 |
|-----|----------------|
| Cursor | `.cursor/skills/game-api-sync/SKILL.md` |
| VS Code（Copilot） | `.github/copilot-instructions.md` |
| Rider（Junie / AI） | `.junie/guidelines.md` 与根目录 `AGENTS.md` |

---

## 二、用法

### 1. 在 IDE 主动请求 ECS 刷新数据缓存

**场景**：飞书文档刚改完，或对齐/对比前需要**最新**快照；由 ECS 执行 `lark-cli` 拉取与解析，本机不装 `lark-cli`。

**你怎么做**：

1. 在 IDE 中说：

	> 请刷新 ECS 上【战斗】模块的接口文档缓存

	（全量刷新可说：请刷新 ECS 全部模块的接口文档缓存）

2. Agent 调用 ECS：

	- 单模块：`POST $env:API_SYNC_BASE/jobs/refresh-cache`，Body：`{ "module": "战斗" }`
	- 全量：同上，Body：`{}` 或省略 `module`

3. 等待返回 `ok: true` 后，再执行其他功能。

---

### 2. 在 IDE 主动对比文档与当前实现差异

**场景**：对齐或开 PR 前，先了解飞书文档与**当前分支**代码差在哪里；Agent 生成 **Markdown 对比文档**，并列出实现缺陷（若有）。

**你怎么做**：

1. 打开 client 或 server 仓库，切到当前工作分支。

2. 可选：先走功能 D 刷新该模块缓存。

3. 在 IDE 中说：

	> 对比【战斗】模块飞书文档与当前仓库实现的差异，生成对比报告并指出实现缺陷

4. Agent 执行：

	- `GET .../api/snapshot?module=战斗`；
	- 按 `config/wiki-registry.yaml` 读取本仓协议源文件；
	- `POST .../jobs/api-compare`（Body：`module`、`repo`、`files` 路径→文件全文）；返回 `report_md` 与 `defects`；
	- 输出：**对比报告**（字段/类型/命名差异表）+ **缺陷列表**（如缺少字段、类型错误等）。

5. **只读**：不修改代码、不开 PR。需要改代码时再走功能 A。

---

### 3. 在 IDE 主动对齐代码

**场景**：有人在飞书更新了「战斗」等模块的接口说明；ECS 刷新该模块快照（定时或后续由 webhook 触发）；群里 Bot 提醒「请在 IDE 对齐代码」（**不会**自动开 PR）。

**你怎么做**（client / server **各自仓库、各自分支**，互不影响）：

1. `git checkout` 到你要提交的功能分支（例如 `feature/battle-v2`）。
2. 打开 **client** 或 **server** 仓库（一次只对一个仓）。
3. 在 Cursor / Copilot / Rider 中说：

   > 根据最新飞书接口文档，对齐本仓库战斗模块代码

4. Agent 按 Skill / `AGENTS.md` 执行：
   - `GET $env:API_SYNC_BASE/api/snapshot?module=战斗` 取文档解析结果（AST/字段列表）；
   - 读本仓 `config/wiki-registry.yaml` 的 `client_glob` 或 `server_glob`，定位**已有** `.cs` / `.h` 等文件；
   - 就地改 struct / enum / 序列化逻辑，**不**创建 `Generated/`；
   - 输出变更摘要；由你自行 `git commit`（是否开 PR 由你决定）。
5. 另一端的同事在 **server**（或 client）仓库、**自己的分支**上重复同样流程。

**可选：手动拉快照核对**（PowerShell）：

```powershell
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot?module=战斗"
```

模块名须与 `GET .../api/snapshot/modules` 返回一致（配置阶段已验证连通）。

---

### 4. 自动 API Review

**场景**：你在 client 或 server 开 Pull Request；CI 把 PR 信息发给 ECS；ECS 对比**飞书最新快照**与 **PR 分支上的协议代码**，在 PR 下留言差异报告（缺字段、类型不一致等）。

**你怎么做**：

1. 照常开发、commit，向 GitHub 开 PR。
2. 等待 Actions 跑完，查看 PR 里的 **API Review** 评论。
3. 按评论改代码或先去飞书改文档，再 push；**Bot 不会改你的代码，也不会开 PR**。

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

ECS 在飞书文档末尾追加**黄色待审核 callout**；负责人在飞书审阅后合并进正文。

---

## 三、权威飞书文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

## 四、常见问题

1. **`curl -H` 报错** → 在 PowerShell 改用 `Invoke-RestMethod -Headers $h`。

2. **模块名乱码** → 控制台编码问题；用 `$env:TEMP\*.json` 查看。

3. **404 snapshot** → 联系管理员在 ECS 执行 `python3 /opt/api-sync/scripts/refresh_all_snapshots.py`。

4. ---

5. ## 五、管理员：ECS 部署


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

## 六、本仓库结构

```text
config/wiki-registry.yaml
scripts/parse_docx_xml.py
scripts/refresh_all_snapshots.py
api-server/main.py
deploy/install-to-ecs.sh
deploy/setup-cron.sh
.cursor/skills/game-api-sync/SKILL.md
.github/copilot-instructions.md
.junie/guidelines.md
AGENTS.md
```

`AGENTS.md` 为各 IDE 共用的简短协作规范；功能 A～E 以本节及对应 IDE 规则文件为准。
