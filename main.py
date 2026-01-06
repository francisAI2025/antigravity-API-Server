"""
Antigravity API Server
基于 Antigravity Manager 核心逻辑的 Claude API 代理服务器
使用 Google Cloud Code API (cloudcode-pa.googleapis.com)
"""
import json
import time
import httpx
import uuid
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio

app = FastAPI(title="Antigravity API Server")

# ============ 配置 ============
with open("config.json") as f:
    CONFIG = json.load(f)

REFRESH_TOKEN = CONFIG["refresh_token"]

# Google OAuth 配置 (来自 Antigravity Manager)
TOKEN_URL = "https://oauth2.googleapis.com/token"
CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET = "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"

# Cloud Code API 端点
CLOUDCODE_API = "https://cloudcode-pa.googleapis.com/v1internal"
USER_AGENT = "antigravity/1.11.9 linux/amd64"

# 缓存
_access_token = None
_token_expires_at = 0
_project_id = None

# ============ Token 管理 ============
async def get_access_token() -> str:
    """获取有效的 Access Token，自动刷新"""
    global _access_token, _token_expires_at
    
    if _access_token and time.time() < _token_expires_at - 300:
        return _access_token
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(TOKEN_URL, data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": REFRESH_TOKEN,
            "grant_type": "refresh_token"
        })
        
        if resp.status_code != 200:
            raise HTTPException(500, f"Token 刷新失败: {resp.text}")
        
        data = resp.json()
        _access_token = data["access_token"]
        _token_expires_at = time.time() + data.get("expires_in", 3600)
        print(f"[Token] 已刷新，有效期至 {time.ctime(_token_expires_at)}")
        
    return _access_token

async def get_project_id() -> str:
    """获取 Cloud Code Project ID"""
    global _project_id
    
    if _project_id:
        return _project_id
    
    access_token = await get_access_token()
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{CLOUDCODE_API}:loadCodeAssist",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT
            },
            json={"metadata": {"ideType": "ANTIGRAVITY"}}
        )
        
        if resp.status_code != 200:
            raise HTTPException(500, f"获取 Project ID 失败: {resp.text}")
        
        data = resp.json()
        _project_id = data.get("cloudaicompanionProject")
        
        if not _project_id:
            _project_id = f"useful-flow-{uuid.uuid4().hex[:5]}"
            print(f"[Project] 未获取到官方 ID，使用随机: {_project_id}")
        else:
            print(f"[Project] 获取成功: {_project_id}")
        
    return _project_id

# ============ 模型映射 ============
def map_model(claude_model: str) -> str:
    """Claude 模型名 -> Gemini 模型名"""
    mappings = {
        "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
        "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku": "claude-3-5-haiku-20241022",
        "claude-3-opus": "gemini-2.5-pro",
    }
    return mappings.get(claude_model, claude_model)

# ============ 格式转换 ============
def claude_to_gemini(request: dict, project_id: str) -> dict:
    """Claude 请求格式 -> Gemini v1internal 格式"""
    contents = []
    
    for msg in request.get("messages", []):
        role = "model" if msg["role"] == "assistant" else msg["role"]
        content = msg.get("content", "")
        
        if isinstance(content, str):
            parts = [{"text": content}]
        elif isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append({"text": block.get("text", "")})
                    elif block.get("type") == "tool_result":
                        parts.append({"text": f"[Tool Result: {block.get('content', '')}]"})
                else:
                    parts.append({"text": str(block)})
        else:
            parts = [{"text": str(content)}]
        
        if parts:
            contents.append({"role": role, "parts": parts})
    
    system_instruction = None
    if request.get("system"):
        system_text = request["system"]
        if isinstance(system_text, list):
            system_text = "\n".join([b.get("text", "") if isinstance(b, dict) else str(b) for b in system_text])
        system_instruction = {"parts": [{"text": system_text}]}
    
    inner_request = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": request.get("max_tokens", 8192),
            "temperature": request.get("temperature", 1.0),
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
        ]
    }
    
    if system_instruction:
        inner_request["systemInstruction"] = system_instruction
    
    model = map_model(request.get("model", "claude-sonnet-4-20250514"))
    
    return {
        "project": project_id,
        "requestId": f"agent-{uuid.uuid4()}",
        "request": inner_request,
        "model": model,
        "userAgent": "antigravity",
        "requestType": "agent"
    }

def gemini_to_claude(gemini_response: dict, model: str) -> dict:
    """Gemini 响应格式 -> Claude 格式"""
    if "response" in gemini_response:
        gemini_response = gemini_response["response"]
    
    candidates = gemini_response.get("candidates", [])
    
    content = []
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            if "text" in part:
                content.append({"type": "text", "text": part["text"]})
    
    usage_metadata = gemini_response.get("usageMetadata", {})
    
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage_metadata.get("promptTokenCount", 0),
            "output_tokens": usage_metadata.get("candidatesTokenCount", 0)
        }
    }

# ============ 请求模型 ============
class Message(BaseModel):
    role: str
    content: Any

class ChatRequest(BaseModel):
    model: str = "claude-sonnet-4-20250514"
    messages: List[Message]
    max_tokens: Optional[int] = 8192
    temperature: Optional[float] = 1.0
    stream: Optional[bool] = False
    system: Optional[Any] = None

# ============ API 端点 ============
@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": "claude-sonnet-4-20250514", "object": "model"},
            {"id": "gemini-2.5-flash", "object": "model"},
            {"id": "gemini-2.5-pro", "object": "model"},
        ]
    }

@app.post("/v1/messages")
async def messages(request: ChatRequest):
    """Anthropic Messages API 兼容接口"""
    
    access_token = await get_access_token()
    project_id = await get_project_id()
    
    gemini_body = claude_to_gemini(request.model_dump(), project_id)
    
    method = "streamGenerateContent" if request.stream else "generateContent"
    query = "alt=sse" if request.stream else ""
    
    url = f"{CLOUDCODE_API}:{method}"
    if query:
        url += f"?{query}"
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT
    }
    
    print(f"[Request] {method} -> {gemini_body.get('model')} (stream={request.stream})")
    
    if request.stream:
        # 流式响应 - 客户端必须在生成器内部创建！
        async def generate():
            async with httpx.AsyncClient(timeout=600) as client:
                try:
                    async with client.stream("POST", url, json=gemini_body, headers=headers) as resp:
                        if resp.status_code != 200:
                            error_text = await resp.aread()
                            yield f'data: {{"type":"error","error":{{"message":"Error {resp.status_code}"}}}}\n\n'
                            return
                        
                        msg_id = f"msg_{uuid.uuid4().hex[:24]}"
                        yield f'data: {{"type":"message_start","message":{{"id":"{msg_id}","type":"message","role":"assistant","content":[],"model":"{request.model}"}}}}\n\n'
                        yield f'data: {{"type":"content_block_start","index":0,"content_block":{{"type":"text","text":""}}}}\n\n'
                        
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        for part in parts:
                                            if "text" in part:
                                                text = part["text"]
                                                escaped = json.dumps(text)
                                                yield f'data: {{"type":"content_block_delta","index":0,"delta":{{"type":"text_delta","text":{escaped}}}}}\n\n'
                                except Exception as e:
                                    print(f"[Stream Parse Error] {e}")
                        
                        yield f'data: {{"type":"content_block_stop","index":0}}\n\n'
                        yield f'data: {{"type":"message_delta","delta":{{"stop_reason":"end_turn"}}}}\n\n'
                        yield f'data: {{"type":"message_stop"}}\n\n'
                except Exception as e:
                    print(f"[Stream Error] {e}")
                    yield f'data: {{"type":"error","error":{{"message":"{str(e)}"}}}}\n\n'
        
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        # 非流式
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(url, json=gemini_body, headers=headers)
            
            if resp.status_code != 200:
                print(f"[Error] {resp.status_code}: {resp.text}")
                raise HTTPException(resp.status_code, resp.text)
            
            gemini_resp = resp.json()
            claude_resp = gemini_to_claude(gemini_resp, request.model)
            
            return claude_resp

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI 兼容接口"""
    body = await request.json()
    
    claude_req = ChatRequest(
        model=body.get("model", "claude-sonnet-4-20250514"),
        messages=[Message(role=m["role"], content=m["content"]) for m in body.get("messages", [])],
        max_tokens=body.get("max_tokens", 8192),
        temperature=body.get("temperature", 1.0),
        stream=body.get("stream", False)
    )
    
    return await messages(claude_req)

# ============ 启动 ============
if __name__ == "__main__":
    import uvicorn
    PORT = CONFIG.get("port", 1234)
    print(f"""
╔══════════════════════════════════════════════════════════╗
║           Antigravity API Server                         ║
║                                                          ║
║  端点: http://0.0.0.0:{PORT:<5}                              ║
║  文档: http://0.0.0.0:{PORT}/docs                          ║
║                                                          ║
║  使用方法:                                               ║
║  source start.sh                                         ║
║  claude                                                   ║
╚══════════════════════════════════════════════════════════╝
    """)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
