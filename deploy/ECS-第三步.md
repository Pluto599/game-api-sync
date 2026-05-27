# 第 3 步：定时刷新快照 + 成员 Skill（本步在 ECS 执行 cron）

## A. 本机（已完成）

- `.cursor/skills/game-api-sync/SKILL.md` — IDE 对齐工作流
- `docs/成员接入.md` — 成员说明
- 将上述内容 `git push` 后，client/server 负责人按 `docs/成员接入.md` 复制 Skill

## B. ECS — 安装每日 03:00 自动刷新（请你在 Workbench 执行）

先拉最新代码（若已 push）：

```bash
cd /tmp
rm -rf game-api-sync
git clone https://github.com/Pluto599/game-api-sync.git
bash /tmp/game-api-sync/deploy/install-to-ecs.sh /tmp/game-api-sync
bash /tmp/game-api-sync/deploy/setup-cron.sh
```

验证 cron：

```bash
crontab -l | grep game-api-sync
```

手动试跑一次（可选）：

```bash
/opt/api-sync/scripts/refresh-all-snapshots.sh
tail -20 /opt/api-sync/logs/refresh.log
```

## C. 验收

- `crontab -l` 含 `0 3 * * * ... refresh-all-snapshots.sh`
- 手动脚本执行后 `/opt/api-sync/cache/snapshots/*.json` 时间戳更新

完成后回复「第 3 步完成」，再进行第 4 步（client/server 复制 Skill 或 webhook，按 plan 顺序）。
