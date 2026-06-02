# 四种入口（v2）

| 入口 | 触发 | ECS |
|------|------|-----|
| 刷新缓存 | IDE 主动 | `POST /jobs/refresh-cache` |
| 对比 | IDE 主动，只读 | `POST /jobs/api-compare` |
| 对齐代码 | IDE 主动 | `GET /api/snapshot` + 改现有文件 |
| 写回文档 | IDE 主动 | `POST /jobs/api-doc-sync` |

详见中央仓 `.cursor/skills/game-api-sync/references/workflows.md`。
