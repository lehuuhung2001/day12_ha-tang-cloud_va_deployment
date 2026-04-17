"""
Production AI Agent — Day 12 Lab Complete

✅ Config từ environment (12-factor)
✅ Structured JSON logging
✅ API Key authentication (app.auth)
✅ Rate limiting — 10 req/min (app.rate_limiter)
✅ Cost guard — $10/day (app.cost_guard)
✅ Input validation (Pydantic)
✅ Health check + Readiness probe
✅ Graceful shutdown (SIGTERM)
✅ Web chat UI (/chat)
✅ Security headers
✅ CORS
"""
import time
import signal
import logging
import json
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from app.auth import verify_api_key
from app.rate_limiter import rate_limiter
from app.cost_guard import cost_guard
from utils.mock_llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — JSON structured
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_request_count = 0
_error_count = 0

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }))
    time.sleep(0.1)
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def request_middleware(request: Request, call_next):
    global _request_count, _error_count
    start = time.time()
    _request_count += 1
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        if "server" in response.headers:
            del response.headers["server"]
        duration = round((time.time() - start) * 1000, 1)
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": duration,
        }))
        return response
    except Exception:
        _error_count += 1
        raise

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)

class AskResponse(BaseModel):
    question: str
    answer: str
    model: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Chat UI HTML
# ─────────────────────────────────────────────────────────
CHAT_HTML = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Agent Chat</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #f0f2f5; height: 100vh; display: flex; align-items: center; justify-content: center; }
  #app { width: 100%; max-width: 700px; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,.12); display: flex; flex-direction: column; height: 90vh; }
  header { padding: 16px 20px; border-bottom: 1px solid #e5e7eb; }
  header h1 { font-size: 1.1rem; color: #111; }
  header p { font-size: .8rem; color: #6b7280; margin-top: 2px; }
  #history { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .msg { max-width: 80%; padding: 10px 14px; border-radius: 10px; font-size: .9rem; line-height: 1.5; }
  .msg.user { align-self: flex-end; background: #2563eb; color: white; border-bottom-right-radius: 2px; }
  .msg.agent { align-self: flex-start; background: #f3f4f6; color: #111; border-bottom-left-radius: 2px; }
  .msg.error { align-self: flex-start; background: #fee2e2; color: #991b1b; border-bottom-left-radius: 2px; }
  .msg .label { font-size: .7rem; opacity: .7; margin-bottom: 3px; text-transform: uppercase; letter-spacing: .05em; }
  #input-bar { padding: 12px 16px; border-top: 1px solid #e5e7eb; display: flex; gap: 8px; }
  #question { flex: 1; padding: 10px 14px; border: 1px solid #d1d5db; border-radius: 8px; font-size: .9rem; outline: none; }
  #question:focus { border-color: #2563eb; }
  #send-btn { padding: 10px 20px; background: #2563eb; color: white; border: none; border-radius: 8px; font-size: .9rem; cursor: pointer; transition: background .15s; }
  #send-btn:hover { background: #1d4ed8; }
  #send-btn:disabled { background: #93c5fd; cursor: not-allowed; }
  .thinking { color: #6b7280; font-style: italic; font-size: .85rem; }
</style>
</head>
<body>
<div id="app">
  <header>
    <h1>🤖 AI Agent Chat</h1>
  </header>
  <div id="history">
    <div class="msg agent"><div class="label">Agent</div>Xin chào! Tôi là AI Agent. Đặt câu hỏi để bắt đầu. 👋</div>
  </div>
  <div id="input-bar">
    <input type="text" id="question" placeholder="Nhập câu hỏi..." onkeydown="if(event.key==='Enter')send()" />
    <button id="send-btn" onclick="send()">Gửi</button>
  </div>
</div>
<script>
const API_KEY = "__API_KEY__";
async function send() {
  const q = document.getElementById('question').value.trim();
  if (!q) return;
  const btn = document.getElementById('send-btn');
  btn.disabled = true;
  addMsg('user', q);
  document.getElementById('question').value = '';
  const thinking = addMsg('agent', '<span class="thinking">Đang suy nghĩ...</span>');
  try {
    const res = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': API_KEY },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    thinking.remove();
    if (res.ok) {
      addMsg('agent', data.answer);
    } else {
      const detail = typeof data.detail === 'object' ? JSON.stringify(data.detail) : (data.detail || 'Lỗi không xác định');
      addMsg('error', `[${res.status}] ${detail}`);
    }
  } catch(e) {
    thinking.remove();
    addMsg('error', 'Network error: ' + e.message);
  }
  btn.disabled = false;
  document.getElementById('question').focus();
}

function addMsg(role, html) {
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  const label = role === 'user' ? 'Bạn' : role === 'agent' ? 'Agent' : 'Lỗi';
  div.innerHTML = '<div class="label">' + label + '</div>' + html;
  const hist = document.getElementById('history');
  hist.appendChild(div);
  hist.scrollTop = hist.scrollHeight;
  return div;
}
</script>
</body>
</html>"""

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
def root():
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "endpoints": {
            "chat_ui": "GET /chat",
            "ask": "POST /ask (requires X-API-Key)",
            "health": "GET /health",
            "ready": "GET /ready",
            "metrics": "GET /metrics (requires X-API-Key)",
        },
    }


@app.get("/chat", response_class=HTMLResponse, tags=["UI"])
def chat_ui():
    """Web chat interface."""
    return CHAT_HTML.replace("__API_KEY__", settings.agent_api_key)


@app.post("/ask", response_model=AskResponse, tags=["Agent"])
async def ask_agent(
    body: AskRequest,
    request: Request,
    api_key: str = Depends(verify_api_key),
):
    """Send a question to the AI agent. Requires X-API-Key header."""
    bucket = api_key[:8]
    rate_limiter.check(bucket)
    cost_guard.check_budget(bucket)

    input_tokens = len(body.question.split()) * 2
    logger.info(json.dumps({
        "event": "agent_call",
        "q_len": len(body.question),
        "client": str(request.client.host) if request.client else "unknown",
    }))

    answer = llm_ask(body.question)

    output_tokens = len(answer.split()) * 2
    cost_guard.record_usage(bucket, input_tokens, output_tokens)

    return AskResponse(
        question=body.question,
        answer=answer,
        model=settings.llm_model,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/health", tags=["Operations"])
def health():
    """Liveness probe — platform restarts container if this fails."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Operations"])
def ready():
    """Readiness probe — load balancer stops routing if not ready."""
    if not _is_ready:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Not ready")
    return {"ready": True}


@app.get("/metrics", tags=["Operations"])
def metrics(api_key: str = Depends(verify_api_key)):
    """Basic metrics (protected)."""
    bucket = api_key[:8]
    usage = cost_guard.get_usage(bucket)
    return {
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "error_count": _error_count,
        **usage,
    }


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal_received", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on {settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
