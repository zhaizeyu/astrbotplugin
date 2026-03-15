# AstrBot Hindsight 长期记忆插件 - 数据结构文档

本文描述插件涉及的配置结构、AstrBot 请求中的数据结构以及插件生成/消费的数据格式。插件自身不维护数据库，仅使用「配置结构」和「内存中的请求/消息结构」。

---

## 1. 插件配置结构（_conf_schema.json）

配置由 AstrBot 从 WebUI 或配置源加载后，以字典形式传入插件 `__init__(context, config)` 的 `config`。AstrBot 要求 `_conf_schema.json` 的**根级为扁平对象**（配置项名 → 项描述），类型使用 `bool`/`int`/`float`/`string`/`text` 等，不能使用外层 `"type":"object"` + `"properties"` 的 JSON Schema 包裹。

### 1.1 配置 Schema 概要

```json
{
  "enabled": { "type": "bool", "description": "...", "default": true },
  "base_url": { "type": "string", "description": "...", "default": "http://localhost:8888" },
  "timeout": { "type": "float", "description": "...", "default": 30 },
  "recall_budget": { "type": "string", "options": ["low", "mid", "high"], "default": "mid" },
  "recall_max_tokens": { "type": "int", "description": "...", "default": 2048 },
  "memory_system_prompt": { "type": "text", "description": "...", "default": "..." },
  "retain_context": { "type": "string", "description": "...", "default": "astrbot_chat" }
}
```

### 1.2 字段说明

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | boolean | true | 是否启用记忆逻辑 |
| base_url | string | "http://localhost:8888" | Hindsight API base URL |
| timeout | number | 30 | Hindsight 请求超时（秒） |
| recall_budget | string | "mid" | recall 检索深度 |
| recall_max_tokens | integer | 2048 | recall 返回最大 token 数 |
| memory_system_prompt | string | 见下 | 注入 system 的模板，含 `{memory}` |
| retain_context | string | "astrbot_chat" | retain 的 context 参数 |

`memory_system_prompt` 默认内容（`\n` 为换行）：

```
以下是与当前对话相关的长期记忆，供你参考：

{memory}

请结合上述记忆自然地进行回复。
```

---

## 2. AstrBot ProviderRequest 相关结构

插件在 `on_req_llm(event, req)` 中读取并修改 `req: ProviderRequest`。这里只描述插件用到的字段与约定格式。

### 2.1 req.prompt

- **类型**：`str`（或可转为字符串的当前轮用户输入）。
- **含义**：当前轮次用户发给 LLM 的「本句」输入。
- **插件用法**：作为 recall 的 `query` 首选；并参与 `_build_retain_content(req)` 拼写写入内容。

### 2.2 req.contexts

- **类型**：`list[dict]`，每个元素为一条消息。
- **单条消息结构**：
  - `role`：`"system"` | `"user"` | `"assistant"`。
  - `content`：字符串或多模态列表（见下）。

**content 的两种常见形态：**

1. **纯文本**：`"content": "用户输入的文本"`  
2. **多模态（OpenAI 风格）**：  
   `"content": [ {"type": "text", "text": "..."}, {"type": "image_url", "image_url": {"url": "..."}} ]`

插件从 `content` 中只提取文本部分（见 `_get_text_from_content`）：若为 list，则取 `type=="text"` 的 `text` 并拼接。

### 2.3 插件对 req.contexts 的修改

- **操作**：在合适位置**插入一条**新的 system 消息，不删除、不修改已有消息。
- **插入规则**：
  - 若 `req.contexts` 为空：`req.contexts = [ inject_msg ]`。
  - 若已存在至少一条 `role=="system"`：在**第一个** system 消息**之后**插入 `inject_msg`。
  - 否则：在 `req.contexts` 的**最前面**插入 `inject_msg`。

**inject_msg 结构：**

```json
{
  "role": "system",
  "content": "<memory_system_prompt 中 {memory} 被替换为召回文本后的完整字符串>"
}
```

即插件只增加一个「长期记忆」的 system 消息，其余 role 与顺序由 AstrBot 原有逻辑决定。

---

## 3. 插件构建的 retain 内容结构

`_build_retain_content(req)` 返回一段**纯文本**，用于调用 `client.retain(bank_id, content, ...)`。

### 3.1 文本格式

- 多行字符串，每行形式为：
  - `用户: <从 role=user 的 content 中提取的文本>`
  - `助手: <从 role=assistant 的 content 中提取的文本>`
- 来源顺序：
  - 先取 `req.contexts` 中**最近若干条**（当前实现为最后 6 条）的 user/assistant 文本；
  - 再追加当前轮 `req.prompt`（若有），作为一条「用户: ...」。

### 3.2 示例

```
用户: 我叫小明
助手: 你好小明，有什么可以帮你的？
用户: 我比较喜欢跑步
```

该字符串整体作为一次 `retain` 的 `content` 传入 Hindsight，不包含 JSON 或结构化字段；Hindsight 内部会做实体/关系/时间等抽取。

---

## 4. recall 返回值的插件内形态

- **类型**：`list[str]`。
- **来源**：对 `client.recall(...)` 返回值的兼容处理：
  - 若有 `response.results`，则对每个元素取 `.text` 或 `str(element)`；
  - 若返回值为 list，则同样取每个元素的 text 或 str。
- **注入时**：将列表中所有字符串用换行拼接成一段，填入 `memory_system_prompt` 的 `{memory}`，得到最终注入的 system `content`。

---

## 5. 小结

| 结构 | 用途 |
|------|------|
| _conf_schema.json / config 字典 | 插件配置，控制启用、Hindsight 地址、recall 参数、提示词模板等 |
| req.prompt / req.contexts | 输入：当前轮与多轮对话；输出：插入一条 system 长期记忆消息 |
| inject_msg | 单条 `{ role: "system", content: "..." }`，content 由 memory_system_prompt 经 `replace("{memory}", ...)` 得到 |
| retain content 文本 | 多行「用户: / 助手:」纯文本，供 Hindsight retain 使用 |
| recall 结果 list[str] | 拼接后替换 `{memory}`，写入 inject_msg 的 content |

本插件**不定义**数据库表或持久化文件格式；持久化由 Hindsight 服务端负责，插件仅使用上述内存与配置结构。
