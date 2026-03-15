# AstrBot Hindsight 长期记忆插件 - 产品需求文档（PRD）

**文档版本**：0.1  
**产品名称**：Hindsight 长期记忆插件（astrbot_plugin_hindsight_memory）  
**目标版本**：0.1.0  

---

## 1. 产品概述

### 1.1 一句话描述

为 AstrBot 提供基于 [Hindsight](https://github.com/vectorize-io/hindsight) 的 Agent 长期记忆能力：在每次把提示词发给大模型之前，自动将当前对话写入 Hindsight、召回相关长期记忆，并插入到多轮对话中，使回复能够利用跨会话记忆。

### 1.2 核心价值

- **用户侧**：对话具备「长期记忆」，机器人能记住历史偏好、事实与上下文，减少重复说明。  
- **平台侧**：通过标准插件与事件钩子接入，不侵入 AstrBot 核心；记忆能力由成熟开源项目 Hindsight 提供。  
- **技术侧**：采用「客户端调用 Hindsight API」的方式，部署清晰：AstrBot + 独立 Hindsight 服务。

### 1.3 产品定位

- **类型**：AstrBot 插件（Star），依赖 AstrBot >= 4.16 与独立部署的 Hindsight 服务。  
- **调用方式**：使用官方 Python 客户端 `from hindsight_client import Hindsight`，通过 HTTP 访问 Hindsight，不内置或托管 Hindsight 进程。  
- **触发时机**：仅在「请求大模型前」介入（OnLLMRequestEvent），不提供独立命令或 API。

---

## 2. 目标与成功标准

### 2.1 产品目标


| 目标      | 说明                                                          |
| ------- | ----------------------------------------------------------- |
| 自动化记忆流程 | 每次 LLM 请求前自动执行「写入 + 召回 + 注入」，无需用户或开发者额外操作。                  |
| 会话隔离    | 按 AstrBot 会话（unified_msg_origin）隔离记忆库（bank_id），避免跨用户/跨会话泄露。 |
| 可配置可关闭  | 通过配置控制启用/禁用、Hindsight 地址、召回深度与提示词模板，便于部署与调优。                |
| 故障不阻断   | Hindsight 不可用或调用失败时，仅记录日志并跳过记忆逻辑，LLM 请求照常进行。                |


### 2.2 成功标准

- 在已部署 AstrBot 与 Hindsight 的环境中，安装并启用插件后，多轮对话中机器人能依据此前对话内容作答。  
- 配置中关闭「启用插件」或 Hindsight 不可用时，对话仍可正常进行，无崩溃。  
- 文档完整：部署、开发、接口、数据结构均有说明，可支撑部署与二次开发。

---

## 3. 用户与干系人


| 角色          | 描述                             | 主要需求                               |
| ----------- | ------------------------------ | ---------------------------------- |
| 终端用户        | 使用 AstrBot 与机器人对话的人            | 希望机器人「记得」自己说过的话与偏好，减少重复说明。         |
| 部署/运维       | 安装 AstrBot、部署 Hindsight、配置插件的人 | 清晰的安装步骤、配置项说明、可选调试环境（如 6185/8888）。 |
| 插件开发者       | 修改或扩展本插件的人                     | 开发流程、接口说明、数据结构与错误处理约定。             |
| AstrBot 维护方 | 框架与插件生态                        | 插件符合 Star 规范，仅使用公开事件与配置，不破坏核心流程。   |


---

## 4. 功能需求

### 4.1 必须实现（MVP）


| ID  | 需求                     | 验收说明                                                                    |
| --- | ---------------------- | ----------------------------------------------------------------------- |
| F1  | 在 LLM 请求前写入记忆          | 每次 OnLLMRequestEvent 触发时，用当前/近期对话内容调用 Hindsight retain，bank_id 为会话标识。   |
| F2  | 在 LLM 请求前召回记忆          | 以当前用户问题为 query 调用 Hindsight recall，得到相关记忆文本列表。                          |
| F3  | 将召回记忆注入多轮对话            | 将记忆按配置模板格式化为一条 system 消息，插入 req.contexts 的合适位置，再交给 LLM。                 |
| F4  | 按会话隔离记忆                | bank_id 使用 event.unified_msg_origin，不同会话互不读写对方记忆。                       |
| F5  | 可配置启用/禁用与 Hindsight 地址 | 提供 enabled、base_url 等配置项，并在 WebUI（_conf_schema.json）中展示。                |
| F6  | 召回与提示词可调               | 提供 recall_budget、recall_max_tokens、memory_system_prompt（含 {memory}）等配置。 |
| F7  | 失败不阻断对话                | retain/recall 异常时仅打日志，不修改 req 或抛错，LLM 请求照常执行。                           |


### 4.2 可选 / 后续迭代


| ID  | 需求                   | 说明                                                  |
| --- | -------------------- | --------------------------------------------------- |
| O1  | bank_id 策略可配置        | 支持按「用户 ID」聚合多会话记忆，或按群组共享记忆。                         |
| O2  | 选择性 retain           | 仅对特定会话类型或关键词触发写入，降低写入量与成本。                          |
| O3  | 使用 Hindsight reflect | 对需要深度推理的场景，可选调用 reflect 替代或补充 recall。               |
| O4  | 异步 Hindsight 客户端     | 若 hindsight-client 提供 aretain/arecall，改为异步调用减少线程占用。 |


---

## 5. 非功能需求


| 类型    | 需求                                                                                                     |
| ----- | ------------------------------------------------------------------------------------------------------ |
| 兼容性   | AstrBot 版本 >= 4.16 且 < 5；Python 与 AstrBot 一致（建议 3.10+）；hindsight-client >= 0.4.0。                      |
| 性能    | retain/recall 通过 asyncio.to_thread 调用同步客户端，不阻塞事件循环；单次请求增加一次 HTTP 往返，可通过 recall_budget/max_tokens 控制耗时。 |
| 可维护性  | 使用 AstrBot 官方 logger；配置与逻辑分离；文档覆盖架构、设计、部署、开发、接口与数据结构。                                                  |
| 安全与隐私 | 不在插件内持久化用户内容；记忆存储在用户自管的 Hindsight 服务中；按会话隔离，不跨会话泄露。                                                    |


---

## 6. 约束与依赖

- **依赖**：AstrBot（含 OnLLMRequestEvent、ProviderRequest）、Hindsight 服务（已单独部署）、hindsight-client。  
- **不包含**：不内置或分发 Hindsight 服务；不提供独立 HTTP API；不实现数据库或本地持久化。  
- **集成方式**：仅通过 OnLLMRequestEvent 钩子读取/修改 ProviderRequest，不修改 AstrBot 核心代码。

---

## 7. 范围与边界

### 7.1 在范围内

- 在每次 LLM 请求前执行 retain → recall → 注入 system 消息。  
- 配置项：启用、Hindsight 地址、超时、召回参数、记忆提示词模板、retain 的 context。  
- 按会话（unified_msg_origin）隔离的 memory bank。  
- 错误处理与日志；部署与开发文档；接口与数据结构说明。

### 7.2 不在范围内

- Hindsight 服务本身的部署、运维与高可用（由用户自行保障）。  
- 记忆内容的编辑、删除、导出或可视化（由 Hindsight 或其 UI 提供）。  
- 除「请求前注入记忆」以外的对话能力（如新指令、新工具）。  
- 多 AstrBot 实例共享同一 Hindsight 时的协调策略（当前按会话隔离即可）。

---

## 8. 文档与交付物


| 交付物    | 说明                                                       |
| ------ | -------------------------------------------------------- |
| 插件代码   | main.py、metadata.yaml、requirements.txt、_conf_schema.json |
| 架构文档   | architecture.md                                          |
| 设计文档   | design.md                                                |
| 部署指导   | deployment.md（含调试环境 6185/8888）                           |
| 开发流程   | development.md                                           |
| 接口文档   | api.md                                                   |
| 数据结构文档 | data-structures.md                                       |
| PRD    | 本文档（PRD.md）                                              |


---

## 9. 参考

- [AstrBot](https://github.com/AstrBotDevs/AstrBot)  
- [Hindsight](https://github.com/vectorize-io/hindsight)  
- 本仓库 [docs/](./README.md) 下的各文档

