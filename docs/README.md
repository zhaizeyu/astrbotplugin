# AstrBot Hindsight 长期记忆 - 文档索引

本目录包含 **AstrBot Hindsight 长期记忆插件** 的架构、设计、部署、开发与接口文档。

## 文档列表

| 文档 | 说明 |
|------|------|
| [architecture.md](./architecture.md) | **架构文档**：系统架构、组件职责、数据流、与 AstrBot / Hindsight 的集成点 |
| [design.md](./design.md) | **设计文档**：功能设计（retain/recall/注入）、配置项、错误处理与扩展方向 |
| [deployment.md](./deployment.md) | **部署指导**：安装步骤、WebUI 配置、验证与调试环境（如 AstrBot 6185 / Hindsight 8888） |
| [development.md](./development.md) | **开发流程**：环境准备、依赖安装、修改与重载、调试方式、提交流程 |
| [api.md](./api.md) | **接口文档**：插件钩子、配置接口、对 Hindsight 的 retain/recall 调用说明 |
| [data-structures.md](./data-structures.md) | **数据结构文档**：配置 Schema、ProviderRequest/contexts、注入消息、retain 内容与 recall 返回值格式 |
| [PRD.md](./PRD.md) | **产品需求文档（PRD）**：产品概述、目标、用户、功能/非功能需求、范围与交付物总结 |

## 调试环境速查

- **AstrBot WebUI**：http://localhost:6185  
- **Hindsight API**：http://localhost:8888（插件配置中的「Hindsight API 地址」填此即可）

## 插件概述

- **作用**：在每次请求大模型前，将当前对话写入 [Hindsight](https://github.com/vectorize-io/hindsight)（retain），并根据当前问题召回长期记忆（recall），插入到多轮对话的 system 消息中再发送给 LLM。  
- **调用方式**：使用 Hindsight 官方 Python 客户端 `from hindsight_client import Hindsight`，通过 HTTP 访问独立部署的 Hindsight 服务。  
- **部署要求**：需单独部署 Hindsight 服务（如 Docker），并在插件配置中填写 `base_url`。

## 快速参考

- 插件目录：`astrbot_plugin_hindsight_memory/`  
- 依赖：`hindsight-client>=0.4.0`，AstrBot >= 4.16  
- 配置：见插件内 `_conf_schema.json` 及 [design.md](./design.md) 中的配置表。

