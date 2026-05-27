# game-api-sync

飞书 Wiki 为权威接口文档。中央服务在 ECS，成员**无需安装 lark-cli**。

仓库：<https://github.com/Pluto599/game-api-sync>

---

## 一、配置（一次性完成）

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

PowerShell 示例（先改两个变量）：

```powershell
$CentralRepo = "<你的路径>/game-api-sync"
$GameRepo    = "<你的路径>/client"   # 或 server

$items = @(
  ".cursor/skills/game-api-sync",
  ".github/copilot-instructions.md",
  ".junie/guidelines.md",
  "AGENTS.md",
  "config/wiki-registry.yaml"
)
foreach ($rel in $items) {
  $from = Join-Path $CentralRepo $rel
  $to = Join-Path $GameRepo $rel
  if ($rel -match "skills") {
    New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
    Copy-Item -Recurse -Force $from $to
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path $to) -ErrorAction SilentlyContinue | Out-Null
    Copy-Item -Force $from $to
  }
  Write-Host "OK $rel"
}
```

负责人还需在**该游戏仓**的 `config/wiki-registry.yaml` 里，把各模块的 `client_glob` / `server_glob` 改成真实协议文件路径后 commit。

| IDE | 读取的规则文件 |
|-----|----------------|
| Cursor | `.cursor/skills/game-api-sync/SKILL.md` |
| VS Code（Copilot） | `.github/copilot-instructions.md` |
| Rider（Junie / AI） | `.junie/guidelines.md` 与根目录 `AGENTS.md` |

---

## 二、配置完成后：三种用法

下面三项是 ECS 中央服务提供的 HTTP 接口（统称「API」= 用 URL 访问的能力，不是要你写代码注册接口）。在 PowerShell 里用 `Invoke-RestMethod` 调用即可；IDE 里的 Agent 也会用同一地址拉数据。

需鉴权的请求都要带请求头：`Authorization: Bearer <API_SYNC_TOKEN>`。下面示例统一先设：

```powershell
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }
```

---

### 功能一：检查服务是否正常

**做什么**：确认 ECS 上的同步服务在线。  
**何时用**：环境变量刚配好、或怀疑连不上时。  
**怎么做**：

```powershell
Invoke-RestMethod "$env:API_SYNC_BASE/health"
```

返回 `ok : True` 即正常。此接口**不需要** Token。

---

### 功能二：查看已有文档快照的模块列表

**做什么**：看中央服务已经为哪些游戏模块生成了「飞书文档解析结果」缓存（如战斗、地图等）。  
**何时用**：对齐代码前确认模块名拼写；或 404 时检查是否尚未刷新快照。  
**怎么做**：

```powershell
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot/modules"
```

返回里的 `modules` 数组即为可用模块名；对齐代码时 `module=` 必须与这里一致。

**可选**：查看 Wiki 节点缓存文件列表（一般由管理员维护，开发较少用）：

```powershell
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/wiki-nodes"
```

---

### 功能三：拉取某模块文档快照，并在 IDE 中对齐代码

**做什么**：获取指定模块的接口文档 + 类型约束解析结果（JSON），供你对照修改**现有**协议源文件。  
**何时用**：飞书文档已更新，要在当前分支把 client/server 代码改到与文档一致。  
**怎么做**：

**3a. 手动查看快照（可选）**

```powershell
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot?module=战斗"
```

将输出存文件便于阅读：

```powershell
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot?module=战斗" |
  ConvertTo-Json -Depth 20 |
  Out-File -Encoding utf8 "$env:TEMP\snapshot-战斗.json"
```

**3b. 在 IDE 中让 Agent 对齐（推荐）**

1. 打开 **client** 或 **server** 仓库，切到你要提交的分支。  
2. 确认已完成「一、配置」中的规则复制与 `wiki-registry.yaml` 路径。  
3. 在 Cursor / Copilot / Rider 中说：

   > 根据最新飞书接口文档，对齐本仓库【战斗】模块的协议代码

4. Agent 会请求同一快照 URL，按 `config/wiki-registry.yaml` 的 glob 修改已有文件（**不**新建 `Generated/`）。  
5. 你 review 后自行 `git commit` / 开 PR。

**禁止**：本机运行 `lark-cli`；依赖 Bot 自动开 PR。

---

## 三、权威飞书文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

## 四、常见问题

**`curl -H` 报错** → 在 PowerShell 改用 `Invoke-RestMethod -Headers $h`。

**模块名乱码** → 控制台编码问题；用 `$env:TEMP\*.json` 查看。

**404 snapshot** → 联系管理员在 ECS 执行 `python3 /opt/api-sync/scripts/refresh_all_snapshots.py`。

---

## 五、管理员：ECS 部署

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

`AGENTS.md` 为各 IDE 共用的简短协作规范；详细对齐流程见各 IDE 规则文件。
