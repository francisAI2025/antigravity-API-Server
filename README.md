# Antigravity API Server

基于 [Antigravity Manager](https://github.com/lbjlaq/Antigravity-Manager) 核心逻辑的 Claude/Gemini API 代理服务器。

## 功能

- 🔐 自动获取和刷新 Google OAuth Token
- 🔄 Anthropic Messages API 兼容格式
- 🌐 支持 Claude Code CLI 直接使用
- 📦 一键启动脚本

## 支持的模型

- Claude 4.5 Sonnet / Opus (Thinking)
- Gemini 2.5 Flash / Pro
- Gemini 3 Flash / Pro

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 获取 Token

```bash
python get_token.py
```

按提示完成 Google OAuth 授权。

### 3. 启动服务

```bash
source start.sh
```

### 4. 使用 Claude Code

```bash
claude
```

## 配置说明

复制 `config.example.json` 为 `config.json`：

```bash
cp config.example.json config.json
```

配置项：

| 字段 | 说明 | 默认值 |
|------|------|--------|
| `refresh_token` | Google OAuth Refresh Token | (需获取) |
| `port` | 监听端口 | 1234 |
| `default_model` | 默认模型 | gemini-2.5-flash |

## 原理

通过 Google Cloud Code API (`cloudcode-pa.googleapis.com`) 访问 Google 托管的 Claude 和 Gemini 模型。

## 文件结构

```
├── config.json          # 配置文件 (含敏感信息，已 gitignore)
├── config.example.json  # 配置示例
├── get_token.py         # Token 获取工具
├── main.py              # API 服务器
├── start.sh             # 一键启动脚本
└── requirements.txt     # 依赖
```

## License

MIT
