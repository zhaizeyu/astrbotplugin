# AstrBot Hindsight 长期记忆插件 - 设计文档

## 1. 设计目标

- 在**提示词喂给大模型之前**完成记忆的写入与召回，并**将长期记忆插入到多轮对话**中。  
- 使用 **Hindsight 客户端调用方式**（`from hindsight_client import Hindsight`），不嵌入 Hindsight 服务本身。  
- 对 AstrBot 与 Hindsight 的改动最小：仅通过 `OnLLMRequestEvent` 钩子修改 `ProviderRequest`，不改变 AstrBot 核心流程。

## 2. 功能设计

### 2.1 写入记忆（Retain）

- **触发时机**：每次 `on_req_llm` 被调用时（即每次即将请求 LLM 前）。  
- **写入内容**：  
  - 由 `_build_retain_content(req)` 从 `ProviderRequest` 生成：  
    - 最近若干条 `contexts` 中的 user/assistant 文本；  
    - 当前轮的 `req.prompt`。  
  - 格式化为「用户: …」「助手: …」的简单对话片段，便于 Hindsight 抽取实体与关系。  
- **参数**：  
  - `bank_id`：`event.unified_msg_origin`，保证按会话隔离。  
  - `context`：配置项 `retain_context`（如 `astrbot_chat`），用于标记来源。  
  - `timestamp`：当前 UTC 时间。  
- **执行方式**：在异步 handler 内通过 `asyncio.to_thread(client.retain, ...)` 调用同步 `retain`，避免阻塞。

### 2.2 召回记忆（Recall）

- **触发时机**：同一次 `on_req_llm` 内，在 retain 之后执行。  
- **查询构造**：  
  - 优先使用 `req.prompt` 作为 `query`；  
  - 若为空，则从 `req.contexts` 中取最后一条 `role=user` 的 content 文本；  
  - 若仍为空，则用本次 retain 的摘要文本作为 query。  
- **参数**：  
  - `bank_id`：与 retain 一致。  
  - `query`：上述查询文本。  
  - `budget`：配置项 `recall_budget`（low/mid/high），控制检索深度。  
  - `max_tokens`：配置项 `recall_max_tokens`，限制返回内容长度。  
- **返回值处理**：  
  - 兼容 `response.results` 或 `response` 为 list 两种形态，统一解析为 `list[str]`；  
  - 若无结果或异常，则不注入记忆，仅正常放行请求。

### 2.3 注入长期记忆到多轮对话

- **格式**：使用配置项 `memory_system_prompt`，其中占位符 `{memory}` 使用字符串 replace 替换为召回的记忆文本（多条用换行拼接），避免用户模板中含其他花括号时 format 报错。  
- **插入位置**：  
  - 若 `req.contexts` 为空，则 `req.contexts = [inject_msg]`。  
  - 若已有至少一条 `role=system`，则在**第一个 system 消息之后**插入该条 system 记忆消息。  
  - 否则在 `req.contexts` **最前**插入。  
- **不修改**：不删除或修改已有 system 消息，只新增一条「长期记忆」system 消息。

## 3. 配置项设计

| 配置键 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| enabled | bool | true | 是否启用记忆逻辑 |
| base_url | string | http://localhost:8888 | Hindsight API base_url |
| timeout | number | 30 | 请求超时（秒） |
| recall_budget | string | mid | recall 检索深度：low / mid / high |
| recall_max_tokens | int | 2048 | 单次 recall 返回的最大 token 数 |
| memory_system_prompt | string | 见下 | 注入记忆时的系统提示模板，支持 {memory} |
| retain_context | string | astrbot_chat | retain 时的 context 字段 |

默认 `memory_system_prompt` 示例：

```text
以下是与当前对话相关的长期记忆，供你参考：

{memory}

请结合上述记忆自然地进行回复。
```

## 4. 错误与边界处理

- **未安装 hindsight-client**：插件加载时打 log，`on_req_llm` 直接 return，不抛错。  
- **Hindsight 不可用**：`_get_client()` 或 retain/recall 异常时，仅打 log，不修改 `req`，请求照常发给 LLM。  
- **recall 返回空**：不插入 system 消息，其余流程不变。  
- **content 多模态**：从 `content` 中只取文本部分（str 或 list 中 type=text 的 text），忽略图片等，避免无效写入。

## 5. 与现有插件的关系

- 与「群聊上下文」等同样使用 `@filter.on_llm_request()` 的插件可并存；通过 `priority` 控制顺序（本插件 priority=100）。  
- 本插件不依赖其他记忆或上下文插件；仅依赖 AstrBot 的 `OnLLMRequestEvent` 与 `ProviderRequest` 结构。

## 6. 后续可扩展方向

- **bank_id 策略**：支持按「用户 ID」聚合多会话记忆，或按「平台+群组」共享群记忆。  
- **选择性 retain**：仅对部分会话类型或关键词触发 retain，降低写入量。  
- **使用 reflect**：对需要「基于记忆做推理」的场景，可调用 Hindsight 的 `reflect()` 替代或补充 `recall()`。  
- **异步 Hindsight API**：若 `hindsight-client` 提供 `aretain`/`arecall`，可改为直接 await，减少线程池占用。

---

以上为插件的行为与设计说明；实现细节见仓库内 `astrbot_plugin_hindsight_memory/main.py` 与 `_conf_schema.json`。
