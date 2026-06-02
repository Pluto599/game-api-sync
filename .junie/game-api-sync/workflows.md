# 五种入口（v2）

| 入口 | 触发 | ECS |
|------|------|-----|
| 刷新缓存 | IDE 主动 | `POST /jobs/refresh-cache` |
| 对比 | IDE 主动，只读 | `POST /jobs/api-compare` |
| 对齐代码 | IDE 主动 | `GET /api/snapshot` + 改现有文件 |
| PR Review | 开 PR 时 CI | `POST /jobs/api-review` |
| 写回文档 | IDE 主动 | `POST /jobs/api-doc-sync` |

## api-compare Body

```json
{
  "module": "战斗",
  "repo": "server",
  "files": { "include/battle.h": "<文件全文>" }
}
```

## api-doc-sync Body

```json
{
  "module": "战斗",
  "repo": "server",
  "target": "api_docs",
  "summary": "变更说明（必填）",
  "files_changed": ["src/battle_server.cpp"]
}
```

**写文档格式**：见 `doc-write-format.md`。产出 DocxXML 草稿并在对话中全文给出。

返回后飞书文档末尾会出现**黄色待审核 callout**，由负责人在飞书合并正文。
