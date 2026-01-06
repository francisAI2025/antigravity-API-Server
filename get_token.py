#!/usr/bin/env python3
"""
===============================================================================
                    Antigravity API Server - Token 获取工具
===============================================================================

功能：通过 Google OAuth 获取 Refresh Token，用于 API 服务器认证

支持两种模式：
  1. 本地模式 - 有桌面环境，自动打开浏览器并接收回调
  2. 远程模式 - 纯命令行服务器，手动复制 code

使用方法：
  python get_token.py

===============================================================================
"""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import httpx
import threading

# ============================================================================
# OAuth 配置 (来自 Antigravity Manager 项目)
# 这些是公开的 OAuth 客户端凭据，用于访问 Google Cloud Code API
# ============================================================================
CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:9004"
TOKEN_URL = "https://oauth2.googleapis.com/token"

# 请求的权限范围
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",      # Cloud Platform 访问
    "https://www.googleapis.com/auth/userinfo.email",      # 用户邮箱
    "https://www.googleapis.com/auth/userinfo.profile",    # 用户资料
]

# 全局变量：存储授权码
auth_code = None
server_done = threading.Event()

# ============================================================================
# HTTP 回调处理器 (仅本地模式使用)
# ============================================================================
class OAuthHandler(BaseHTTPRequestHandler):
    """处理 OAuth 回调请求"""
    
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        
        if "code" in query:
            auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""
            <html><body style="font-family: sans-serif; text-align: center; padding-top: 50px;">
            <h1 style="color: green;">&#10004; 授权成功!</h1>
            <p>请返回终端查看结果，可以关闭此页面。</p>
            </body></html>
            """)
            server_done.set()
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 静默 HTTP 日志

# ============================================================================
# 辅助函数
# ============================================================================
def get_auth_url():
    """生成 Google OAuth 授权 URL"""
    scope = " ".join(SCOPES)
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={scope}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

def exchange_code_for_token(code: str) -> dict:
    """用授权码换取 access_token 和 refresh_token"""
    print("    → 正在与 Google 服务器通信...")
    
    with httpx.Client(timeout=30) as client:
        resp = client.post(TOKEN_URL, data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        })
        
        if resp.status_code != 200:
            raise Exception(f"Token 交换失败: {resp.text}")
        
        return resp.json()

# ============================================================================
# 主函数
# ============================================================================
def main():
    global auth_code
    
    # 打印欢迎信息
    print("\n" + "="*65)
    print("         🔐 Antigravity API Server - Token 获取工具")
    print("="*65)
    print("\n📌 此工具用于获取 Google OAuth Refresh Token")
    print("   获取后将自动保存到 config.json\n")
    
    # 生成授权 URL
    auth_url = get_auth_url()
    
    print("-"*65)
    print("📋 步骤 1: 请在浏览器中打开以下 URL 进行 Google 授权")
    print("-"*65)
    print(f"\n\033[94m{auth_url}\033[0m\n")
    
    # 询问用户模式
    print("-"*65)
    print("📋 步骤 2: 选择运行模式")
    print("-"*65)
    print("\n  [1] 本地模式 - 自动接收回调")
    print("      └─ 适用于：有桌面环境的电脑\n")
    print("  [2] 远程模式 - 手动输入 code (推荐)")
    print("      └─ 适用于：SSH 连接的服务器、无桌面环境\n")
    
    try:
        choice = input("请选择模式 (1/2) [默认: 2]: ").strip() or "2"
    except EOFError:
        choice = "2"
    
    # 本地模式
    if choice == "1":
        print("\n[*] 启动本地回调服务器...")
        print(f"    监听地址: {REDIRECT_URI}")
        print("    等待 Google 回调...\n")
        
        try:
            import webbrowser
            webbrowser.open(auth_url)
            print("    (已尝试自动打开浏览器)\n")
        except:
            pass
        
        try:
            server = HTTPServer(("localhost", 9004), OAuthHandler)
            server.timeout = 300  # 5分钟超时
            
            while not server_done.is_set():
                server.handle_request()
            
            server.server_close()
            print("    ✓ 收到回调")
        except OSError as e:
            print(f"\n⚠️  端口 9004 被占用，自动切换到远程模式...")
            choice = "2"
    
    # 远程模式
    if choice == "2":
        print("\n" + "-"*65)
        print("📋 步骤 3: 复制授权码")
        print("-"*65)
        print("""
操作指南：

  1. 在本地电脑的浏览器中打开上面的 URL
  
  2. 登录 Google 账号并点击 "允许"
  
  3. 浏览器会跳转到一个 localhost 地址（会显示无法访问，这是正常的）
     示例: http://localhost:9004/?code=4/0AXXXX...&scope=...
  
  4. 从地址栏复制 code= 后面的内容（到 & 符号之前）
     示例: 4/0AXXXX...
  
  5. 粘贴到下面
""")
        print("-"*65)
        
        try:
            auth_code = input("\n请粘贴 code 值: ").strip()
        except EOFError:
            print("❌ 错误：无法读取输入")
            sys.exit(1)
    
    # 检查授权码
    if not auth_code:
        print("\n❌ 错误：未收到授权码")
        sys.exit(1)
    
    print(f"\n[*] 收到授权码: {auth_code[:20]}...")
    print("[*] 正在换取 Refresh Token...")
    
    # 换取 token
    try:
        tokens = exchange_code_for_token(auth_code)
        refresh_token = tokens.get("refresh_token")
        
        if not refresh_token:
            print("\n" + "!"*65)
            print("⚠️  警告：未获取到 refresh_token")
            print("!"*65)
            print("""
可能的原因：
  • 此 Google 账号之前已经授权过

解决方法：
  1. 打开 https://myaccount.google.com/permissions
  2. 找到 "第三方应用" 中的相关应用
  3. 点击 "移除访问权限"
  4. 重新运行此脚本
""")
            sys.exit(1)
        
        # 保存到 config.json（保留其他配置）
        config_path = "config.json"
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except:
            config = {"port": 1234, "default_model": "gemini-2.5-flash"}
        
        config["refresh_token"] = refresh_token
        
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        
        # 成功提示
        print("\n" + "="*65)
        print("         ✅ 成功获取 Refresh Token!")
        print("="*65)
        print(f"\n  Token: {refresh_token[:40]}...")
        print(f"  已保存到: {config_path}")
        print("\n" + "-"*65)
        print("  下一步: 运行 source start.sh 启动服务")
        print("-"*65 + "\n")
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        sys.exit(1)

# ============================================================================
# 入口
# ============================================================================
if __name__ == "__main__":
    main()
