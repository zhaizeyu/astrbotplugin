# AstrBot Hindsight 长期记忆插件 - 部署指导

本文说明如何在已部署的 AstrBot 与 Hindsight 环境中安装、配置并启用本插件。调试环境示例：**AstrBot WebUI** `http://localhost:6185`，**Hindsight API** `http://localhost:8888`。

---

## 1. 环境要求

| 组件 | 要求 |
|------|------|
| AstrBot | 已运行，版本 >= 4.16且 < 5 |
| Hindsight 服务 | 已部署并可访问（如 `http://localhost:8888`） |
| Python | 与 AstrBot 一致（建议 3.10+） |

---

## 2. 部署 Hindsight（若尚未部署）

若 `http://localhost:8888` 已可用可跳过本节。

**Docker 单机示例：**

```bash
export OPENAI_API_KEY=sk-xxx   # 或设置 HINDSIGHT 所需的其他 LLM Key

docker run --rm -it -p 8888:8888 -p 9999:9999 \
  -e HINDSIGHT_API_LLM_API_KEY=$OPENAI_API_KEY \
  -v $HOME/.hindsight-docker:/home/hindsight/.pg0 \
  ghcr.io/vectorize-io/hindsight:latest
```

- API: `http://localhost:8888`
- UI: `http://localhost:9999`

---

## 3. 安装插件到 AstrBot

### 3.1 方式一：放入 data/plugins（推荐本地调试）

1. 定位 AstrBot 的插件目录，一般为：
   - 源码运行：`<AstrBot 项目根目录>/data/plugins/`
   - uv 安装：`<uv 环境目录>/data/plugins/` 或 用户目录下 AstrBot 数据目录中的 `data/plugins/`

2. 将本仓库中的 **整个插件目录** 放入该目录下，保证结构为：
   ```
   data/plugins/astrbot_plugin_hindsight_memory/
   ├── main.py
   ├── metadata.yaml
   ├── requirements.txt
   └── _conf_schema.json
   ```

3. 安装插件依赖（在 AstrBot 使用的 Python 环境中执行）：
   ```bash
   pip install -r data/plugins/astrbot_plugin_hindsight_memory/requirements.txt
   ```
   或：
   ```bash
   pip install hindsight-client>=0.4.0
   ```

### 3.2 方式二：从 Git 克隆到 data/plugins

```bash
cd <AstrBot 根目录或 data/plugins 所在目录>
mkdir -p data/plugins
cd data/plugins
git clone <本插件仓库地址> astrbot_plugin_hindsight_memory
pip install -r astrbot_plugin_hindsight_memory/requirements.txt
```

### 3.3 容器模式部署 AstrBot 时安装插件

AstrBot 使用 Docker 时，通过**挂载 data 目录**持久化配置与数据，插件需放在该目录下，容器内才能加载。

#### 步骤一：确认 data 挂载

- **Docker Compose**（AstrBot 官方仓库）：
  ```bash
  git clone https://github.com/AstrBotDevs/AstrBot
  cd AstrBot
  docker compose up -d
  ```
  一般会挂载 `./data` 到容器内 `/AstrBot/data`（以实际 `compose.yml` 为准）。

- **单容器 run**：
  ```bash
  mkdir -p astrbot/data
  docker run -itd -p 6185:6185 -p 6199:6199 \
    -v $PWD/data:/AstrBot/data \
    -v /etc/localtime:/etc/localtime:ro \
    --name astrbot soulter/astrbot:latest
  ```
  宿主机 `./data` 即容器内 `/AstrBot/data`。

#### 步骤二：在宿主机放入插件

在**宿主机**上操作（即挂载的 `data` 所在目录）：

```bash
# 进入挂载的 data 目录（例如 AstrBot 项目下的 data，或上面 astrbot/data）
cd /path/to/astrbot/data
mkdir -p plugins
cd plugins

# 方式 A：直接复制本插件目录到 plugins 下
cp -r /path/to/astrbot_plugin_hindsight_memory .

# 方式 B：从 Git 克隆
git clone <本插件仓库地址> astrbot_plugin_hindsight_memory
```

保证宿主机上存在目录：`data/plugins/astrbot_plugin_hindsight_memory/`，且内含 `main.py`、`metadata.yaml`、`requirements.txt`、`_conf_schema.json`。容器内对应路径为 `/AstrBot/data/plugins/astrbot_plugin_hindsight_memory/`。

#### 步骤三：安装插件依赖（容器内）

官方镜像可能不会在启动时自动安装每个插件的 `requirements.txt`，需要**在容器内**安装本插件依赖：

```bash
docker exec -it astrbot pip install -r /AstrBot/data/plugins/astrbot_plugin_hindsight_memory/requirements.txt
```

或只安装包名：

```bash
docker exec -it astrbot pip install hindsight-client>=0.4.0
```

若你的 AstrBot 版本支持「加载插件时自动检查并安装 requirements」，也可在 WebUI 中启用/重载插件后观察是否仍报 `ModuleNotFoundError`；若报错再执行上述 `docker exec pip install`。

#### 步骤四：重启容器或重载插件

- **重启容器**（推荐，确保依赖被加载）：
  ```bash
  docker restart astrbot
  ```
- 或仅**重载插件**：打开 WebUI → 插件管理 → 找到本插件 → 重载插件。

#### Hindsight 地址（容器内访问）

- **Hindsight 在宿主机**（如 `docker run ... -p 8888:8888`）：从 AstrBot **容器内**访问宿主机需用宿主机 IP，不能用 `localhost`。Linux 可用 `host.docker.internal`（部分环境）或宿主机实际 IP（如 `172.17.0.1`）。插件配置中 **Hindsight API 地址** 填：`http://宿主机IP:8888`。
- **Hindsight 与 AstrBot 在同一 Docker Compose**：为 Hindsight 定义服务名（如 `hindsight`），同一 compose 网络内 AstrBot 可填：`http://hindsight:8888`。
- **Hindsight 与 AstrBot 同机、AstrBot 用 host 网络**：若 AstrBot 容器使用 `--network host`，可填 `http://localhost:8888`。

完成后在 WebUI 中启用插件并填写上述 Hindsight 地址即可。

---

## 4. 在 WebUI 中启用与配置

1. 打开 AstrBot WebUI（调试环境示例：**http://localhost:6185**）。

2. 进入 **插件管理**（或「插件 / Plugins」），找到 **Hindsight 长期记忆**（或 `hindsight_memory`）。

3. **启用插件**：若未启用，点击启用。

4. **配置**（必填/常用项）：
   - **Hindsight API 地址**：`http://localhost:8888`（与当前 Hindsight 服务一致，勿加尾部路径）。
   - **启用插件**：勾选。
   - 其余可选：
     - **请求超时(秒)**：默认 30。
     - **召回预算**：`low` / `mid` / `high`，默认 `mid`。
     - **召回最大 token 数**：默认 2048。
     - **长期记忆系统提示词**：使用 `{memory}` 占位符，会替换为召回内容。
     - **存入记忆时的上下文标签**：默认 `astrbot_chat`。

5. 保存配置后，可点击 **重载插件** 使配置生效（无需重启 AstrBot）。

---

## 5. 验证部署

1. **Hindsight 连通性**（可选）：浏览器或 curl 访问 `http://localhost:8888`，确认有正常响应（如 404 或健康检查端点均可，只要说明服务在监听）。

2. **AstrBot 侧**：
   - 在 WebUI 中与机器人发起对话（使用已接入的 LLM）。
   - 多轮对话后，问一个与之前内容相关的问题，观察回复是否带有「长期记忆」中的信息。
   - 若启用了 AstrBot 日志，可查看是否有 `hindsight_memory: 已加载，base_url=...` 及 retain/recall 相关日志。

3. **故障排查**：
   - 插件未生效：确认插件已启用、依赖已安装（`pip list | grep hindsight`）、配置中 `base_url` 为 `http://localhost:8888`。
   - 无记忆效果：确认 Hindsight 服务正常、同一会话多轮对话后再提问、查看 AstrBot 日志中是否有 retain/recall 报错。

---

## 6. 部署后如何调试与查看插件日志

### 6.1 日志输出在哪里

插件使用 AstrBot 的 logger（`astrbot.api.logger`），**输出目标与 AstrBot 一致**：若 AstrBot 配置了写入 `astrbot.log`（或其它日志文件），本插件的 `hindsight_memory:` 日志也会写入同一文件；若只输出到控制台，则插件日志也只在控制台。

| 部署方式 | 查看方式 |
|----------|----------|
| **本地/源码运行** | AstrBot 进程的标准输出（终端或 IDE 控制台）；若配置了日志文件则同时/仅写该文件 |
| **Docker 容器** | `docker logs -f astrbot`（容器名以你实际为准），或 `docker compose logs -f`；若 AstrBot 在容器内配置了写文件，则需到容器内或挂载的 data 目录下找该文件（如 `astrbot.log`） |
| **写入文件** | 在 WebUI「系统配置」中开启 **启用文件日志**、路径填 `logs/astrbot.log` 时，日志会写入 **data/logs/astrbot.log**（相对路径以 data 为基准）。插件日志与 AstrBot 同级，均写入该文件；控制台日志级别为 INFO 时，插件的 INFO 日志会一并写入 |

### 6.2 本插件会打哪些日志

插件通过 AstrBot 的 logger 输出，所有条目均带前缀 `hindsight_memory:`，便于过滤：

| 级别 | 内容示例 | 含义 |
|------|----------|------|
| INFO | `hindsight_memory: 已加载，base_url=..., enabled=...` | 插件加载成功，当前 base_url 与启用状态 |
| INFO | `hindsight_memory: 插件已卸载` | 插件被禁用或重载时触发 terminate |
| WARNING | `hindsight_memory: 未安装 hindsight-client，...` | 未安装依赖，记忆逻辑不执行 |
| WARNING | `hindsight_memory: retain 失败 (bank_id=...): ...` | 写入 Hindsight 失败（网络/服务/参数） |
| WARNING | `hindsight_memory: recall 失败 (bank_id=...): ...` | 召回 Hindsight 失败 |
| EXCEPTION | `hindsight_memory: 创建 Hindsight 客户端失败: ...` | 初始化客户端异常（如 base_url 不可达） |
| DEBUG | `hindsight_memory: 关闭客户端时忽略: ...` | 卸载时关闭客户端时的非关键异常（可忽略） |

成功执行 retain/recall 时插件**不**打日志，以减少刷屏；只有异常或启停时才有输出。

### 6.3 如何看日志（命令示例）

**只看本插件相关：**

```bash
# 本地运行时（终端已在前台）
# 直接看控制台，或重定向后过滤：
python main.py 2>&1 | grep hindsight_memory

# Docker
docker logs -f astrbot 2>&1 | grep hindsight_memory
# 或最近 500 行再过滤
docker logs --tail 500 astrbot 2>&1 | grep hindsight_memory
```

**看完整 AstrBot 日志（含其它模块）：**

```bash
docker logs -f astrbot
# 或
docker compose logs -f
```

### 6.4 简单调试流程

1. **确认插件已加载**：启动或重载后应有一条 `hindsight_memory: 已加载，base_url=..., enabled=...`；若无，检查插件是否启用、依赖是否安装。
2. **触发一次对话**：在 WebUI 或接入平台发一条会走 LLM 的消息。
3. **看是否有报错**：若出现 `retain 失败` 或 `recall 失败`，根据报错信息检查 Hindsight 地址、网络、服务状态；若出现 `创建 Hindsight 客户端失败`，重点检查 `base_url` 与网络。
4. **无日志且无记忆**：可能是 recall 结果为空（尚未有足够记忆）、或插件被关闭（检查配置里「启用插件」）。

### 6.5 提高日志详细度（可选）

- 在插件配置中开启 **debug**（本插件提供的配置项）后，每次 LLM 请求会在 **astrbot.log**（或控制台）中打印提示词存取的详细信息：
  - **存入(retain)**：bank_id、内容长度、内容摘要（前 200 字）；
  - **查询(recall)**：bank_id、本次查询 query 摘要（前 100 字）；
  - **查出(recall)**：返回条数、bank_id、召回内容摘要（前 300 字）。
- 在「系统配置」中启用文件日志且路径为 `logs/astrbot.log` 时，上述 INFO 级别日志会写入 **data/logs/astrbot.log**，便于排查与审计。
- 若需更细的排查，可在插件代码中临时增加 `logger.debug(...)` 并在 AstrBot 侧将日志级别调整为 DEBUG（若 AstrBot 支持配置 log level）。

### 6.6 看不到日志且 9999 记忆库无新 bank/记忆

可能原因与对应处理：

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| astrbot.log / docker logs 都没有输出 | AstrBot 未把日志写到文件或 stdout | 查 AstrBot 文档或 `data/` 下是否有日志配置；Docker 下用 `docker logs -f 容器名` 看是否本就没有任何输出。 |
| 插件加载日志（如「已加载」）也没有 | 插件未加载或未启用 | WebUI 插件列表确认已启用；重载后看是否有报错。 |
| 9999（Hindsight UI）里没有新 bank、没有新记忆 | ① 请求没走到 LLM，钩子未触发<br>② AstrBot 在 Docker 里，base_url 填了 localhost:8888<br>③ retain 失败（网络/地址错误）但日志没看到 | ① 用会真正调用 LLM 的入口发消息（如 Web 聊天且已选模型），再观察<br>② **从容器内访问 Hindsight 必须用宿主机 IP 或服务名**，不能填 `localhost:8888`（容器内 localhost 是容器自己）。改为 `http://宿主机IP:8888` 或同一 compose 下用 `http://hindsight:8888`<br>③ 开启插件 **debug** 配置后重载，再发一条消息，看是否有 `on_req_llm 触发` / `retain 已调用`；若出现 `retain 失败` 则按报错查网络与地址 |

**从容器内自测 Hindsight 是否可达**（将 `宿主机IP` 换成实际 IP，如 `172.17.0.1` 或 host 网络下用 `host.docker.internal`）：

```bash
docker exec -it astrbot sh -c 'wget -q -O- http://宿主机IP:8888 2>&1 | head -1'
# 或
docker exec -it astrbot curl -s -o /dev/null -w "%{http_code}" http://宿主机IP:8888
```

若有 HTTP 状态码或页面片段返回，说明容器能访问 Hindsight；若超时/连接拒绝，说明 base_url 或网络有问题。

**bank_id 是什么**：插件用 `event.unified_msg_origin` 作为 bank_id（如 `webchat:friend:xxx`、`telegram:group:xxx`）。在 Hindsight UI(9999) 里看到的 bank 名称/ID 应与此一致，可在 debug 开启后看日志里的 `bank_id=` 确认。

**报错 `Timeout context manager should be used inside a task`**：说明在子线程中调用了内部使用 asyncio timeout 的代码。插件已改为优先使用 hindsight-client 的异步方法 `aretain`/`arecall`（若存在），请在确保 `hindsight-client>=0.4.0` 后重载插件；若仍报错，请升级到最新版（`pip install -U hindsight-client`）以使用异步接口。

---

## 7. 调试环境速查

| 服务 | 地址 | 说明 |
|------|------|------|
| AstrBot WebUI | http://localhost:6185 | 管理插件、配置、对话 |
| Hindsight API | http://localhost:8888 | 插件通过 `hindsight-client` 调用 |

插件配置中 **Hindsight API 地址** 填：`http://localhost:8888` 即可在该环境下完成部署与调试。部署后调试与查看插件日志的详细说明见 [§6 部署后如何调试与查看插件日志](#6-部署后如何调试与查看插件日志)。
