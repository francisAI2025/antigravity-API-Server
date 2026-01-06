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
# ============ 模型映射 ============
def map_model(claude_model: str) -> str:
    """Claude 模型名 -> Google Internal 模型名"""
    # 0. 预处理：转小写
    model = claude_model.lower()

    # 1. 验证过的有效内部 ID 映射表 (from Antigravity-Manager)
    # 这些是 cloudcode-pa API 真正接受的 ID
    valid_mappings = {
        # Claude 3.5 Sonnet 系列 -> claude-sonnet-4-5
        "claude-3-5-sonnet-20241022": "claude-sonnet-4-5",
        "claude-3-5-sonnet-20240620": "claude-sonnet-4-5",
        "claude-3-5-sonnet-latest": "claude-sonnet-4-5",
        "claude-3-5-sonnet": "claude-sonnet-4-5",
        
        # Claude 3 Haiku 系列 -> claude-sonnet-4-5 (智能升级)
        "claude-3-haiku-20240307": "claude-sonnet-4-5",
        "claude-3-haiku": "claude-sonnet-4-5",

        # Opus 系列 -> claude-opus-4-5-thinking
        "claude-3-opus-20240229": "claude-opus-4-5-thinking",
        "claude-3-opus": "claude-opus-4-5-thinking",
        "claude-opus-4-5-20251101": "claude-opus-4-5-thinking", # 用户指定的 ID
        
        # 兼容性映射
        "gpt-4": "gemini-2.5-pro",
        "gpt-4o": "gemini-2.5-pro", 
        "gpt-3.5-turbo": "gemini-2.5-flash",
    }

    # 2. 精确匹配
    if model in valid_mappings:
        mapped = valid_mappings[model]
        print(f"\033[92m[Model Map] '{claude_model}' -> '{mapped}' (Exact Match)\033[0m")
        return mapped

    # 3. 智能关键词匹配 (Fuzzy Match)
    if "gemini" in model:
        # 透传 Gemini 模型 (假设用户知道自己在做什么)
        return claude_model

    if "opus" in model:
        mapped = "claude-opus-4-5-thinking"
        print(f"\033[93m[Model Map] '{claude_model}' -> '{mapped}' (Keyword: opus)\033[0m")
        return mapped
        
    if "sonnet" in model:
        mapped = "claude-sonnet-4-5"
        print(f"\033[93m[Model Map] '{claude_model}' -> '{mapped}' (Keyword: sonnet)\033[0m")
        return mapped
        
    if "haiku" in model:
        mapped = "claude-sonnet-4-5" # 升级 Haiku 到 Sonnet 4.5
        print(f"\033[93m[Model Map] '{claude_model}' -> '{mapped}' (Keyword: haiku -> Upgrade)\033[0m")
        return mapped

    # 4. 默认 Fallback
    fallback = "gemini-2.5-flash"
    print(f"\033[91m[Model Map] Unknown model '{claude_model}'. Fallback -> '{fallback}'\033[0m")
    return fallback

# ============ 格式转换 ============
# ============ 格式转换 ============

def flatten_refs(schema: dict, defs: dict):
    """递归展开 $ref"""
    if "$ref" in schema:
        ref_path = schema.pop("$ref")
        ref_name = ref_path.split("/")[-1]
        if ref_name in defs:
            # 合并定义
            def_schema = defs[ref_name]
            for k, v in def_schema.items():
                if k not in schema:
                    schema[k] = v
            # 递归处理可能引入的新 $ref
            flatten_refs(schema, defs)
    
    for v in schema.values():
        if isinstance(v, dict):
            flatten_refs(v, defs)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    flatten_refs(item, defs)

def clean_json_schema(value: Any):
    """递归清理 JSON Schema 以符合 Gemini 接口要求"""
    if isinstance(value, dict):
        # 0. 预处理：展开 $defs (仅在顶层或有 definitions 的层级)
        defs = {}
        if "$defs" in value:
            defs.update(value.pop("$defs"))
        if "definitions" in value:
            defs.update(value.pop("definitions"))
            
        if defs:
            flatten_refs(value, defs)

        # 1. 深度递归处理
        for v in value.values():
            clean_json_schema(v)
            
        # 2. 收集并处理校验字段 (迁移到描述)
        validation_fields = {
            "pattern": "pattern",
            "minLength": "minLen",
            "maxLength": "maxLen",
            "minimum": "min",
            "maximum": "max",
            "minItems": "minItems",
            "maxItems": "maxItems",
            "exclusiveMinimum": "exclMin",
            "exclusiveMaximum": "exclMax",
            "multipleOf": "multipleOf",
            "format": "format",
        }
        
        constraints = []
        for field, label in validation_fields.items():
            if field in value:
                val = value.pop(field)
                if isinstance(val, (str, int, float, bool)):
                    constraints.append(f"{label}: {val}")
        
        # 3. 追加到描述
        if constraints:
            suffix = f" [Constraint: {', '.join(constraints)}]"
            desc = value.get("description", "")
            value["description"] = desc + suffix

        # 4. 移除不支持的字段 (黑名单)
        hard_remove_fields = [
            "$schema", "$id", "additionalProperties", "enumCaseInsensitive",
            "enumNormalizeWhitespace", "uniqueItems", "default", "const",
            "examples", "propertyNames", "anyOf", "oneOf", "allOf",
            "not", "if", "then", "else", "dependencies",
            "dependentSchemas", "dependentRequired", "cache_control",
            "contentEncoding", "contentMediaType", "deprecated",
            "readOnly", "writeOnly"
        ]
        for field in hard_remove_fields:
            if field in value:
                value.pop(field)

        # 5. 清理 required (确保只包含存在的 properties)
        if "required" in value and "properties" in value:
            valid_props = set(value["properties"].keys())
            value["required"] = [k for k in value["required"] if k in valid_props]
            if not value["required"]:
                value.pop("required") # 如果为空则移除

        # 6. 处理 type 字段
        if "type" in value:
            if isinstance(value["type"], str):
                value["type"] = value["type"].lower()
            elif isinstance(value["type"], list):
                # 联合类型 ["string", "null"] -> "string"
                selected = "string"
                for t in value["type"]:
                    if t != "null":
                        selected = t.lower()
                        break
                value["type"] = selected
                
    elif isinstance(value, list):
        for item in value:
            clean_json_schema(item)

def transform_tools(tools: List[dict]) -> List[dict]:
    """Claude 工具定义 -> Gemini 工具定义"""
    if not tools:
        return None
        
    function_declarations = []
    for tool in tools:
        decl = {
            "name": tool["name"],
            "description": tool.get("description", ""),
        }
        if "input_schema" in tool:
            params = tool["input_schema"]
            # Debug: 打印原始 schema 中是否包含 $schema
            if "$schema" in params:
                print(f"[DEBUG] Found $schema in tool '{tool['name']}' BEFORE cleaning")
            
            # 使用深度清理逻辑
            clean_json_schema(params)
            
            # Debug: 打印清理后的 schema 中是否包含 $schema
            if "$schema" in params:
                 print(f"[ERROR] $schema STILL present in tool '{tool['name']}' AFTER cleaning!")
            else:
                 print(f"[DEBUG] $schema successfully removed from '{tool['name']}'")
            
            decl["parameters"] = params
            
        function_declarations.append(decl)
        
    return [{"function_declarations": function_declarations}]

def claude_to_gemini(request: dict, project_id: str) -> dict:
    """Claude 请求格式 -> Gemini v1internal 格式"""
    contents = []
    
    for msg in request.get("messages", []):
        role = "model" if msg["role"] == "assistant" else msg["role"]
        content = msg.get("content", "")
        
        parts = []
        # 处理内容（可能是字符串或数组）
        if isinstance(content, str):
            parts = [{"text": content}]
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append({"text": block.get("text", "")})
                    elif block.get("type") == "tool_use":
                        # Assistant 想要调用工具 -> Gemini functionCall
                        parts.append({
                            "functionCall": {
                                "name": block["name"],
                                "args": block["input"]
                            }
                        })
                    elif block.get("type") == "tool_result":
                        # Tool 执行结果 -> Gemini functionResponse
                        # 注意：Gemini 要求 functionResponse 单独作为一条消息或在 user 消息中
                        parts.append({
                            "functionResponse": {
                                "name": block.get("name", "unknown_tool"), # Claude tool_result 通常不带 name，可能需要记录上下文或从 content_block 中推断，这里需要注意
                                "response": {
                                    "name": block.get("name", "unknown_tool"),
                                    "content": block.get("content", "") 
                                }
                            }
                        })
                        # 对于 Antigravity/CloudCode API，tool_result 通常也是 "user" role
                else:
                    parts.append({"text": str(block)})
        else:
            parts = [{"text": str(content)}]
        
        if parts:
            # 修正: Gemini 中 functionResponse 应该是 'function' role 或者是 user的一部分?
            # Cloud Code API 中通常 user 角色发送 functionResponse
             contents.append({"role": role, "parts": parts})

    # 处理 tool_result 的特殊情况：Claude 中 tool_result 是 user 消息
    # 我们的循环已经处理了 role 映射

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

    # 处理 Tools 定义
    if "tools" in request:
        inner_request["tools"] = transform_tools(request["tools"])
        # 强制工具使用模式
        # inner_request["toolConfig"] = {"functionCallingConfig": {"mode": "AUTO"}}
    
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
    stop_reason = "end_turn"

    if candidates:
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            if "text" in part:
                content.append({"type": "text", "text": part["text"]})
            elif "functionCall" in part:
                # Gemini 想要调用工具 -> Claude tool_use
                fc = part["functionCall"]
                content.append({
                    "type": "tool_use",
                    "id": f"call_{uuid.uuid4().hex[:16]}", # Gemini 不返回 call_id，需要生成
                    "name": fc["name"],
                    "input": fc["args"]
                })
                stop_reason = "tool_use"
    
    usage_metadata = gemini_response.get("usageMetadata", {})
    
    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "content": content,
        "model": model,
        "stop_reason": stop_reason,
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
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[Any] = None

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
                        
                        # 内容块索引
                        block_index = 0
                        # 记录当前是否正在流式传输文本块
                        in_text_block = False
                        
                        async for line in resp.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    candidates = data.get("candidates", [])
                                    if candidates:
                                        parts = candidates[0].get("content", {}).get("parts", [])
                                        for part in parts:
                                            # 处理文本
                                            if "text" in part:
                                                text = part["text"]
                                                if not in_text_block:
                                                    yield f'data: {{"type":"content_block_start","index":{block_index},"content_block":{{"type":"text","text":""}}}}\n\n'
                                                    in_text_block = True
                                                
                                                escaped = json.dumps(text)
                                                yield f'data: {{"type":"content_block_delta","index":{block_index},"delta":{{"type":"text_delta","text":{escaped}}}}}\n\n'
                                            
                                            # 处理函数调用
                                            elif "functionCall" in part:
                                                if in_text_block:
                                                    yield f'data: {{"type":"content_block_stop","index":{block_index}}}\n\n'
                                                    block_index += 1
                                                    in_text_block = False
                                                
                                                fc = part["functionCall"]
                                                tool_id = f"call_{uuid.uuid4().hex[:16]}"
                                                name_json = json.dumps(fc["name"])
                                                
                                                # 开始 Tool Block
                                                yield f'data: {{"type":"content_block_start","index":{block_index},"content_block":{{"type":"tool_use","id":"{tool_id}","name":{name_json},"input":{{}}}}}}\n\n'
                                                
                                                # 发送参数 (Gemini 返回的是对象，我们转回 JSON 字符串发送)
                                                args_json = json.dumps(fc["args"])
                                                escaped_args = json.dumps(args_json) # 再次转义作为 JSON 字符串的值
                                                yield f'data: {{"type":"content_block_delta","index":{block_index},"delta":{{"type":"input_json_delta","partial_json":{escaped_args}}}}}\n\n'
                                                
                                                # 结束 Tool Block
                                                yield f'data: {{"type":"content_block_stop","index":{block_index}}}\n\n'
                                                block_index += 1
                                                
                                                # 记录停止原因
                                                yield f'data: {{"type":"message_delta","delta":{{"stop_reason":"tool_use"}}}}\n\n'

                                except Exception as e:
                                    print(f"[Stream Parse Error] {e}")
                        
                        if in_text_block:
                            yield f'data: {{"type":"content_block_stop","index":{block_index}}}\n\n'
                        
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
