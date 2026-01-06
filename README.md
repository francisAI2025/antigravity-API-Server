# 🚀 Antigravity API Server

**免费使用 Claude 和 Gemini 模型的 API 代理服务器**

通过 Google Cloud Code API，将你的 Google 账号变成一个强大的 AI API 服务。

---

## ✨ 亮点

| 特性 | 说明 |
|------|------|
| 🆓 **免费** | 使用 Google 账号即可，无需付费 API Key |
| 🤖 **多模型** | 支持 Claude 4.5、Gemini 2.5/3 等顶级模型 |
| 🔌 **兼容** | Anthropic Messages API 格式，可直接对接 Claude Code CLI |
| 🖥️ **自托管** | 在自己的服务器上运行，数据不经过第三方 |

---

## 🎯 使用场景

### 1. 给 Claude Code CLI 提供免费后端

```bash
source start.sh  # 启动服务并设置环境变量
claude           # 直接使用 Claude Code，无需官方 API Key
```

### 2. 作为通用 AI API 服务

```bash
curl http://localhost:1234/v1/messages \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-flash",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## 📦 支持的模型

- **Claude 4.5** Sonnet / Opus (含 Thinking 模式)
- **Gemini 3** Flash / Pro
- **Gemini 2.5** Flash / Pro

---

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/francisAI2025/antigravity-API-Server.git
cd antigravity-API-Server
```

### 2. 获取 Google OAuth Token

```bash
python get_token.py
```

按提示在浏览器中完成 Google 授权。

### 3. 启动服务

```bash
source start.sh
```

脚本会自动：
- 检查并安装依赖
- 启动 API 服务器
- 设置环境变量（当前会话 + `/root/.env` 持久化）

### 4. 开始使用

```bash
claude  # 直接使用 Claude Code CLI
```

---

## ⚙️ 配置

复制示例配置：

```bash
cp config.example.json config.json
```

编辑 `config.json`：

```json
{
  "refresh_token": "你的token",
  "port": 1234,
  "default_model": "gemini-2.5-flash"
}
```

---

## 🔧 工作原理

```
┌─────────────────┐     ┌─────────────────────┐     ┌──────────────────┐
│  Claude Code    │     │  Antigravity API    │     │  Google Cloud    │
│  或其他客户端    │ ──▶ │  Server (本项目)     │ ──▶ │  Code API        │
└─────────────────┘     └─────────────────────┘     └──────────────────┘
                                  │
                                  ▼
                        ┌──────────────────┐
                        │  Claude / Gemini │
                        │  模型响应         │
                        └──────────────────┘
```

本项目基于 [Antigravity Manager](https://github.com/lbjlaq/Antigravity-Manager) 的核心逻辑实现。

---

## 📄 License

MIT
