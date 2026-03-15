# AstrBot Hindsight 长期记忆插件 - 接口文档

本文描述插件的对外集成点、配置接口以及内部使用的 Hindsight 客户端接口，便于二次开发与排查问题。

---

## 1. 插件与 AstrBot 的接口

### 1.1 事件钩子

插件通过 AstrBot 的 **OnLLMRequestEvent** 在「请求大模型之前」介入。

| 项目 | 说明 |
|------|------|
| 事件类型 | `EventType.OnLLMRequestEvent` |
| 注册方式 | `@filter.on_llm_request(priority=100)` |
| 处理函数 | `async def on_req_llm(self, event: AstrMessageEvent, req: ProviderRequest) -> None` |
| 调用方 | AstrBot 框架（在构造好本次 LLM 请求后、发送前） |
| 约定 | 仅修改 `req`（如 `req.contexts`）；不向用户直接发送消息 |

**参数：**

- **event: AstrMessageEvent**  
  - 当前消息事件。  
  - 插件使用：`event.unified_msg_origin` 作为 Hindsight 的 `bank_id`（会话/用户隔离）。

- **req: ProviderRequest**  
  - 本次 LLM 请求体。  
  - 插件读取：`req.prompt`、`req.contexts`。  
  - 插件修改：向 `req.contexts` 插入一条 `role="system"` 的长期记忆消息（详见 [data-structures.md](./data-structures.md)）。

**执行顺序：**  
同一事件上可能注册多个 `on_llm_request`；本插件使用 `priority=100`，具体顺序由 AstrBot 的 handler 排序规则决定（数字越大越先执行，视框架实现而定）。

---

## 2. 插件配置接口

配置来源于 AstrBot 的插件配置（WebUI 或配置文件），由框架在加载时传入插件 `__init__(context, config)` 的 `config` 参数。结构见 `_conf_schema.json`，字段说明如下。

| 键 | 类型 | 默认值 | 说明 |
|----|------|--------|------|
| enabled | boolean | true | 为 false 时，on_req_llm 直接返回，不执行 retain/recall/注入 |
| base_url | string | "http://localhost:8888" | Hindsight API 的 base URL，无尾部斜杠 |
| timeout | number | 30 | 调用 Hindsight HTTP 的超时时间（秒） |
| recall_budget | string | "mid" | recall 检索深度：`low` / `mid` / `high` |
| recall_max_tokens | integer | 2048 | 单次 recall 返回内容的最大 token 数 |
| memory_system_prompt | string | 见下 | 注入长期记忆时的 system 内容模板，必须包含 `{memory}` |
| retain_context | string | "astrbot_chat" | retain 时传给 Hindsight 的 context 字段 |

**memory_system_prompt 默认值：**

```
以下是与当前对话相关的长期记忆，供你参考：

{memory}

请结合上述记忆自然地进行回复。
```

---

## 3. 插件对 Hindsight 的调用接口

插件通过官方 Python 客户端 `hindsight_client.Hindsight` 访问已部署的 Hindsight 服务（如 `http://localhost:8888`），不启动或嵌入 Hindsight 进程。

### 3.1 客户端初始化

- **方式**：在插件内 `Hindsight(base_url=self._base_url, timeout=self._timeout)`。
- **时机**：首次需要调用时在 `_get_client()` 中懒加载，并复用同一实例。
- **base_url**：来自配置项 `base_url`，例如调试环境为 `http://localhost:8888`。

### 3.2 retain（写入记忆）

- **用途**：将当前/近期对话内容写入指定 memory bank。
- **调用**：`client.retain(bank_id, content, context=..., timestamp=...)`
- **插件传参**：
  - `bank_id`：`event.unified_msg_origin`（会话/用户标识）。
  - `content`：由 `_build_retain_content(req)` 生成（详见 [data-structures.md](./data-structures.md)）。
  - `context`：配置项 `retain_context`。
  - `timestamp`：当前 UTC 时间。
- **执行**：在异步上下文中通过 `asyncio.to_thread(client.retain, ...)` 调用，避免阻塞事件循环。

### 3.3 recall（召回记忆）

- **用途**：根据当前用户问题检索相关长期记忆。
- **调用**：`client.recall(bank_id, query, budget=..., max_tokens=...)`
- **插件传参**：
  - `bank_id`：与 retain 相同。
  - `query`：当前用户问题（优先 `req.prompt`，否则从 `req.contexts` 最后一条 user 消息取，再否则用本次 retain 的摘要）。
  - `budget`：配置项 `recall_budget`（low/mid/high）。
  - `max_tokens`：配置项 `recall_max_tokens`。
- **返回值处理**：兼容 `response.results` 或 `response` 为 list，统一得到 `list[str]`；若无结果或异常则返回空列表，不注入记忆。

---

## 4. 插件不提供的接口

- **对外 HTTP API**：插件不提供独立 API 端口，仅通过 AstrBot 事件与配置交互。  
- **Hindsight 服务管理**：不负责启动/停止 Hindsight；仅作为客户端连接已有服务。  
- **Bank 管理**：不显式调用 create_bank；依赖 Hindsight 在首次 retain 时按 bank_id 自动创建。

---

## 5. 参考

- [data-structures.md](./data-structures.md) - `req.contexts`、注入消息、retain content 等结构说明  
- [deployment.md](./deployment.md) - 配置与部署  
- [Hindsight API](https://hindsight.vectorize.io/developer/api/operations) - Hindsight 服务端接口说明
