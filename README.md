# 🚀 Antigravity API Server

<div align="center">

**免费使用 Claude 和 Gemini 模型的本地 API 代理服务器**

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-green.svg)](https://python.org)

</div>

---

## 💡 这是什么？

一个让你**免费使用 Claude 和 Gemini 顶级 AI 模型**的工具。

通过 Google Cloud Code API，将你的 Google 账号变成一个强大的 AI API 服务，可以：

- 🤖 **作为 Claude Code CLI 的后端** - 无需官方 API Key
- 🌐 **作为通用 AI API 服务** - 兼容 Anthropic Messages API 格式
- 🆓 **完全免费** - 只需要 Google 账号

---

## ✨ 功能特点

| 特性 | 说明 |
|------|------|
| 🆓 **免费** | 使用 Google 账号，无需付费 API Key |
| 🤖 **多模型** | Claude 4.5 Sonnet/Opus、Gemini 2.5/3 Flash/Pro |
| 🔌 **API 兼容** | Anthropic Messages API 格式 |
| 🖥️ **自托管** | 数据不经过第三方 |
| 📦 **一键安装** | 自动安装 Claude CLI + 配置 + 启动 |

---

## 📦 支持的模型

- **Claude 4.5** Sonnet / Opus (含 Thinking 模式)
- **Gemini 3** Flash / Pro
- **Gemini 2.5** Flash / Pro (含 Thinking 模式)

---

## 🚀 快速开始

### 一键安装

```bash
# 1. 克隆项目
git clone https://github.com/francisAI2025/antigravity-API-Server.git
cd antigravity-API-Server

# 2. 获取 Token（首次需要）
python get_token.py

# 3. 一键安装并启动
source install.sh
```

完成后直接运行：

```bash
claude
```

> **提示**：新终端需要先 `source /root/.env` 或重新 `source start.sh`

---

## 📁 项目结构

```
antigravity-API-Server/
├── install.sh          # 一键安装脚本（推荐）
├── start.sh            # 启动服务脚本
├── get_token.py        # 获取 Google OAuth Token
├── main.py             # API 服务器核心代码
├── config.json         # 配置文件（敏感，已 gitignore）
├── config.example.json # 配置示例
└── requirements.txt    # Python 依赖
```

---

## ⚙️ 配置说明

### config.json

```json
{
  "refresh_token": "你的Google OAuth Token",
  "port": 1234,
  "default_model": "gemini-2.5-flash"
}
```

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `refresh_token` | Google OAuth Refresh Token | (需通过 get_token.py 获取) |
| `port` | API 服务监听端口 | 1234 |
| `default_model` | 默认模型 | gemini-2.5-flash |

---

## 🔧 工作原理

```
┌─────────────────┐      ┌─────────────────────┐      ┌──────────────────┐
│  Claude Code    │      │  Antigravity API    │      │  Google Cloud    │
│  或其他客户端   │ ───▶ │  Server (本项目)    │ ───▶ │  Code API        │
└─────────────────┘      └─────────────────────┘      └──────────────────┘
                                   │
                                   ▼
                         ┌──────────────────┐
                         │  Claude / Gemini │
                         │  模型响应        │
                         └──────────────────┘
```

本项目基于 [Antigravity Manager](https://github.com/lbjlaq/Antigravity-Manager) 的核心逻辑实现。

---

## 📖 使用示例

### 作为 Claude Code CLI 后端

```bash
source start.sh
claude
```

### 作为 API 服务调用

```bash
curl http://localhost:1234/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "你好！"}]
  }'
```

---

## ❓ 常见问题

### 1. Claude CLI 安装失败（Killed 错误）

内存不足导致。解决方案：

```bash
# 使用二进制安装（推荐）
curl -fsSL https://github.com/anthropics/claude-code/releases/latest/download/claude-linux-x64 -o /usr/local/bin/claude
chmod +x /usr/local/bin/claude
```

### 2. 如何获取新的 refresh_token？

```bash
python get_token.py
```

支持远程服务器（纯命令行）和本地桌面两种模式。

### 3. 服务启动后 SSH 断开会停止吗？

使用 `source start.sh` 启动时，服务在后台运行，SSH 断开不影响。

---

## 📄 License

MIT

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

</div>
