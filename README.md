# Hindsight 长期记忆

**版本**: 0.1.0 · **AstrBot** >= 4.16

基于 [Hindsight](https://github.com/vectorize-io/hindsight) 的 AstrBot 长期记忆插件。在每次请求大模型前，自动将当前对话写入 Hindsight（retain）、召回相关长期记忆（recall），并注入到多轮对话中，使回复具备跨会话记忆能力。

## 要求

- AstrBot >= 4.16
- 已部署并可访问的 **Hindsight 服务**（如 `http://localhost:8888`）
- 依赖：`hindsight-client>=0.4.0`（安装/上传插件时由 AstrBot 或手动 pip 安装）

## 安装

- **WebUI**：插件管理 → 安装插件 → 从文件安装，选择本插件的 `.zip`（zip 内需包含 `astrbot_plugin_hindsight_memory` 目录及 `main.py`、`metadata.yaml`、`requirements.txt`、`_conf_schema.json`）。
- **本地/容器**：将本目录放到 AstrBot 的 `data/plugins/astrbot_plugin_hindsight_memory/`，并在对应 Python 环境中执行 `pip install -r requirements.txt`（容器内可用 `docker exec ... pip install -r /AstrBot/data/plugins/astrbot_plugin_hindsight_memory/requirements.txt`）。

## 配置

在 AstrBot WebUI 的插件配置中：

| 配置项 | 说明 | 默认 |
|--------|------|------|
| 启用插件 | 是否启用记忆逻辑 | 是 |
| Hindsight API 地址 | 服务 base_url，如 `http://localhost:8888` | http://localhost:8888 |
| 请求超时(秒) | 调用 Hindsight 的超时时间 | 30 |
| 召回预算 | 检索深度：low / mid / high | mid |
| 召回最大 token 数 | 单次 recall 返回长度上限 | 2048 |
| 长期记忆系统提示词 | 注入模板，`{memory}` 会被替换为召回内容 | 见配置页 |
| 存入记忆时的上下文标签 | retain 的 context 字段 | astrbot_chat |
| 图片长期记忆 | 是否将对话中的图片通过 Hindsight files/retain 写入记忆（仅内联 base64 图） | 是 |
| 图片解析器 | 图片 retain 使用的解析器（如 iris、default），留空用服务端默认 | 空 |
| 参与 retain 的消息条数 | 文本与图片共用的最近消息条数 | 6 |

**注意**：若 AstrBot 运行在 Docker 内、Hindsight 在宿主机，API 地址需填宿主机 IP（如 `http://172.17.0.1:8888`），不能填 `localhost`。

### 图片长期记忆

- 开启「图片长期记忆」后，插件会从最近 N 条消息中提取**内联图片**（`data:image/...;base64,...` 或 Gemini `inlineData`），并调用 Hindsight 的 **files/retain** 上传。Hindsight 会对图片做 OCR/视觉抽取，结果作为记忆参与后续 recall。
- 仅处理内联 base64 图片，**不拉取远程 URL**，避免超时与隐私问题。
- 需 Hindsight 服务端支持 files/retain 接口；若客户端版本无 `retain_file`，图片记忆会静默跳过，仅保留文本侧「附有一张图片」的标记。

## 调试与日志

- **日志位置**：本地运行为终端/控制台；Docker 为 `docker logs -f astrbot`（或 `docker compose logs -f`）。
- **过滤本插件**：所有插件日志带前缀 `hindsight_memory:`，例如：  
  `docker logs -f astrbot 2>&1 | grep hindsight_memory`
- **常见条目**：加载成功 `已加载，base_url=..., enabled=...`；失败时 `retain 失败` / `recall 失败` / `创建 Hindsight 客户端失败`。成功执行 retain/recall 时不打日志。
- 更多说明见 [部署文档 - 调试与查看插件日志](docs/deployment.md#6-部署后如何调试与查看插件日志)。

## 文档

更多说明（架构、设计、部署、开发、接口、数据结构）见本目录下 [docs/](docs/README.md)。

## 从链接安装（代码仓）

本仓库按 AstrBot「从链接安装」要求组织：**仓库根目录即插件根目录**，根目录包含 `main.py`、`metadata.yaml`、`requirements.txt`、`_conf_schema.json`、`README.md`，以及 `docs/`。

- **从链接安装**：在 AstrBot WebUI → 插件管理 → 安装插件 → **从链接安装**，填写本仓库地址（如 `https://github.com/你的用户名/astrbot_plugin_hindsight_memory`）。克隆后 AstrBot 会将仓库根目录识别为插件目录（目录名 = 仓库名，建议仓库名为 `astrbot_plugin_hindsight_memory`）。
- **提交到代码仓**：以本目录（`astrbot_plugin_hindsight_memory`）为 **Git 仓库根目录** 初始化并推送到 GitHub，保证根目录下直接有 `main.py`、`metadata.yaml` 等，不要多一层父目录。
