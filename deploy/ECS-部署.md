# ECS 部署（最简）

公网 IP：`120.27.249.20`  
仓库：`https://github.com/Pluto599/game-api-sync`（public，用 HTTPS，无需 SSH 密钥）

## 1. 克隆并安装

```bash
cd /tmp
rm -rf game-api-sync
git clone https://github.com/Pluto599/game-api-sync.git
bash /tmp/game-api-sync/deploy/install-to-ecs.sh /tmp/game-api-sync
```

## 2. 刷新文档快照（需已登录飞书用户）

```bash
lark-cli auth status --verify
pip3 install -q pyyaml
python3 /opt/api-sync/scripts/refresh_all_snapshots.py
```

若 auth 失败：

```bash
lark-cli auth login --recommend
```

## 3. 本机验证

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
curl -H "Authorization: Bearer $env:API_SYNC_TOKEN" "$env:API_SYNC_BASE/api/snapshot?module=战斗"
```
