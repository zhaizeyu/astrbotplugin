# AstrBot Hindsight 长期记忆插件 - 开发流程文档

本文面向需要修改或扩展本插件的开发者，说明推荐开发环境、日常流程与调试方式。调试环境：**AstrBot** `http://localhost:6185`，**Hindsight** `http://localhost:8888`。

---

## 1. 环境准备

### 1.1 必备

- **AstrBot**：可本地运行（源码或 uv 安装），版本 >= 4.16。
- **Hindsight**：本地或远程可访问，调试时常用 `http://localhost:8888`。
- **Python**：与 AstrBot 一致（建议 3.10+）。
- **编辑器**：任意；建议使用 Ruff 做格式与检查。

### 1.2 克隆与目录结构

```bash
# 克隆 AstrBot 本体（若尚未有）
git clone https://github.com/AstrBotDevs/AstrBot
cd AstrBot

# 插件放在 data/plugins 下（开发时可直接用当前仓库的插件目录复制或软链）
mkdir -p data/plugins
# 将 astrbot_plugin_hindsight_memory 放到 data/plugins/ 下
```

开发时目录示例：

```
AstrBot/
├── astrbot/           # 本体
├── data/
│   └── plugins/
│       └── astrbot_plugin_hindsight_memory/   # 本插件
│           ├── main.py
│           ├── metadata.yaml
│           ├── requirements.txt
│           └── _conf_schema.json
└── ...
```

---

## 2. 依赖安装

在 AstrBot 使用的 Python 环境中：

```bash
pip install -r data/plugins/astrbot_plugin_hindsight_memory/requirements.txt
# 或
pip install hindsight-client>=0.4.0
```

如需按 AstrBot 规范做代码检查：

```bash
pip install ruff
# 在插件目录
ruff check astrbot_plugin_hindsight_memory/
ruff format astrbot_plugin_hindsight_memory/
```

---

## 3. 日常开发流程

### 3.1 启动依赖服务

1. **启动 Hindsight**（若本地调试）  
   确保 `http://localhost:8888` 可用（参见 [deployment.md](./deployment.md)）。

2. **启动 AstrBot**  
   例如：
   ```bash
   # 源码
   python main.py
   # 或 uv
   astrbot run
   ```

3. 打开 WebUI：**http://localhost:6185**，确认插件已启用且 **Hindsight API 地址** 为 `http://localhost:8888`。

### 3.2 修改代码后重载

- 修改 `main.py` 或配置后，**无需重启 AstrBot**。
- 在 WebUI **插件管理** 中找到本插件，点击 **重载插件**。
- 若重载失败，查看管理页错误信息或控制台日志，修正后再次重载。

### 3.3 修改配置结构

- 修改 `_conf_schema.json` 后，需重载插件；新增字段会在 WebUI 配置页展示（若 AstrBot 支持该 schema）。
- 默认值在 `main.py` 的 `__init__` 中也有兜底，两者可保持一致便于文档与行为一致。

---

## 4. 调试方式

### 4.1 日志

- 使用 AstrBot 提供的 logger：`from astrbot.api import logger`。
- 插件内已使用 `logger.info` / `logger.warning` / `logger.exception`，可在 AstrBot 日志输出中查看：
  - 插件加载：`hindsight_memory: 已加载，base_url=..., enabled=...`
  - retain/recall 失败：`hindsight_memory: retain 失败 ...` / `recall 失败 ...`

### 4.2 断点调试

- 在 IDE 中对 AstrBot 主进程设断点（如对 `main.py` 的 `on_req_llm` 或 `_retain`/`_recall`）。
- 用 WebUI 或接入平台发起对话，触发 LLM 请求即可命中 `on_req_llm`。

### 4.3 单独测 Hindsight

在不启动 AstrBot 的情况下验证 Hindsight 与客户端：

```bash
python -c "
from hindsight_client import Hindsight
c = Hindsight(base_url='http://localhost:8888')
c.retain(bank_id='test', content='用户: 我喜欢编程')
r = c.recall(bank_id='test', query='用户喜欢什么')
print(r)
"
```

### 4.4 关闭记忆逻辑

- 在 WebUI 配置中将 **启用插件** 关闭，或把 `enabled` 设为 `false`，可保留插件加载但不执行 retain/recall/注入，便于对比行为。

---

## 5. 提交流程建议

1. **代码风格**：提交前在插件目录执行 `ruff check`、`ruff format`。
2. **版本与元数据**：修改行为或配置时，同步更新 `metadata.yaml` 的 `version` 与 `display_name`/`description`（如需要）。
3. **文档**：若新增配置项或接口，请同步更新：
   - [api.md](./api.md) 接口文档
   - [data-structures.md](./data-structures.md) 数据结构文档（若涉及配置或消息结构）

---

## 6. 常见问题

| 现象 | 建议 |
|------|------|
| 重载后报 ModuleNotFoundError | 确认当前 AstrBot 进程的 Python 环境中已 `pip install hindsight-client`。 |
| 无记忆效果 | 确认 Hindsight 可访问、配置中 base_url 正确、同一会话下多轮对话后再问相关话题。 |
| 请求变慢 | recall 会增加一次 HTTP 请求；可适当降低 `recall_budget` 或 `recall_max_tokens`。 |
| 想临时禁用 | 在 WebUI 中关闭「启用插件」或设置 `enabled: false`。 |

---

## 7. 参考文档

- [deployment.md](./deployment.md) - 部署与配置
- [api.md](./api.md) - 插件接口与 Hindsight 调用
- [data-structures.md](./data-structures.md) - 配置与消息数据结构
