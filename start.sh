#!/bin/bash
#
# Antigravity API Server 启动脚本
# 用法: source start.sh  (这样环境变量才能在当前会话生效)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
ENV_FILE="/root/.env"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Antigravity API Server - Start Script            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# 检查并安装依赖
echo "[*] 检查 Python 依赖..."
MISSING_DEPS=0
while IFS= read -r pkg || [ -n "$pkg" ]; do
    pkg=$(echo "$pkg" | tr -d '[:space:]')
    [ -z "$pkg" ] && continue
    
    if ! python3 -c "import $pkg" 2>/dev/null; then
        echo "    [!] 缺少: $pkg"
        MISSING_DEPS=1
    fi
done < "$REQUIREMENTS_FILE"

if [ $MISSING_DEPS -eq 1 ]; then
    echo "[*] 安装缺少的依赖..."
    pip install -q -r "$REQUIREMENTS_FILE"
    if [ $? -ne 0 ]; then
        echo "[✗] 依赖安装失败"
        return 1 2>/dev/null || exit 1
    fi
    echo "[✓] 依赖安装完成"
else
    echo "[✓] 依赖已满足"
fi
echo ""

# 检查 config.json 是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[!] config.json 不存在，正在创建..."
    echo '{"refresh_token": "", "port": 1234, "default_model": "gemini-2.5-flash"}' > "$CONFIG_FILE"
fi

# 读取配置
REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('refresh_token', ''))" 2>/dev/null)
PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('port', 1234))" 2>/dev/null)
DEFAULT_MODEL=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('default_model', 'gemini-2.5-flash'))" 2>/dev/null)

# 检查 refresh_token
if [ -z "$REFRESH_TOKEN" ] || [ "$REFRESH_TOKEN" = "" ]; then
    echo "[!] 未配置 refresh_token，启动授权流程..."
    echo ""
    cd "$SCRIPT_DIR"
    python3 get_token.py
    
    if [ $? -ne 0 ]; then
        echo "[✗] 获取 token 失败"
        return 1 2>/dev/null || exit 1
    fi
    
    # 重新读取
    REFRESH_TOKEN=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('refresh_token', ''))" 2>/dev/null)
    PORT=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('port', 1234))" 2>/dev/null)
fi

echo "[✓] Refresh Token: ${REFRESH_TOKEN:0:20}..."
echo "[✓] 监听端口: $PORT"
echo "[✓] 默认模型: $DEFAULT_MODEL"
echo ""

# 杀死旧进程
echo "[*] 停止旧进程..."
pkill -f "antigravity-API-Server/main.py" 2>/dev/null
fuser -k $PORT/tcp 2>/dev/null
sleep 1

# 启动服务
echo "[*] 启动 API 服务器..."
cd "$SCRIPT_DIR"
nohup python3 main.py > /tmp/antigravity.log 2>&1 &
SERVER_PID=$!

# 等待启动
sleep 3

# 检查是否启动成功
if curl -s "http://127.0.0.1:$PORT/health" | grep -q "ok"; then
    echo "[✓] 服务器启动成功 (PID: $SERVER_PID)"
    echo ""
    
    # 设置当前会话环境变量
    export ANTHROPIC_BASE_URL="http://127.0.0.1:$PORT"
    export ANTHROPIC_API_KEY="sk-antigravity"
    export ANTHROPIC_MODEL="$DEFAULT_MODEL"
    
    # 更新 /root/.env 文件 (智能添加/修改，不覆盖其他变量)
    echo "[*] 更新 $ENV_FILE ..."
    
    # 创建文件（如果不存在）
    touch "$ENV_FILE"
    
    # 定义要设置的变量
    declare -A ENV_VARS
    ENV_VARS["ANTHROPIC_BASE_URL"]="http://127.0.0.1:$PORT"
    ENV_VARS["ANTHROPIC_API_KEY"]="sk-antigravity"
    ENV_VARS["ANTHROPIC_MODEL"]="$DEFAULT_MODEL"
    
    # 逐个处理变量
    for VAR_NAME in "${!ENV_VARS[@]}"; do
        VAR_VALUE="${ENV_VARS[$VAR_NAME]}"
        
        if grep -q "^export $VAR_NAME=" "$ENV_FILE" 2>/dev/null; then
            sed -i "s|^export $VAR_NAME=.*|export $VAR_NAME=\"$VAR_VALUE\"|" "$ENV_FILE"
        elif grep -q "^$VAR_NAME=" "$ENV_FILE" 2>/dev/null; then
            sed -i "s|^$VAR_NAME=.*|export $VAR_NAME=\"$VAR_VALUE\"|" "$ENV_FILE"
        else
            echo "export $VAR_NAME=\"$VAR_VALUE\"" >> "$ENV_FILE"
        fi
    done
    
    echo "[✓] 已更新 $ENV_FILE"
    echo ""
    
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║  环境变量已设置:                                         ║"
    echo "║                                                          ║"
    echo "║  ANTHROPIC_BASE_URL=http://127.0.0.1:$PORT               ║"
    echo "║  ANTHROPIC_API_KEY=sk-antigravity                        ║"
    echo "║  ANTHROPIC_MODEL=$DEFAULT_MODEL                          ║"
    echo "║                                                          ║"
    echo "║  已写入 /root/.env (持久生效)                            ║"
    echo "║  新终端请运行: source /root/.env                         ║"
    echo "║                                                          ║"
    echo "║  现在可以直接运行: claude                                ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo ""
    echo "[i] 日志: tail -f /tmp/antigravity.log"
    echo "[i] 停止: pkill -f 'antigravity-API-Server/main.py'"
    echo ""
else
    echo "[✗] 服务器启动失败，请检查日志:"
    echo "    tail -50 /tmp/antigravity.log"
    return 1 2>/dev/null || exit 1
fi
