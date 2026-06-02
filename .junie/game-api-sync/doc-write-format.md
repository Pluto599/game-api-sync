# 代码 → 飞书文档格式（Agent 必读）

完整版：`docs/feishu-doc-write-format.md` §3.1、§4.6。

## 模式 A

- **h2** 主题（非 h1 子主题）
- **禁止** docx_draft 含【合并位置】
- enum + type → **两个 pre**，无 caption
- **禁止** 实例行

ECS 插入 **h1 客户端/服务端** 分区末尾。

## 模式 B

可用 **h1** 主题。

## §4.3

协议消息同节多方向时才用 caption 区分 client/server。
