# 安装方式说明

本插件支持三种安装方式，任选其一即可。

## 1. 从链接安装（推荐，适合从代码仓安装）

AstrBot WebUI → **插件管理** → **安装插件** → **从链接安装**，填写本仓库地址：

```
https://github.com/你的用户名/astrbot_plugin_hindsight_memory
```

或使用 Git 克隆到 AstrBot 的插件目录：

```bash
cd /path/to/AstrBot/data/plugins
git clone https://github.com/你的用户名/astrbot_plugin_hindsight_memory
```

**要求**：仓库根目录必须直接包含 `main.py`、`metadata.yaml`、`requirements.txt`、`_conf_schema.json`、`README.md`（即本仓库结构）。克隆完成后，AstrBot 会将克隆得到的目录名（如 `astrbot_plugin_hindsight_memory`）作为插件目录。依赖会在加载时自动安装或需手动执行 `pip install -r requirements.txt`（见 AstrBot 文档）。

## 2. 从文件安装（zip）

1. 将本仓库打包为 zip（**zip 根目录应为插件目录**，解压后得到 `astrbot_plugin_hindsight_memory/main.py` 等）。
2. WebUI → 插件管理 → 安装插件 → **从文件安装**，选择该 zip。

打包示例（在仓库根目录执行）：

```bash
zip -r astrbot_plugin_hindsight_memory.zip . -x "*.git*" -x "__pycache__/*" -x "*.pyc"
```

## 3. 手动放入 data/plugins

将本仓库克隆或复制到 AstrBot 的 `data/plugins/` 下，保证路径为：

```
data/plugins/astrbot_plugin_hindsight_memory/
├── main.py
├── metadata.yaml
├── requirements.txt
├── _conf_schema.json
├── README.md
└── docs/
```

然后在 AstrBot 的 Python 环境中安装依赖：

```bash
pip install -r data/plugins/astrbot_plugin_hindsight_memory/requirements.txt
```

---

安装后在 WebUI 中启用插件并配置 **Hindsight API 地址**（如 `http://localhost:8888` 或从容器内访问宿主机时的地址）。详见 [docs/deployment.md](docs/deployment.md)。
