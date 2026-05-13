import os
import json
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse

app = FastAPI()

# --- 配置区 ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# 你指定的精选厂商前缀
ALLOWED_PREFIXES = [
    "openai/", "google/", "anthropic/", "microsoft/",
    "alibaba/", "zhipuai/", "minimax/", "meta-llama/"
]

@app.api_route("/v1/models", methods=["GET", "HEAD"])
async def list_models():
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get("https://openrouter.ai/api/v1/models")
            data = resp.json()
            
            # 过滤：1. 免费 2. 属于指定厂商
            filtered = [
                model for model in data.get("data", [])
                if model.get("pricing", {}).get("prompt") == "0" and 
                any(model.get("id", "").lower().startswith(p) for p in ALLOWED_PREFIXES)
            ]
            
            return {"object": "list", "data": sorted(filtered, key=lambda x: x["id"])}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.api_route("/v1/chat/completions", methods=["POST", "HEAD"])
async def chat_proxy(request: Request):
    body = await request.json()
    if "model" not in body:
        body["model"] = "openrouter/free"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://github.com/your-repo/proxy",
        "Content-Type": "application/json"
    }

    async def generate():
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST", 
                "https://openrouter.ai/api/v1/chat/completions",
                json=body,
                headers=headers
            ) as response:
                if response.status_code != 200:
                    yield f"Error: {response.status_code}".encode()
                    return
                
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)
