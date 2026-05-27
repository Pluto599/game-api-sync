# game-api-sync

飞书 Wiki 为权威接口文档。中央服务在 ECS，成员**无需安装 lark-cli**。

仓库：<https://github.com/Pluto599/game-api-sync>

---

## 成员：环境变量（一次性）

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
```

建议写入 PowerShell Profile 或 IDE 终端配置。

## 成员：验证连通

```powershell
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }
Invoke-RestMethod "$env:API_SYNC_BASE/health"
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot/modules"
```

应返回 `ok: True` 和 8 个模块。

## 成员：常用 API

```powershell
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }

Invoke-RestMethod "$env:API_SYNC_BASE/health"
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/wiki-nodes"
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot/modules"
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot?module=战斗"
```

PowerShell 中请用 `Invoke-RestMethod`，不要用 `curl -H`（会报错）。

## 成员：文档更新后对齐代码

1. 在 **client** 或 **server** 仓库切到你要提交的分支。
2. 确认本仓已安装 IDE 规则（见下节「复制到游戏仓库」）。
3. 在 IDE 中说：

   > 根据最新飞书接口文档，对齐本仓库【战斗】模块的协议代码

4. Agent 拉 ECS 快照，按 `config/wiki-registry.yaml` 的 glob 修改**现有**源文件。
5. 自行 review 后 `git commit` / 开 PR。

## 成员：禁止事项

| 禁止 | 原因 |
|------|------|
| 本机 `lark-cli` | 拉文档仅 ECS 负责 |
| 新建 `Generated/` | 就地改现有协议文件 |
| 依赖 Bot 自动 PR | v2 已取消 |

## 复制到游戏仓库（client / server）

**不要**把整个 `game-api-sync` 克隆进游戏仓。只把下列文件/目录复制到 **游戏仓库根目录**（与 `Assets/` 或 `src/` 同级）：

| 复制源（中央仓内路径） | 目标（游戏仓根目录） |
|------------------------|----------------------|
| `.cursor/skills/game-api-sync/` | `.cursor/skills/game-api-sync/` |
| `.github/copilot-instructions.md` | `.github/copilot-instructions.md` |
| `.junie/guidelines.md` | `.junie/guidelines.md` |
| `AGENTS.md` | `AGENTS.md` |
| `config/wiki-registry.yaml` | `config/wiki-registry.yaml` |

PowerShell 示例（先改两个变量）：

```powershell
$CentralRepo = "<你的路径>/game-api-sync"   # 本工具仓根目录
$GameRepo    = "<你的路径>/client"          # 或 server 仓库根目录

$items = @(
  @{ Src = ".cursor/skills/game-api-sync"; Dst = ".cursor/skills/game-api-sync" },
  @{ Src = ".github/copilot-instructions.md"; Dst = ".github/copilot-instructions.md" },
  @{ Src = ".junie/guidelines.md"; Dst = ".junie/guidelines.md" },
  @{ Src = "AGENTS.md"; Dst = "AGENTS.md" },
  @{ Src = "config/wiki-registry.yaml"; Dst = "config/wiki-registry.yaml" }
)
foreach ($i in $items) {
  $from = Join-Path $CentralRepo $i.Src
  $to = Join-Path $GameRepo $i.Dst
  if ($i.Src -match "skills") {
    New-Item -ItemType Directory -Force -Path (Split-Path $to) | Out-Null
    Copy-Item -Recurse -Force $from $to
  } else {
    New-Item -ItemType Directory -Force -Path (Split-Path $to) -ErrorAction SilentlyContinue | Out-Null
    Copy-Item -Force $from $to
  }
}
```

负责人需在**各游戏仓**的 `config/wiki-registry.yaml` 中把 `client_glob` / `server_glob` 改成真实路径后 commit。

### 各 IDE 读哪份文件

| IDE | 规则文件 |
|-----|----------|
| Cursor | `.cursor/skills/game-api-sync/SKILL.md` |
| VS Code（GitHub Copilot） | `.github/copilot-instructions.md` |
| JetBrains Rider（Junie / AI） | `.junie/guidelines.md` + 根目录 `AGENTS.md` |

## 权威飞书文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

## 常见问题

**`curl -H` 报错** → 用 `Invoke-RestMethod -Headers @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }`。

**模块名乱码** → 控制台编码问题；用 `$env:TEMP\*.json` 查看。

**404 snapshot** → 联系管理员在 ECS 执行 `python3 /opt/api-sync/scripts/refresh_all_snapshots.py`。

---

## 管理员：ECS 部署（最简）

公网：`120.27.249.20`  
仓库：`https://github.com/Pluto599/game-api-sync`（public，HTTPS 克隆）

```bash
cd /tmp && rm -rf game-api-sync
git clone https://github.com/Pluto599/game-api-sync.git
bash /tmp/game-api-sync/deploy/install-to-ecs.sh /tmp/game-api-sync
lark-cli auth login --recommend   # 若未登录
pip3 install -q pyyaml
python3 /opt/api-sync/scripts/refresh_all_snapshots.py
bash /tmp/game-api-sync/deploy/setup-cron.sh   # 每日 03:00 自动刷新
```

## 本仓库结构

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

`AGENTS.md` 为各 IDE 共用的简短协作规范；详细对齐流程见 Cursor Skill 与 Copilot/Junie 规则文件。
