# 如何提交到代码仓并支持「从链接安装」

AstrBot 从链接安装时，会克隆你提供的仓库到 `data/plugins/<仓库名>/`，并**要求仓库根目录直接包含 `main.py`**。因此需要以**本目录**为仓库根目录提交，而不是以包含本目录的父文件夹为根。

## 推荐做法：以本目录为独立 Git 仓库

1. **用本目录作为仓库根**（不要以 `astrbotplugin` 等父目录为仓库根）：
   ```bash
   cd astrbot_plugin_hindsight_memory
   git init
   git add .
   git commit -m "Initial commit: Hindsight 长期记忆插件"
   ```

2. **在 GitHub 上新建仓库**，名称建议为 `astrbot_plugin_hindsight_memory`（与插件目录名一致），不要勾选「Add README」（避免与本地冲突）。

3. **关联并推送**：
   ```bash
   git remote add origin https://github.com/你的用户名/astrbot_plugin_hindsight_memory.git
   git branch -M main
   git push -u origin main
   ```

4. **从链接安装**：在 AstrBot WebUI → 插件管理 → 安装插件 → 从链接安装，填写：
   ```
   https://github.com/你的用户名/astrbot_plugin_hindsight_memory
   ```

## 当前目录结构（应符合以下布局）

```
astrbot_plugin_hindsight_memory/   ← 仓库根目录
├── main.py
├── metadata.yaml
├── requirements.txt
├── _conf_schema.json
├── README.md
├── INSTALL.md
├── SUBMIT.md
├── .gitignore
└── docs/
    ├── README.md
    ├── architecture.md
    ├── design.md
    ├── deployment.md
    ├── development.md
    ├── api.md
    ├── data-structures.md
    └── PRD.md
```

这样克隆后 `data/plugins/astrbot_plugin_hindsight_memory/main.py` 存在，AstrBot 即可正确识别。

## 若当前仓库是「父目录」

若你现在的 Git 仓库是包含 `astrbot_plugin_hindsight_memory` 的父目录（例如 `astrbotplugin`），则有两种方式：

- **方式 A**：新建一个**只包含插件**的仓库，把 `astrbot_plugin_hindsight_memory` 目录下的所有文件作为新仓库根目录提交（如上所示）。
- **方式 B**：在父仓库中保留当前结构，安装时使用「从文件安装」并上传将 `astrbot_plugin_hindsight_memory` 打成的 zip，或手动复制该目录到 `data/plugins/`。
