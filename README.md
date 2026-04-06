# ST-Manager

<div align="center">

**SillyTavern 资源可视化管理工具**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

功能强大 • 界面美观 • 操作便捷

</div>

<!-- 主界面效果图 -->
<p align="center">
  <img src="docs/screenshots/hero.png" alt="ST-Manager 主界面" width="900">
</p>

---

## ✨ 功能亮点

<table>
<tr>
<td width="50%">

### 🎴 角色卡管理

- PNG / JSON 格式角色卡浏览与编辑
- 标签分类、收藏、批量操作
- 高级筛选工作台，支持时间 / Token / 标签组合筛选
- 隔离分类与 Bundle 多版本管理
- 一键发送到 SillyTavern
- Bundle 多版本管理

</td>
<td width="50%">

<!-- 角色卡网格 -->
<img src="docs/screenshots/feature-cards.png" alt="角色卡网格" width="100%">

</td>
</tr>
<tr>
<td width="50%">

<!-- 聊天阅读器 -->
<img src="docs/screenshots/feature-chats.png" alt="聊天记录管理" width="100%">

</td>
<td width="50%">

### 💬 聊天记录管理

- `.jsonl` 聊天导入、角色绑定、全文检索
- 沉浸式三栏阅读器，楼层导航与收藏
- 楼层编辑时可对照原文消息，支持批量查找替换
- 整页实例模式运行前端片段，头部自动隐藏更顺滑

</td>
</tr>
<tr>
<td width="50%">

### 📚 世界书管理

- 全局 / 资源目录 / 内嵌世界书统一管理
- 分类管理、拖拽归类、本地备注
- 在线编辑、剪切板、一键新建
- 版本时光机：快照、回滚、可视化对比
- 条目级独立历史版本

</td>
<td width="50%">

<!-- 世界书 -->
<img src="docs/screenshots/feature-wi.png" alt="世界书管理" width="100%">

</td>
</tr>
<tr>
<td width="50%">

<!-- 预设 -->
<img src="docs/screenshots/feature-presets.png" alt="预设管理" width="100%">

</td>
<td width="50%">

### 📝 预设管理

- 拖拽上传 JSON 预设文件
- 支持分类整理与拖拽归类
- 三栏详情阅读器（采样器 / 参数 / Prompts）
- Prompts 筛选（启用 / 禁用 / 全部）
- 正则脚本与 ST 脚本扩展集成

</td>
</tr>
<tr>
<td width="50%">

### 🤖 自动化规则引擎

- 基于条件的自动化任务执行
- 支持规则顺序调整、条件组 / 动作排序
- 支持收藏、标签管理、论坛标签抓取
- 模板化文件重命名、分类拆分为标签
- 标签合并（同义标签归并）
- Discord 论坛帖子标签自动同步

</td>
<td width="50%">

<!-- 自动化 -->
<img src="docs/screenshots/feature-automation.png" alt="自动化规则引擎" width="100%">

</td>
</tr>
<tr>
<td width="50%">

<!-- 脚本管理 -->
<img src="docs/screenshots/feature-scripts.png" alt="脚本管理" width="100%">

</td>
<td width="50%">

### 🛠️ 脚本与扩展

- 正则脚本可视化管理
- Tavern Helper 脚本运行 / 重载 / 停止
- 快速回复模板管理
- 运行时检查器统一状态查看

</td>
</tr>
</table>

### 更多特性

- 🔄 **实时同步** — 文件系统自动监听，变更即时同步到数据库
- 🎨 **暗色 / 亮色主题** — 现代化响应式 UI，桌面端与移动端自适应
- 📱 **移动端深度适配** — 抽屉式导航、底部操作栏、触控友好的交互控件，手机浏览器即可高效管理
- 🔍 **智能搜索** — 名称、标签、创作者等多维度搜索，支持搜索范围控制
- 🏷️ **标签系统** — 分类管理、颜色 / 透明度、自定义筛选、拖拽排序与标签治理
- 🖼️ **个性化壁纸** — 内置默认背景，支持自定义壁纸、遮罩浓度与模糊度
- ⚡ **启动更省心** — 首次运行自动生成 `config.json`，Docker 首次启动也可自动补齐基础配置
- 📦 **酒馆资源同步** — 从本地 SillyTavern 一键同步角色卡、聊天、世界书、预设等

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- pip 包管理器

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Dadihu123/ST-Manager.git
cd ST-Manager

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动
python app.py
```

首次本地运行时，如果仓库根目录下不存在 `config.json`，程序会自动创建一个默认配置文件。

程序启动后会按当前实际监听地址自动打开浏览器；如果服务监听的是 `0.0.0.0`，则浏览器会自动访问对应端口的 `127.0.0.1`。

如需仅对当前这次启动临时覆盖监听地址或端口，可使用：

```bash
python app.py --host 127.0.0.1 --port 5000
```

`--host` 和 `--port` 只影响当前进程，不会写回 `config.json`。

### Docker 部署

```bash
docker-compose up -d
# 访问 http://localhost:5000
```

首次使用 Docker Compose 启动时，如果宿主机项目根目录下不存在 `./config.json`，会先自动生成该文件，再启动主服务。

Docker 首次自动生成的配置默认会把 `host` 写为 `0.0.0.0`，便于容器对外监听。

---

## 📸 界面展示

<!-- 截图展示区 -->

<p align="center">
  <img src="docs/screenshots/gallery-cards-detail.png" alt="角色卡详情页" width="420">&nbsp;
  <img src="docs/screenshots/gallery-chat-reader.png" alt="聊天阅读器" width="420">
</p>
<p align="center">
  <img src="docs/screenshots/gallery-wi-editor.png" alt="世界书编辑器" width="420">&nbsp;
  <img src="docs/screenshots/gallery-preset-detail.png" alt="预设详情" width="420">
</p>
<p align="center">
  <img src="docs/screenshots/gallery-automation.png" alt="自动化规则" width="420">&nbsp;
  <img src="docs/screenshots/gallery-settings.png" alt="设置界面" width="420">
</p>

### 📱 移动端适配

所有页面均针对移动端进行了深度优化——抽屉式侧栏导航、底部操作栏、触控友好的卡片与列表交互，手机浏览器即可完成角色卡管理、聊天阅读、世界书编辑等全部操作。

<p align="center">
  <img src="docs/screenshots/mobile-cards.png" alt="移动端角色卡网格" width="260">&nbsp;
  <img src="docs/screenshots/mobile-chat-reader.png" alt="移动端聊天阅读器" width="260">&nbsp;
  <img src="docs/screenshots/mobile-sidebar.png" alt="移动端抽屉导航" width="260">
</p>
<p align="center">
  <img src="docs/screenshots/mobile-card-detail.png" alt="移动端角色卡详情" width="260">&nbsp;
  <img src="docs/screenshots/mobile-wi-editor.png" alt="移动端世界书编辑" width="260">&nbsp;
  <img src="docs/screenshots/mobile-settings.png" alt="移动端设置" width="260">
</p>

---

## ⚙️ 配置速览

程序首次运行自动生成 `config.json`。本地直接运行时会在项目根目录生成该文件；Docker Compose 首次启动时会先在宿主机项目根目录生成 `./config.json`。本地默认监听 `127.0.0.1:5000`；Docker 首次自动生成时默认监听 `0.0.0.0:5000`。常用配置项：

| 配置项          | 说明                                 | 默认值                  |
| --------------- | ------------------------------------ | ----------------------- |
| `host`          | 监听地址                             | `127.0.0.1`             |
| `port`          | 监听端口                             | `5000`                  |
| `st_url`        | SillyTavern 地址                     | `http://127.0.0.1:8000` |
| `st_data_dir`   | SillyTavern 数据目录（留空自动探测） | `""`                    |
| `auth_username` | 公网访问用户名（需与密码同时设置）   | `""`                    |

临时启动覆盖示例：`python app.py --host 0.0.0.0 --port 6000`。这类命令行参数只影响当前进程，不会写回 `config.json`。

完整配置说明请参阅 → [docs/CONFIG.md](docs/CONFIG.md)

---

## 📖 相关文档

| 文档                            | 内容                                              |
| ------------------------------- | ------------------------------------------------- |
| [配置说明](docs/CONFIG.md)      | 完整配置项、自动生成规则、Discord 认证、身份验证  |
| [API 文档](docs/API.md)         | REST API 接口说明（角色卡、聊天、世界书、预设等） |
| [开发指南](docs/DEVELOPMENT.md) | 项目结构、代码风格、数据库结构、测试              |

---

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送并开启 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE)。

---

## 🙏 致谢

- [SillyTavern](https://github.com/SillyTavern/SillyTavern) — 本项目管理的目标程序
- [Flask](https://flask.palletsprojects.com/) — Web 框架
- [Tailwind CSS](https://tailwindcss.com/) — CSS 框架
- [Alpine.js](https://alpinejs.dev/) — 轻量级 JavaScript 框架

---

## 📮 联系方式

- 问题反馈：[GitHub Issues](https://github.com/Dadihu123/ST-Manager/issues)
- 功能建议：[Discord 类脑](https://discord.com/channels/1134557553011998840/1448353646596325578)

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐️ Star 支持一下！**

Made with ❤️ by ST-Manager Team

</div>
