# game-api-sync

飞书 Wiki 为权威接口文档。中央服务在 ECS，成员**无需安装 lark-cli**。

仓库：<https://github.com/Pluto599/game-api-sync>

## 环境变量（PowerShell，复制即用）

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
```

## 常用命令

PowerShell 里 `curl` 是别名，请用下面写法（或 `curl.exe -H ...`）：

```powershell
$h = @{ Authorization = "Bearer $env:API_SYNC_TOKEN" }

# 健康检查
Invoke-RestMethod "$env:API_SYNC_BASE/health"

# Wiki 子节点列表（每日 cron 刷新）
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/wiki-nodes"

# 模块文档快照（接口文档 + 类型约束解析结果）
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot?module=战斗"

# 列出已有快照的模块
Invoke-RestMethod -Headers $h "$env:API_SYNC_BASE/api/snapshot/modules"

# 在 ECS 上手动刷新全部模块快照（管理员 Workbench SSH 后执行）
# pip3 install -q pyyaml
# python3 /opt/api-sync/scripts/refresh_all_snapshots.py
```

## 权威文档

- [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)
- [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)

## IDE 对齐代码

1. 切到目标分支  
2. 在 Cursor 说：`根据最新飞书接口文档，对齐本仓库战斗模块的协议代码`  
3. Agent 先执行：`Invoke-RestMethod -Headers @{ Authorization = "Bearer $env:API_SYNC_TOKEN" } "$env:API_SYNC_BASE/api/snapshot?module=战斗"`  
4. 对照快照就地改代码，自行 commit  

## 仓库结构

```text
config/wiki-registry.yaml
scripts/parse_docx_xml.py
scripts/refresh-all-snapshots.sh
api-server/main.py
deploy/install-to-ecs.sh
```

详见 [AGENTS.md](AGENTS.md)、[成员接入说明](docs/成员接入.md)。

## IDE Skill

复制 `.cursor/skills/game-api-sync` 到 client/server 仓库的 `.cursor/skills/`，见 [deploy/ECS-第三步.md](deploy/ECS-第三步.md)。
