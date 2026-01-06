#!/bin/bash
#
# ============================================================================
#                    Antigravity API Server - 一键安装脚本
# ============================================================================
#
# 功能：
#   1. 安装 Claude CLI（多种备选方案，解决常见安装问题）
#   2. 跳过 Claude 官方登录验证
#   3. 启动 Antigravity API Server
#   4. 配置 Claude CLI 使用自定义 API
#
# 使用方法：
#   source install.sh
#
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="/root/.env"

echo ""
echo "╔═══════════════════════════════════════════════════════════════════════╗"
echo "║           🚀 Antigravity API Server - 一键安装                        ║"
echo "╚═══════════════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# Step 1: 检查并安装 Claude CLI
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📦 Step 1: 检查 Claude CLI"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

install_claude_cli() {
    # 方法 1: 使用官方推荐的二进制安装（最稳定）
    echo "[*] 尝试方法 1: 官方二进制安装..."
    
    # 检测架构
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)  ARCH_NAME="x64" ;;
        aarch64) ARCH_NAME="arm64" ;;
        *)       ARCH_NAME="x64" ;;
    esac
    
    # 下载并安装
    INSTALL_DIR="/usr/local/bin"
    DOWNLOAD_URL="https://github.com/anthropics/claude-code/releases/latest/download/claude-linux-${ARCH_NAME}"
    
    if curl -fsSL "$DOWNLOAD_URL" -o /tmp/claude 2>/dev/null; then
        chmod +x /tmp/claude
        mv /tmp/claude "$INSTALL_DIR/claude"
        
        if command -v claude &> /dev/null; then
            echo "[✓] 二进制安装成功"
            return 0
        fi
    fi
    echo "    二进制安装失败，尝试其他方法..."
    
    # 方法 2: npm 安装（需要 Node.js）
    echo "[*] 尝试方法 2: npm 安装..."
    
    if ! command -v npm &> /dev/null; then
        echo "    npm 未安装，尝试安装 Node.js..."
        
        # 使用 NodeSource 安装最新 LTS 版本
        if command -v apt &> /dev/null; then
            curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - 2>/dev/null
            apt install -y nodejs 2>/dev/null
        elif command -v yum &> /dev/null; then
            curl -fsSL https://rpm.nodesource.com/setup_lts.x | bash - 2>/dev/null
            yum install -y nodejs 2>/dev/null
        fi
    fi
    
    if command -v npm &> /dev/null; then
        # 增加 npm 超时和重试
        # 解决内存不足问题：设置 NODE_OPTIONS
        export NODE_OPTIONS="--max-old-space-size=512"
        
        echo "    正在安装 @anthropic-ai/claude-code..."
        echo "    (如果内存不足可能会失败，请耐心等待...)"
        
        # 使用 --no-optional 减少依赖
        if npm install -g @anthropic-ai/claude-code --no-optional 2>/dev/null; then
            if command -v claude &> /dev/null; then
                echo "[✓] npm 安装成功"
                return 0
            fi
        fi
        
        # 如果还失败，尝试清理缓存后重试
        echo "    首次尝试失败，清理缓存后重试..."
        npm cache clean --force 2>/dev/null
        
        if npm install -g @anthropic-ai/claude-code --no-optional 2>/dev/null; then
            if command -v claude &> /dev/null; then
                echo "[✓] npm 安装成功（第二次尝试）"
                return 0
            fi
        fi
    fi
    
    echo "    npm 安装失败"
    
    # 方法 3: 使用 pipx 安装 Python 版本（如果有的话）
    echo "[*] 尝试方法 3: 检查其他安装方式..."
    
    # 最后的提示
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  自动安装失败！请手动安装 Claude CLI:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  方法 1 (推荐): 下载二进制文件"
    echo "    curl -fsSL https://github.com/anthropics/claude-code/releases/latest/download/claude-linux-x64 -o /usr/local/bin/claude"
    echo "    chmod +x /usr/local/bin/claude"
    echo ""
    echo "  方法 2: 使用 npm"
    echo "    npm install -g @anthropic-ai/claude-code"
    echo ""
    echo "  如果遇到 'Killed' 错误 (内存不足):"
    echo "    1. 增加 swap 空间"
    echo "    2. 或使用二进制安装方式"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    return 1
}

if command -v claude &> /dev/null; then
    CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "unknown")
    echo "[✓] Claude CLI 已安装: $CLAUDE_VERSION"
else
    install_claude_cli
    if [ $? -ne 0 ]; then
        echo ""
        echo "[!] Claude CLI 安装失败，但 API Server 仍可使用"
        echo "    安装 Claude CLI 后重新运行此脚本"
    fi
fi
echo ""

# ============================================================================
# Step 2: 配置跳过登录
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔓 Step 2: 配置跳过官方登录"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Claude CLI 配置目录（可能的位置）
CLAUDE_CONFIG_DIRS=(
    "$HOME/.claude"
    "$HOME/.config/claude"
)

for CLAUDE_CONFIG_DIR in "${CLAUDE_CONFIG_DIRS[@]}"; do
    mkdir -p "$CLAUDE_CONFIG_DIR"
    
    CLAUDE_CONFIG_FILE="$CLAUDE_CONFIG_DIR/.credentials.json"
    
    # 创建假的凭据文件跳过登录
    cat > "$CLAUDE_CONFIG_FILE" << 'EOF'
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-placeholder",
    "refreshToken": "placeholder",
    "expiresAt": 9999999999999
  }
}
EOF
done

echo "[✓] 已配置跳过官方登录"
echo ""

# ============================================================================
# Step 3: 启动 API Server
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Step 3: 启动 Antigravity API Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 调用 start.sh
cd "$SCRIPT_DIR"
source start-server.sh

# 检查是否成功
if [ $? -ne 0 ]; then
    echo "[✗] API Server 启动失败"
    return 1 2>/dev/null || exit 1
fi
echo ""

# ============================================================================
# Step 4: 完成
# ============================================================================
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ 安装完成!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  现在可以直接使用 Claude CLI："
echo ""
echo "    \$ claude"
echo ""
echo "  环境变量已配置："
echo "    • 当前会话已生效"
echo "    • 已写入 $ENV_FILE（新终端请 source $ENV_FILE）"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
