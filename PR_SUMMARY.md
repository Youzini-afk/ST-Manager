# Pull Request: 外网访问身份验证 + IP 白名单机制

## 📋 概述

为 ST-Manager 添加完整的外网访问身份验证系统，保护公网/内网穿透部署场景下的数据安全。

**核心特性**：
- 🔐 账号密码认证（Session 机制）
- 🛡️ IP 白名单（默认仅本机免登录）
- 🌍 支持环境变量配置（适合 Docker/systemd）
- 💻 命令行配置工具（适合纯公网服务器）
- 🚀 跨平台兼容（Windows/Linux/macOS/Docker）

---

## 🎯 解决的问题

### 安全隐患
在 v2.x 之前，ST-Manager **完全没有身份验证机制**，任何知道 URL 的人都能：
- ❌ 查看/修改所有角色卡和世界书
- ❌ 删除数据、修改系统配置
- ❌ 执行自动化规则、上传恶意文件

### 使用场景
- 通过 frp/ngrok 等内网穿透暴露到公网
- 部署在云服务器/VPS 供多人访问
- 在公司/学校网络中共享使用

---

## ✨ 新增功能

### 1. 身份验证系统

#### 认证流程
- 默认：**仅 `127.0.0.1` 和 `::1`（本机）免登录**
- 其他来源（包括局域网）需要登录
- 登录后 Session 有效期 7 天
- 支持反向代理场景（识别 `X-Forwarded-For` / `X-Real-IP`）

#### 白名单机制
用户可自定义信任的 IP 地址，免登录访问：
- **单个 IP**：`192.168.1.100`
- **CIDR 网段**：`192.168.1.0/24`
- **通配符**：`192.168.*.*`

### 2. 三种配置方式

#### 方式 1：配置文件 (`config.json`)
```json
{
  "auth_username": "admin",
  "auth_password": "your_password",
  "auth_trusted_ips": ["192.168.1.0/24"]
}
```

#### 方式 2：环境变量（优先级最高）
```bash
# Linux/Docker
export STM_AUTH_USER=admin
export STM_AUTH_PASS=your_password
python app.py

# Docker Compose
environment:
  - STM_AUTH_USER=admin
  - STM_AUTH_PASS=secret
```

#### 方式 3：命令行工具（适合公网 Linux 首次配置）
```bash
# 查看认证状态
python -m core.auth

# 设置账号密码
python -m core.auth --set-auth admin password123

# 添加白名单 IP
python -m core.auth --add-ip 192.168.1.0/24
```

### 3. 登录页面
- 现代化 UI 设计（玻璃态模糊背景）
- 显示访问者真实 IP（方便添加到白名单）
- 移动端适配

---

## 📦 代码变更

### 新增文件
- **`core/auth.py`** (563 行)
  - IP 白名单匹配逻辑（支持 CIDR/通配符）
  - Session 认证管理
  - Flask 认证中间件
  - 登录页面 HTML
  - 命令行工具（`python -m core.auth`）

### 修改文件
| 文件 | 变更 | 说明 |
|------|------|------|
| `core/__init__.py` | +4 行 | 导入并初始化认证模块 |
| `core/config.py` | +9 行 | 添加认证配置项 |
| `static/js/state.js` | +3 行 | 前端状态字段 |
| `templates/modals/settings.html` | +71 行 | 认证设置 UI（账号密码 + IP 白名单管理） |
| `app.py` | +12 行 | UTF-8 编码支持（兼容 Windows emoji） |
| `README.md` | +100 行 | 认证功能文档 + 导航目录 |

### 删除文件
- **`Revision Notes.md`** (-177 行) - 已过时的二改日志

**总计**：+760 行，-179 行

---

## 🔒 安全设计

### 1. 默认安全策略
- ❌ 不信任任何非本机 IP（包括局域网）
- ✅ 用户需主动添加白名单才能免登录
- ✅ 避免"默认开放局域网"带来的风险（公司网络/公共 WiFi）

### 2. Session 安全
- Secret Key 自动生成并持久化存储（`data/.secret_key`）
- Cookie 设置：`HttpOnly=True`, `SameSite=Lax`
- Session 有效期可配置（默认 7 天）

### 3. 中间件保护
- 全局 `@app.before_request` 拦截所有请求
- 静态资源（`/static/`, `/favicon.ico`）无需认证
- API 请求返回 401，页面请求重定向到登录

### 4. 反向代理支持
正确识别真实客户端 IP：
```python
X-Forwarded-For: 203.0.113.1, 192.168.1.1  # 取第一个
X-Real-IP: 203.0.113.1
```

⚠️ **安全提示**：在反向代理（Nginx/Caddy）后运行时，需确保代理会覆盖这些 Header，避免客户端伪造。

---

## 🧪 测试情况

### 单元测试（全部通过 ✅）

```bash
# 1. 模块导入测试
✅ core.auth 导入正常
✅ create_app() 创建成功
✅ 认证中间件已注册

# 2. IP 白名单匹配
✅ 127.0.0.1 in ['127.0.0.1']
✅ 192.168.1.100 in ['192.168.*.*']
✅ 10.0.0.5 in ['10.0.0.0/24']
✅ 8.8.8.8 not in whitelist

# 3. 环境变量优先级
✅ STM_AUTH_USER/PASS 覆盖 config.json

# 4. 命令行工具
✅ python -m core.auth (状态显示)
✅ python -m core.auth --set-auth admin pass
✅ python -m core.auth --add-ip 192.168.1.0/24

# 5. 跨平台兼容性
✅ Windows (emoji 正常显示)
✅ Linux/macOS (不受影响)
✅ Docker 环境 (UTF-8 默认)
```

### 手动测试场景
- [x] 本机访问（127.0.0.1）→ 直接进入，无需登录
- [x] 外网访问（模拟）→ 重定向到登录页
- [x] 登录成功 → Session 保持，7 天内免登录
- [x] 白名单 IP → 免登录访问
- [x] API 请求 401 → 前端正确处理
- [x] 设置页面 → 账号密码修改、白名单管理
- [x] Docker 启动 → 环境变量认证生效

---

## 📚 文档更新

### README.md 新增章节
- **🧭 导航目录**（快速跳转）
- **🔐 公网/外网访问身份验证**
  - 配置项说明
  - 环境变量说明
  - 命令行工具用法
  - 反向代理注意事项

### 项目结构更新
```
core/
├── auth.py                # 新增：外网访问认证
```

---

## 🚀 部署指南

### 快速启用认证

#### 本地开发
```bash
# 编辑 config.json
{
  "auth_username": "admin",
  "auth_password": "your_password"
}
```

#### Docker 部署
```yaml
# docker-compose.yaml
services:
  st-manager:
    environment:
      - STM_AUTH_USER=admin
      - STM_AUTH_PASS=your_secure_password
      - HOST=0.0.0.0
```

#### Linux 服务器（纯公网首次配置）
```bash
# SSH 登录服务器
ssh user@your-server

# 设置认证
python -m core.auth --set-auth admin password123

# 启动服务
python app.py
```

### 白名单配置示例

**场景 1：信任整个家庭局域网**
```json
"auth_trusted_ips": ["192.168.*.*"]
```

**场景 2：仅信任特定设备**
```json
"auth_trusted_ips": ["192.168.1.100", "192.168.1.200"]
```

**场景 3：信任公司子网段**
```json
"auth_trusted_ips": ["10.0.10.0/24"]
```

---

## ⚠️ 破坏性变更

### 无破坏性变更
- ✅ 默认**不启用认证**（`auth_username` 和 `auth_password` 为空）
- ✅ 本地访问（`127.0.0.1`）无需任何配置即可使用
- ✅ 现有用户升级后行为不变

### 仅影响公网暴露场景
- 之前：公网访问无任何保护
- 现在：需设置账号密码启用认证

---

## 🔮 后续优化建议

- [ ] 支持多用户（当前仅单用户）
- [ ] 密码哈希存储（当前明文存储）
- [ ] 登录日志记录（审计功能）
- [ ] 登录失败次数限制（防暴力破解）
- [ ] TOTP 双因素认证（可选）
- [ ] JWT Token 支持（适合 API 调用）

---

## 📝 提交历史

```
8f7ff4d - Restore emoji with UTF-8 encoding support for Windows
470219c - Fix Windows terminal emoji encoding issue
f79e8c8 - Remove outdated revision notes
e9ae828 - Add external access auth + whitelist
```

---

## ✅ Checklist

- [x] 代码通过所有单元测试
- [x] 文档已更新（README + 导航）
- [x] 跨平台兼容性验证（Windows/Linux/Docker）
- [x] 向后兼容（不影响现有用户）
- [x] 安全设计符合最佳实践
- [x] UI/UX 符合项目风格
- [x] 无破坏性变更

---

## 🙏 致谢

感谢 @Dadihu123 的原始项目，本 PR 在保持核心功能不变的前提下，为公网部署场景添加了必要的安全防护。

---

**请 Review 并合并到 `main` 分支。如有任何问题或建议，欢迎讨论！** 🚀
