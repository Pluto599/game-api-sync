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
  "repo": "client",
  "files": { "Assets/Scripts/Battle/Foo.cs": "<文件全文>" }
}
```

## api-doc-sync Body

```json
{
  "module": "战斗",
  "repo": "client",
  "target": "api_docs",
  "summary": "变更说明（必填）",
  "files_changed": ["Assets/Scripts/Battle/Foo.cs"]
}
```

**写文档格式**：见 `doc-write-format.md`（或 `docs/feishu-doc-write-format.md`）。Agent 须产出 DocxXML 草稿（`h1` + `pre lang="TypeScript"`），并在对话中全文给出；`target` 为 `api_docs` 或 `type_constraints`。

返回后飞书文档末尾会出现**黄色待审核 callout**，由负责人在飞书合并正文。
