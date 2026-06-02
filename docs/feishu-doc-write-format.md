# 代码 → 飞书文档：Agent 写文档格式规范

> 权威源对照：
> - [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)（`api_docs`，按模块叶子页）
> - [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)（`type_constraints`，共享类型/枚举）

与 `scripts/parse_docx_xml.py` 解析规则一致；Agent 产出须能被同一解析器读回。

---

## 1. 写哪一份文档

| 代码变更类型 | 目标文档 | `wiki-registry` 字段 | 示例模块 |
|--------------|----------|----------------------|----------|
| 请求/响应消息、接口字段、协议号说明 | **接口文档** 对应模块叶子页 | `api_docs_obj` | 战斗、地图、联机大厅 |
| 跨模块 struct、enum、网络 Envelope、通用类型 | **类型约束** 对应章节 | `type_constraints_obj` | 网络相关、玩家存档、战斗（类型节） |

- 仅改 client C# 消息类 → 优先写 **接口文档** 中 **客户端** 代码块。
- 仅改 server C++/头文件协议 → 优先写 **接口文档** 中 **服务端** 代码块。
- 改 enum / 通用 DTO / 网络包封装 → 写 **类型约束**（勿拆散到各模块接口页，除非该类型仅单模块使用）。

`POST /jobs/api-doc-sync` 的 `target` 字段：

- `"api_docs"`（默认）— 接口文档叶子
- `"type_constraints"` — 类型约束叶子

---

## 2. 交付方式（两阶段）

### 阶段 A：待审核草稿（当前 ECS 默认）

Agent **不直接改正文**。通过 `api-doc-sync` 在文档**末尾**追加黄色 callout（`doc_sync.py` 已生成外壳）。callout **内部**须包含按下面第 3～5 节编写的 **DocxXML 片段**（或等价的结构化变更说明 + XML），供负责人复制进正文。

callout 外壳固定语义（勿改）：

- emoji `📝`，`background-color="light-yellow"`
- 标题：**【待审核】代码 → 文档同步草稿**
- 文末提示：审阅后合并进正文并删除 callout

### 阶段 B：负责人合并进正文

负责人根据 callout 内 XML：

1. 用 `docs +fetch --detail with-ids` 定位对应 `h1`/`h2`/`pre` 块；
2. `str_replace` / `block_replace` / `block_insert_after` 合并（见 lark-cli `docs +update`）；
3. 删除 callout。

Agent 在阶段 A 应**同时**给出：建议修改的章节名、完整 DocxXML 草稿、变更摘要。

---

## 3. 文档层级与标题

### 3.1 接口文档（api_docs）

与现有 Wiki 一致，**按请求组织**：

```text
<h1>请求中文名或协议主题</h1>          ← 一个请求/主题（解析为 section 根）
  <h2>可选小节</h2>                      ← 如「说明」「错误码」
  <pre lang="TypeScript" caption="...">  ← 见第 4 节
```

- **h1**：一条客户端↔服务端交互、一个界面协议组、或一个独立 API 主题（与现有战斗/地图页内 h1 同级）。
- **h2**：补充说明、子协议、备注；可省略。
- **不要**用 h3 及以下（解析器未依赖，且与现网文档风格不一致）。

新增请求：在模块页**按现有 h1 顺序**插入新 `h1` 块，不要插入文档 `<title>` 下全局说明区之外的无标题代码块。

### 3.2 类型约束（type_constraints）

按**类型主题**组织（非按请求）：

```text
<h1>主题名</h1>                          ← 如「网络相关」「玩家存档」「战斗」
  <pre lang="TypeScript" caption="...">  ← struct / enum / Envelope
```

- **网络相关**：须保持 `enum`、Envelope、通用包头等与现网一致命名。
- 单模块专属类型：放在对应主题的 h1 下，**不要**重复写到接口文档页（接口页只引用字段类型名）。

---

## 4. 代码块（核心）

### 4.1 标签与属性

```xml
<pre lang="TypeScript" caption="客户端|服务端|留空">
<code>// 伪 TypeScript，与现网一致
字段名: 类型;  // 可选中文注释
</code>
</pre>
```

| 属性 | 必填 | 规则 |
|------|------|------|
| `lang` | 是 | 固定 `TypeScript`（解析器据此抽字段） |
| `caption` | 推荐 | 含 **客户端** → `direction=client`；含 **服务端** → `direction=server`；共享类型可留空或写「通用」 |
| `code` 子元素 | 是 | 纯文本伪 TS，**不要**外层 markdown 围栏 |

### 4.2 字段行（与 parse 正则一致）

每行一条字段，格式：

```typescript
字段名: 类型;
字段名?: 可选类型;  // 中文说明
```

- 字段名：`[A-Za-z_][A-Za-z0-9_]*`
- 类型：写到分号前；可选字段用 `?`
- 注释：`//` 后中文说明协议含义、单位、取值范围

**禁止**在 pre 内写完整 C#/C++ 实现、using、namespace、方法体。

### 4.3 结构体（请求/响应/消息体）

接口文档中，每个 **客户端发送** 或 **服务端发送** 的消息体单独一个 `pre`（或同一 h1 下多个 pre，caption 区分方向）：

```xml
<h1>进入战斗</h1>
<pre lang="TypeScript" caption="客户端">
<code>EnterBattleReq: {
  roomId: string;
  heroId: number;
};</code>
</pre>
<pre lang="TypeScript" caption="服务端">
<code>EnterBattleRsp: {
  code: number;
  battleId: string;
};</code>
</pre>
```

- 结构体名与代码中类名/消息名一致（如 `EnterBattleReq`）。
- 若代码无独立类型名，用 `消息名 + 方向` 作注释区分，但 prefer 具名。

### 4.4 枚举

类型约束或接口文档中的 enum，**整个 enum 一个 pre**：

```xml
<pre lang="TypeScript" caption="通用">
<code>enum BattlePhase {
  Idle = 0,
  Running = 1,
  End = 2,
};</code>
</pre>
```

- 成员一行一个，`名 = 值` 或 `名,`
- 与 `parse_docx_xml._parse_enums` 一致

### 4.5 不宜用代码块的内容

- 长段 prose 协议说明 → 用 `<p>` 放在 h1/h2 下、pre 之前或之后。
- 表格型错误码 → 可用 `<table>`（解析器不抽字段，仅人类阅读）。
- 流程图 → 用 `<whiteboard>`（本流程 MVP 可仅用文字列表代替）。

---

## 5. Agent 从代码生成文档的步骤

1. **读代码 diff**（用户当前分支），识别消息名、字段增删改、enum 变更。
2. **读现有快照**（可选）：`GET /api/snapshot?module=<模块>`，对齐已有 h1/字段命名。
3. **判定目标**：`api_docs` vs `type_constraints`（见第 1 节）。
4. **生成 DocxXML 草稿**（仅包含**变更相关**章节，不要重写整页）：
   - 新增字段 → 在对应 struct 的 `pre` 内补行，或新建 `pre`；
   - 删除字段 → 在草稿中用 `<p><del>删除字段 xxx</del></p>` 或说明「删除 pre 中某行」；
   - 改类型 → 写出完整替换后的 `pre` 块便于 `block_replace`。
5. **生成 callout 外壳 + 摘要**，调用 `POST /jobs/api-doc-sync`：

```json
{
  "module": "战斗",
  "repo": "client",
  "target": "api_docs",
  "summary": "EnterBattleReq 新增 heroId；BattlePhase 新增 End=2",
  "files_changed": ["Assets/Scripts/Battle/EnterBattle.cs"],
  "docx_draft": "<h1>进入战斗</h1><pre lang=\"TypeScript\" caption=\"客户端\">...</pre>"
}
```

> `docx_draft` 为建议扩展字段：当前 ECS 仅把 `summary` 写入 callout；Agent 应将 **完整 DocxXML** 放在 `summary` 下方或单独消息中供负责人使用。实现扩展前，Agent 在对话中**全文输出** `docx_draft`。

---

## 6. 完整示例（接口文档 · 战斗 · 草稿片段）

```xml
<callout emoji="📝" background-color="light-yellow" border-color="yellow">
<p><b>【待审核】代码 → 文档同步草稿</b></p>
<p>模块：战斗 | 仓库：client | 变更：EnterBattleReq 增加 heroId</p>
<p><b>建议合并位置</b>：h1「进入战斗」下客户端 pre 之后插入</p>
<h1>进入战斗</h1>
<pre lang="TypeScript" caption="客户端">
<code>EnterBattleReq: {
  roomId: string;
  heroId: number;  // 新增：英雄配置 id
};</code>
</pre>
<p><i>请负责人在飞书审阅后合并进正文，并删除本 callout。</i></p>
</callout>
```

---

## 7. 完整示例（类型约束 · 网络相关 · enum 增补）

```xml
<pre lang="TypeScript" caption="通用">
<code>enum PacketType {
  Heartbeat = 0,
  Battle = 1,
  Lobby = 2,
};</code>
</pre>
```

---

## 8. 禁止与检查清单

| 禁止 | 原因 |
|------|------|
| 改正文且不经过 callout | 流程要求负责人审核 |
| `lang` 非 TypeScript | 解析器不抽字段 |
| 在接口页写完整 C# 源码 | 与现网伪 TS 风格不一致 |
| 客户端字段写在 caption=服务端 | direction 错乱 |
| 同一字段在接口页与类型页重复定义 | 单源：共享类型只在类型约束 |

**提交前自检**：

- [ ] 每个 `pre` 含 `lang="TypeScript"` 与 `<code>`
- [ ] caption 与代码仓库（client/server）一致
- [ ] 字段行符合 `名: 类型;` 模式
- [ ] 模块名、target 与 `wiki-registry.yaml` 一致
- [ ] 已说明建议合并的 h1/h2 位置

---

## 9. 相关链接

- 解析实现：`scripts/parse_docx_xml.py`
- 草稿追加：`scripts/doc_sync.py`
- ECS：`POST /jobs/api-doc-sync`
- 飞书 DocxXML 标签：lark-cli `lark-doc` skill → `references/lark-doc-xml.md`
