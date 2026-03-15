# AstrBot Hindsight 长期记忆插件 - 架构文档

## 1. 概述

本插件为 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 接入 [Hindsight](https://github.com/vectorize-io/hindsight) 作为 Agent 长期记忆后端。在每次将提示词发送给大模型之前，自动完成「写入记忆」与「召回长期记忆并注入多轮对话」的流程，从而让对话具备跨会话的长期记忆能力。

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AstrBot 运行时                                    │
├─────────────────────────────────────────────────────────────────────────┤
│  用户/平台消息 → 消息管道 → [本插件 on_llm_request] → LLM 提供商 → 回复     │
│                                    │                                      │
│                                    ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Hindsight Memory Plugin                                          │   │
│  │  1. 从 ProviderRequest 提取本轮/近期对话 → retain() 写入 Hindsight   │   │
│  │  2. 用当前用户问题 → recall() 召回相关长期记忆                       │   │
│  │  3. 将召回内容格式化为 system 消息插入 req.contexts                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ HTTP (hindsight_client)
                                        ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Hindsight 服务 (独立部署)                               │
│  - retain: 接收文本，抽取实体/关系/时间，写入 Memory Bank                    │
│  - recall: 多策略检索（语义/关键词/图/时间）返回相关记忆                     │
│  - bank_id = 会话标识（如 unified_msg_origin），实现按用户/会话隔离         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. 组件职责

| 组件 | 职责 |
|------|------|
| **AstrBot** | 消息路由、多轮对话管理、LLM 请求封装（ProviderRequest）、触发 `OnLLMRequestEvent` |
| **本插件** | 订阅 `OnLLMRequestEvent`，在请求前执行 retain/recall，并修改 `ProviderRequest.contexts` |
| **hindsight_client** | 通过 HTTP 调用 Hindsight API：`retain()` 写入记忆，`recall()` 检索记忆 |
| **Hindsight 服务** | 存储与检索 Agent 记忆（World/Experiences/Mental Models 等），按 bank 隔离 |

## 4. 数据流

1. **请求进入**  
   AstrBot 在即将调用 LLM 前发出 `OnLLMRequestEvent`，携带 `event: AstrMessageEvent` 与 `req: ProviderRequest`。  
   `req` 包含：`prompt`（当前轮用户输入）、`contexts`（多轮对话消息列表，每项为 `{role, content}`）。

2. **Retain（写入）**  
   - 使用 `event.unified_msg_origin` 作为 Hindsight 的 `bank_id`（如 `platform:session_type:session_id`），实现按会话隔离。  
   - 从 `req.contexts` 与 `req.prompt` 构建本轮/近期对话文本，调用 `client.retain(bank_id, content, context=..., timestamp=...)`。  
   - 在插件内通过 `asyncio.to_thread()` 调用同步的 `retain`，避免阻塞事件循环。

3. **Recall（召回）**  
   - 以当前用户问题（优先 `req.prompt`，否则从 `contexts` 最后一条 user 消息取）作为 `query`。  
   - 调用 `client.recall(bank_id, query, budget=..., max_tokens=...)`，得到与当前问题相关的长期记忆片段列表。

4. **注入**  
   - 将召回的记忆文本用配置项 `memory_system_prompt` 模板格式化（其中 `{memory}` 替换为记忆内容）。  
   - 在 `req.contexts` 中插入一条 `role="system"` 的消息：若已有 system 消息则插在第一个 system 之后，否则插在首位。  
   - 随后 AstrBot 使用修改后的 `req` 调用 LLM，大模型即可在上下文中看到长期记忆。

5. **响应**  
   LLM 正常返回，无需插件再处理；记忆的写入与注入仅在「请求前」完成。

## 5. 与 AstrBot 的集成点

- **事件类型**：`EventType.OnLLMRequestEvent`  
- **注册方式**：在插件类上使用 `@filter.on_llm_request(priority=100)` 装饰器注册处理方法。  
- **方法签名**：`async def on_req_llm(self, event: AstrMessageEvent, req: ProviderRequest) -> None`  
- **修改约定**：仅修改 `req.contexts`（及可选的 `req.prompt`），不替换整个请求；不向用户直接发送消息。  
- **优先级**：设为 100，使记忆注入在多数其他 on_llm_request 逻辑之后、发送给 LLM 之前执行；若需更早/更晚可调整 priority。

## 6. 与 Hindsight 的集成方式

- **调用方式**：使用官方 Python 客户端 `from hindsight_client import Hindsight`，通过 HTTP 访问已部署的 Hindsight API。  
- **不内置服务**：插件不启动或嵌入 Hindsight 服务进程，仅作为客户端；Hindsight 需单独部署（如 Docker / Docker Compose）。  
- **API 使用**：  
  - `retain(bank_id, content, context=..., timestamp=...)`：写入记忆。  
  - `recall(bank_id, query, budget=..., max_tokens=...)`：检索记忆，返回与 query 相关的文本列表。  
- **bank_id 策略**：默认以 `event.unified_msg_origin` 作为 bank_id，实现「每用户/每会话一个记忆库」的隔离。

## 7. 配置与扩展

- **插件配置**（如 `_conf_schema.json` / WebUI）：  
  - `base_url`：Hindsight API 地址。  
  - `recall_budget` / `recall_max_tokens`：控制召回深度与长度。  
  - `memory_system_prompt`：长期记忆注入时的系统提示模板，支持 `{memory}` 占位符。  
- **扩展点**：  
  - 若需按「用户 ID」而非「会话 ID」共享记忆，可在插件内将 `bank_id` 改为从 `event` 解析出的用户 ID。  
  - 若需区分「群聊/私聊」记忆，可在 `bank_id` 或 Hindsight 的 metadata 中加入会话类型。

## 8. 依赖关系

- **AstrBot**：>= 4.16, < 5（以支持 `OnLLMRequestEvent` 与 `ProviderRequest`）。  
- **hindsight-client**：>= 0.4.0（PyPI：`hindsight-client`）。  
- **Hindsight 服务**：需单独部署并可用，版本与 API 与 `hindsight-client` 兼容（如 0.4.x）。

---

以上为 AstrBot Hindsight 长期记忆插件的架构说明；详细行为与配置见「设计文档」与插件内 `_conf_schema.json`。
