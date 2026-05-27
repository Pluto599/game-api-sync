# 第 2 步：部署到 ECS 并生成快照

在 ECS Workbench 终端依次执行。

## 1. 上传代码到 ECS

在本机 PowerShell（将 `game-api-sync` 打成 zip 或用 scp）。若无 scp，可在 ECS 上 `git clone` 你的 GitHub 仓库。

**简易方式 — 本机用 scp（若已配置 SSH）：**

```powershell
cd E:\Desktop
scp -r game-api-sync root@120.27.249.20:/tmp/
```

若无法用 scp：把 `E:\Desktop\game-api-sync` 压缩为 zip，通过阿里云 Workbench「文件」页上传到 `/tmp/`，再：

```bash
cd /tmp && unzip -o game-api-sync.zip -d /tmp/game-api-sync
```

## 2. 安装到 /opt/api-sync

```bash
bash /tmp/game-api-sync/deploy/install-to-ecs.sh /tmp/game-api-sync
```

## 3. 刷新全部模块快照（需已 lark-cli auth login）

```bash
pip3 install -q pyyaml
python3 /opt/api-sync/scripts/refresh_all_snapshots.py
```

约 1～2 分钟，应看到 8 行 `OK 模块名 -> ...`。

## 4. 本机验证

```powershell
$env:API_SYNC_BASE = "http://120.27.249.20"
$env:API_SYNC_TOKEN = "ed7484c01552b1d3c271870a4c128bc7e1c0e5b92c732d33"
curl -H "Authorization: Bearer $env:API_SYNC_TOKEN" "$env:API_SYNC_BASE/api/snapshot/modules"
curl -H "Authorization: Bearer $env:API_SYNC_TOKEN" "$env:API_SYNC_BASE/api/snapshot?module=战斗"
```

返回 JSON 且含 `api_docs` / `type_constraints` 即成功。
