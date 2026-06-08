# 代码 → 飞书文档：Agent 写文档格式规范

> 权威源对照：
>
> - [接口文档](https://my.feishu.cn/wiki/NYw0wSFwji6j3skwW4ocIrkxn6b)（`api_docs`，按模块叶子页）
> - [类型约束](https://my.feishu.cn/wiki/CF6owdEKLiYhwmkBrMxcgxK8nde)（`type_constraints`，共享类型/枚举）

与 `scripts/parse_docx_xml.py` 解析规则一致；Agent 产出须能被同一解析器读回。

---

## 1. 写哪一份文档


| 代码变更类型                                        | 目标文档                                                  | `wiki-registry` 字段     | 示例模块       |
| --------------------------------------------- | ----------------------------------------------------- | ---------------------- | ---------- |
| 请求/响应消息、协议号、联机包字段                             | **接口文档** 模块叶子页                                        | `api_docs_obj`         | 战斗、地图、联机大厅 |
| 跨模块 enum、Envelope、全局通用类型                      | **类型约束**                                              | `type_constraints_obj` | 网络相关、玩家存档  |
| **仅本模块、本端** 使用的配置/表结构（如 ScriptableObject 定义类） | **接口文档** 该模块页；模式 A 用 **h2 主题** + **pre×2**（无 caption） | `api_docs_obj`         | 任意模块·客户端配置 |


**判定顺序（Agent 必做）**：

1. 是否 **多模块复用** 或文档已约定在「类型约束」？→ `target: type_constraints`。
2. 否则是否为 **网络/TCP 协议消息** 或 **client/server 交互**？→ `target: api_docs`；同一小节内**客户端/服务端各一条消息**时，`pre` 的 `**caption` 写客户端/服务端** 以区分方向（§4.3）。
3. 是否为 **单模块、单端配置/表**（仅类型定义，无实例）？→ `target: api_docs`；模式 A 用 `**h2` 主题名** + **两个 `pre`（enum / type）**（§4.6），**不要** `caption="客户端"` 代替挂在 `h1 客户端` 下。

- 仅改 client 代码 → `repo: client`；分区靠 **合并到 `h1 客户端` 下**，不是靠代码块 caption。
- 仅改 server 代码 → `repo: server`；同理 `**h1 服务端`**。

`POST /jobs/api-doc-sync` 的 `target` 字段：

- `"api_docs"`（默认）— 接口文档叶子
- `"type_constraints"` — 类型约束叶子

---

## 2. 交付方式

### 写入正文（ECS 默认）

通过 `api-doc-sync` 写入 DocxXML 正文（**不使用 callout**）。`doc_sync.py` 会：

- 在页内存在 **`h1 客户端` / `h1 服务端`** 时，将草稿 **插入到与 `repo` 对应分区末尾**（`block_insert_after`）；
- 否则 **append** 到文档末尾；
- **自动剔除** `docx_draft` 中的 **【合并位置】** 段落；
- 对每个 `h1`/`h2` 标题自动补上 **`（agent生成，待审查）`**（若 Agent 已写上则不再重复）。

Agent 产出须按下面第 3～5 节编写；`docx_draft` 字段携带完整片段，由 ECS 写入飞书。

### 负责人审阅

1. 在飞书中搜索标题含 `**（agent生成，待审查）**` 的章节；
2. 核对字段与代码一致后，用 `docs +update` 的 `str_replace` / `block_replace` / `block_insert_after` 合并到对应正式 `h1`/`h2`/`pre`（或就地改标题去掉标记、整理段落）；
3. 删除或改写已审阅的 agent 段落，避免重复。

Agent 应**同时**给出：建议合并的正式章节名、完整 DocxXML、`summary`。

---

## 3. 文档层级与标题

### 3.1 接口文档（api_docs）

**生成前必读快照**：`GET /api/snapshot?module=<模块>`，确认该模块页**已有层级**，再决定用 `h1` 还是 `h2`。

#### 模式 A：页内已有 `h1 客户端` / `h1 服务端`（常见）

许多模块（战斗、地图、联机大厅等）接口文档为：

```text
<模块页>
├── h1 客户端              ← 方向分区（已存在，勿重复创建）
│   ├── h2 <主题A> + pre   ← 如协议请求、配置、玩法子模块
│   └── h2 <主题B> + pre
└── h1 服务端
    └── h2 … + pre
```

**凡新增内容属于某一方向（与 `repo` 一致）时**：


| 规则  | 说明                                                                                                        |
| --- | --------------------------------------------------------------------------------------------------------- |
| 禁止  | 为子主题再建 `**h1 <主题名>（agent生成，待审查）`**（会与「客户端」「服务端」并列成一级目录）                                                   |
| 必须  | 使用 `**h2 <主题名>（agent生成，待审查）**`，语义上落在对应 `**h1 客户端**` 或 `**h1 服务端**` 之下                                     |
| 禁止  | 用 `**h1 <主题名>**` 当子主题（会与「客户端」「服务端」并列）                                                                     |
| 禁止  | 用 `**caption="客户端"` / `caption="服务端"**` 代替分区——那是代码块在飞书里的**显示名**，不是文档目录；配置类（§4.6）**不写 caption**（与现网块名一致即可） |
| 勿重复 | 不要 append 第二个 `h1 客户端` / `h1 服务端`                                                                         |


```text
<h2>武器（agent生成，待审查）</h2>        ← 业务主题名，不是「客户端」
  <pre lang="TypeScript">…enum…</pre>      ← 无 caption 或留空
  <pre lang="TypeScript">…type…</pre>
```

**子主题**指：配置类型（表结构）、单条协议、玩法逻辑分组等，**不限于**某一模块或业务名称。

#### 模式 B：页内无「客户端/服务端」分区

若快照中**没有** `h1 客户端` / `h1 服务端`，新主题用 `**h1 <主题名>（agent生成，待审查）</h1>`**（与现网同级请求/主题一致即可）。

#### 标题标记

`**（agent生成，待审查）**` 只加在**具体主题**的 `h1`/`h2` 上，不加在「客户端」「服务端」总标题上。

**禁止**用 h2/h1 充当：「枚举与数据结构」「实例」「资源路径」「配置说明」等空泛小节名；枚举/类型进 `pre`，不单独起标题。

#### ECS 插入位置（模式 A）

| 项 | 规则 |
|----|------|
| 插入点 | `repo: client` → **h1 客户端** 分区内**最后一个 block 之后**；`repo: server` → **h1 服务端** 分区末尾 |
| Agent `docx_draft` | **禁止** 写 `<p>【合并位置】…</p>`；合并说明只在 **对话回复** 中口述即可 |
| 审阅 | 去掉标题「（agent生成，待审查）」；若历史误 append 到文末，删除重复段 |

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


| 属性         | 必填  | 规则                                                                                                       |
| ---------- | --- | -------------------------------------------------------------------------------------------------------- |
| `lang`     | 是   | 固定 `TypeScript`（解析器据此抽字段）                                                                                |
| `caption`  | 视场景 | **§4.3 协议消息**（同节多方向）：写 **客户端** / **服务端**。**§4.6 配置类型（模式 A）**：**省略**或留空，勿用 caption 当分区。**类型约束**：可写「通用」或留空 |
| `code` 子元素 | 是   | 纯文本伪 TS，**不要**外层 markdown 围栏                                                                             |


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
- **h2 标题可用中文**；**pre 内第一行必须是英文类型名**，格式 `RegisterReq: { ... };`（与代码 struct 一致），中文说明写在 `//` 注释。
- 若代码无独立类型名，用 `消息名 + 方向` 作注释区分，但 prefer 具名。

### 4.4 枚举

enum 写在 **伪 TS** 中，格式与 `parse_docx_xml._parse_enums` 一致。成员一行一个，`名 = 值`。

多个 enum 属于**同一主题**时，写在**同一个** `pre` 的 `<code>` 内（不要每个 enum 一个标题）；**所有 type** 放在**另一个** `pre`（见 4.6）。

### 4.6 含 enum + type 的配置/类型主题（普适）

适用于任意模块、任意业务名：配置表、技能/物品/任务定义、ScriptableObject **类型**（非实例）、仅单端使用的数据结构等。

**与 4.3 的区别**：4.3 是**单条协议消息**（`MessageName: { }`，常各方向一个 `pre`）；4.6 是**类型系统**（`type X = { }` + enum），且 **enum 与 type 必须分两个 `pre`**。

**模式 A 页（已有 h1 客户端/服务端）— 推荐结构**：

```xml
<h2>武器（agent生成，待审查）</h2>
<pre lang="TypeScript">
<code>enum WeaponType { Melee = 0, Ranged = 1, }
enum WeaponTag { None = 0, Melee = 1, Ranged = 2, }</code>
</pre>
<pre lang="TypeScript">
<code>type WeaponConfig = { weaponName: string; damage: number; /* 仅字段，无实例行 */ };
type WeaponDatabase = { weapons: WeaponConfig[]; };
type Projectile = { speed: number; lifetime: number; };</code>
</pre>
```

**勿写入**：`// Knife`、`.asset` 路径、`{ weaponName: "Knife", damage: 6, … }` 等**配置实例取值**（变更在仓库与 registry，不进接口文档）。


| 规则             | 说明                                                              |
| -------------- | --------------------------------------------------------------- |
| 层级             | 模式 A：`**h2 <主题名>`** under `**h1 客户端/服务端**`；禁止 `**h1 <主题名>**`    |
| 代码块            | **第 1 个 `pre`**：该主题下**全部 enum**；**第 2 个 `pre`**：该主题下**全部 type** |
| 仅 enum 或仅 type | 仍只写一个 `pre`；同时有两类则**必须两个** `pre`                                |
| 类型写法           | 配置/表用 `type Name = { }`；协议消息用 4.3 的 `MsgName: { }`              |
| 禁止内容           | 实例取值、资源路径列表、.asset 行、方法体、C# 源码                                  |


**错误示范（任意模块均适用）**：


| 禁止                              | 说明                                         |
| ------------------------------- | ------------------------------------------ |
| 在模式 A 页用 `h1` 写子主题（如 `h1 武器配置`） | 子主题一律 `**h2 武器`**                          |
| 用 `caption="客户端"` 表示挂在客户端下      | 分区用 **h2 + 合并到 h1 客户端**；配置类 **不写 caption** |
| enum + type 同一 `pre`            | 拆成两个 `pre`                                 |
| pre 内 `// Knife`、字面量对象行         | 只写 **type/enum 定义**，不写表数据实例                |
| 多个 h1/h2：「枚举与数据结构」「实例」「资源路径」    | 一个业务主题一个 `h2`                              |
| 把路径、实例写进文档                      | 仓库与 registry 体现                            |


**示例（仅示意；`<模块>`、`<主题名>` 替换为实际值）**：

```json
{
  "module": "<模块>",
  "repo": "client",
  "target": "api_docs",
  "summary": "<主题名>：enum 与 type 分块，合并到客户端分区",
  "docx_draft": "<h2><主题名>（agent生成，待审查）</h2><pre lang=\"TypeScript\"><code>enum ...</code></pre><pre lang=\"TypeScript\"><code>type ...</code></pre>"
}
```

> ECS 按 `repo` 插入到 **h1 客户端/服务端** 分区末尾；**不要**在 `docx_draft` 里写【合并位置】。

#### Agent 易错反例（战斗·武器，勿照抄）


| 错误产出 | 正确做法 |
| -------- | -------- |
| `<h1>武器配置…</h1>` 或草稿在**全文末尾** | `<h2>武器（agent生成，待审查）</h2>`；ECS 插入 **h1 客户端** 分区末 |
| `docx_draft` 含 `<p>【合并位置】…</p>` | **不要写**；ECS 会剔除，该段不应出现在飞书 |
| `<pre caption="客户端">` 整块 enum+type | **两个** `<pre lang="TypeScript">`（无 caption） |
| pre 末尾 `// Knife` + 字面量对象行 | **删除**；文档只写 type/enum |


### 4.5 不宜用代码块的内容

- 长段 prose 协议说明 → 用 `<p>` 放在 h1/h2 下、pre 之前或之后。
- 表格型错误码 → 可用 `<table>`（解析器不抽字段，仅人类阅读）。
- 流程图 → 用 `<whiteboard>`（本流程 MVP 可仅用文字列表代替）。

---

## 5. Agent 从代码生成文档的步骤

1. **读代码 diff**（用户当前分支），识别消息名、字段增删改、enum 变更。
2. **读现有快照**（可选）：`GET /api/snapshot?module=<模块>`，对齐已有 h1/字段命名。
3. **判定目标**：`api_docs` vs `type_constraints`（见第 1 节）。
4. **生成 DocxXML 草稿**（先对照快照层级；仅包含**变更相关**章节，不要重写整页）：
  - 新增字段 → 在对应 struct 的 `pre` 内补行，或新建 `pre`；
  - 删除字段 → 在草稿中用 `<p><del>删除字段 xxx</del></p>` 或说明「删除 pre 中某行」；
  - 改类型 → 写出完整替换后的 `pre` 块便于 `block_replace`。
5. 调用 `POST /jobs/api-doc-sync`（**必填** `docx_draft` 或 `summary` 至少其一）：

```json
{
  "module": "战斗",
  "repo": "client",
  "target": "api_docs",
  "summary": "EnterBattleReq 新增 heroId；BattlePhase 新增 End=2",
  "files_changed": ["Assets/Scripts/Battle/EnterBattle.cs"],
  "docx_draft": "<h1>进入战斗（agent生成，待审查）</h1><pre lang=\"TypeScript\" caption=\"客户端\">...</pre>"
}
```

> `docx_draft` 写入飞书正文；`h1`/`h2` 须带 `**（agent生成，待审查）**`。无 `docx_draft` 时 ECS 仅追加摘要块（标题同样带该标记）。

---

## 6. 完整示例（接口文档 · 战斗 · append 片段）

```xml
<hr/>
<h1>进入战斗（agent生成，待审查）</h1>
<pre lang="TypeScript" caption="客户端">
<code>EnterBattleReq: {
  roomId: string;
  heroId: number;  // 新增：英雄配置 id
};</code>
</pre>
```

负责人审阅后：合并到正式 h1「进入战斗」对应 `pre`，并删除或改写带标记的 agent 段落。

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


| 禁止                            | 原因                                |
| ----------------------------- | --------------------------------- |
| 生成 h1/h2 不带「（agent生成，待审查）」    | 无法区分待审内容                          |
| 使用 callout 包裹草稿               | 已废弃，一律写正文                         |
| `lang` 非 TypeScript           | 解析器不抽字段                           |
| 在接口页写完整 C# 源码                 | 与现网伪 TS 风格不一致                     |
| 配置类用 caption=客户端/服务端 代替 h2 分区 | 块名误当目录；§4.6 应无 caption            |
| 协议消息客户端字段写在 caption=服务端       | direction 错乱                      |
| 同一字段在接口页与类型页重复定义              | 单源：共享类型只在类型约束                     |
| 模式 A 页用 `h1` 写子主题             | 子主题必须用 `h2`，挂在对应方向 `h1` 下（见 3.1）  |
| enum 与 type 同一 `pre`          | 必须两个 `pre`（见 4.6）                 |
| 拆「实例」「资源路径」「枚举与数据结构」等标题       | 仅 `h2` 主题名 + 两个 `pre`             |
| 把 .asset / JSON 数据行写入文档       | 只写类型，不写配置实例值                      |
| 配置表写在类型约束                     | 模块专属 client 配置写接口文档 + caption 客户端 |


**提交前自检**：

- 已读 snapshot，判定模式 A/B；模式 A 下子主题为 **h2**，未新建与「客户端/服务端」同级的 `h1`
- 已判定 `api_docs` vs `type_constraints`；§4.6 **未**用 caption 代替 h2/客户端分区
- 含 enum+type：**两个 pre**（无 caption）；**无**【合并位置】段落；**无**实例行与 .asset 数值
- 每个 `pre` 含 `lang="TypeScript"` 与 `<code>`
- 字段行符合 `名: 类型;` 模式，无 C# 路径列表、无 .asset 实例块
- 模块名、target 与 `wiki-registry.yaml` 一致

---

## 9. 相关链接

- 解析实现：`scripts/parse_docx_xml.py`
- 草稿追加：`scripts/doc_sync.py`
- ECS：`POST /jobs/api-doc-sync`
- 飞书 DocxXML 标签：lark-cli `lark-doc` skill → `references/lark-doc-xml.md`

