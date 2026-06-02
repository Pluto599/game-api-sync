# 代码 → 飞书文档格式（Agent 必读）

完整版：`docs/feishu-doc-write-format.md`（仓库根目录）。

## 写哪份文档

| 变更 | 目标 | `target` |
|------|------|----------|
| 请求/响应、消息字段 | [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b) 模块页 | `api_docs` |
| enum、通用 struct、Envelope | [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde) | `type_constraints` |

## 结构（与现网一致）

**接口文档**：`h1` = 请求/主题 → 可选 `h2` → `pre lang="TypeScript"`

**类型约束**：`h1` = 类型主题 → `pre`（struct/enum）

## 代码块模板

```xml
<pre lang="TypeScript" caption="客户端">
<code>MessageName: {
  fieldName: string;  // 中文说明
};</code>
</pre>
```

- `caption` 含 **客户端** / **服务端**（与代码仓一致）
- 仅伪 TS 字段行，禁止粘贴 C#/C++ 源码
- enum 整块一个 pre：`enum Name { A = 0, B = 1, }`

## Agent 流程

1. 读代码 diff + 可选 `GET /api/snapshot?module=…`
2. 生成 **DocxXML 草稿**（仅变更章节）
3. `POST /jobs/api-doc-sync`（`summary` + `files_changed`）
4. 在对话中**全文贴出** DocxXML，供负责人合并；ECS callout 为黄色待审核外壳

## 禁止

不直接改正文；不新建 `Generated/`；共享类型勿在接口页重复定义。
