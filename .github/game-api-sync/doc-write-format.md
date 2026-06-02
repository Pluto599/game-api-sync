# 代码 → 飞书文档格式（Copilot）

完整版：仓库根目录 `docs/feishu-doc-write-format.md`。

- **接口文档**：https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b — `h1` 请求 + `pre lang="TypeScript"`，`caption` 标客户端/服务端
- **类型约束**：https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde — `h1` 主题 + enum/struct 的 `pre`

写文档时只产出 **DocxXML 伪 TS 字段**；`api-doc-sync` 追加黄色 callout；负责人在飞书合并正文。
