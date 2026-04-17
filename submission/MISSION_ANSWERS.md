# Day 12 Lab - Mission Answers

> **Student Name:** Le Huu Hung  
> **Date:** 17/04/2026

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcoded API key** — `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`: Nếu push lên GitHub thì key bị lộ ngay lập tức. Attacker có thể dùng key này tạo chi phí bất hạn.

2. **Hardcoded database credentials** — `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`: Username/password database trong source code. Bất cứ ai đọc code đều biết credentials.

3. **Dùng `print()` thay vì structured logging** — `print(f"[DEBUG] Got question: {question}")`: Trong production không thể filter, search, hay aggregate logs. Không có level (INFO/WARNING/ERROR), không có timestamp chuẩn.

4. **Log ra secret** — `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`: Secret key được ghi vào stdout/log files. Ai có quyền đọc log đều thấy API key.

5. **Không có health check endpoint**: Nếu agent crash, platform (Railway/K8s) không biết để restart. Container có thể đang chạy nhưng không phục vụ được request.

6. **Hardcoded host `"localhost"`** — `host="localhost"`: Chỉ accept connections từ chính machine đó. Trong Docker container, external requests sẽ bị từ chối. Phải dùng `"0.0.0.0"`.

7. **Hardcoded port `8000`** — `port=8000`: Railway/Render inject PORT qua environment variable. Nếu cứng port thì app sẽ lắng nghe sai port, platform không route được traffic.

8. **Debug reload trong production** — `reload=True`: Uvicorn reload liên tục watch file changes — tốn CPU, giảm performance, tiềm ẩn security risk. Chỉ dùng khi develop local.

---

### Exercise 1.3: Comparison table — Develop vs Production

| Feature | Develop (❌) | Production (✅) | Tại sao quan trọng? |
|---------|------------|----------------|-------------------|
| **Config** | Hardcoded trong code (`OPENAI_API_KEY = "sk-..."`) | Environment variables (`os.getenv("OPENAI_API_KEY")`) | Tách config khỏi code, không lộ secret trên GitHub |
| **Logging** | `print("[DEBUG] ...")` | Structured JSON logging với level, timestamp | Có thể search, aggregate, alert trong production |
| **Secrets** | API key, DB password ghi thẳng trong code | Không có giá trị thật trong code, chỉ có `.env.example` | Prevent credential leak, comply với security policy |
| **Host** | `host="localhost"` | `host="0.0.0.0"` | Accept external connections trong Docker/cloud |
| **Port** | `port=8000` cứng | `port=int(os.getenv("PORT", 8000))` | Tương thích với Railway/Render PORT injection |
| **Health check** | Không có | `GET /health` và `GET /ready` | Platform biết khi nào restart/route traffic |
| **Graceful shutdown** | Không có | SIGTERM handler, `timeout_graceful_shutdown=30` | Finish in-flight requests trước khi dừng |
| **Reload** | `reload=True` luôn luôn | `reload=settings.debug` (False trong production) | Performance và stability |
| **Error handling** | Không có try/catch | HTTPException với status codes phù hợp | API client biết lỗi gì và cách xử lý |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. **Base image của develop Dockerfile**: `python:3.11` (full distribution, ~1 GB)
2. **Base image của production Dockerfile**: `python:3.11-slim` (minimal, ~200 MB)
3. **WORKDIR**: `/build` (stage 1), `/app` (stage 2)
4. **Tại sao copy `requirements.txt` trước source code?**: Docker layer caching — nếu requirements không đổi, layer `pip install` được cache, build nhanh hơn nhiều
5. **USER instruction**: Chạy app với non-root user `agent` → giảm attack surface nếu container bị compromise
6. **HEALTHCHECK**: Platform tự động restart container nếu health check fail liên tục

### Exercise 2.3: Image size comparison

| | Develop | Production |
|--|---------|-----------|
| **Base image** | `python:3.11` | `python:3.11-slim` |
| **Build stages** | 1 stage | 2 stages (multi-stage) |
| **Image size** | ~1.0 GB | ~200-250 MB |
| **Build tools** | Included | Chỉ ở stage 1, không copy sang runtime |
| **Difference** | — | ~75% nhỏ hơn |

**Tại sao multi-stage nhỏ hơn?** Stage 1 cài `gcc`, `libpq-dev` để compile packages. Stage 2 chỉ copy `.local` (Python packages đã compiled) và source code — không có compiler, không có build tools.

### Exercise 2.4: Docker Compose architecture

```
docker-compose.yml
│
├── service: agent (port 8000:8000)
│   ├── build: . (Dockerfile)
│   ├── env: ENVIRONMENT=staging, REDIS_URL=redis://redis:6379/0
│   ├── depends_on: redis (service_healthy)
│   └── healthcheck: /health endpoint
│
└── service: redis (redis:7-alpine)
    ├── command: maxmemory 128mb, allkeys-lru eviction
    └── healthcheck: redis-cli ping
```

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

- **Platform**: Railway.app
- **URL**: `https://lab12-production-c840.up.railway.app`
- **Screenshot**: [Xem screenshots/dashboard.png](screenshots/dashboard.png)

**Environment variables đã set trên Railway:**
- `AGENT_API_KEY` — API key bí mật
- `ENVIRONMENT` — `production`
- `RATE_LIMIT_PER_MINUTE` — `10`
- `DAILY_BUDGET_USD` — `10.0`
- `PORT` — Railway tự inject

**Deploy steps:**
```bash
# Cài Railway CLI
npm install -g @railway/cli

# Login và deploy
railway login
railway init
railway up

# Set environment variables
railway variables set AGENT_API_KEY=your-secret-key-here
railway variables set ENVIRONMENT=production
```

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication — Test results

```bash
# Test 1: Không có API key → 401 Unauthorized
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Response:
# HTTP 401
# {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}

# Test 2: Sai API key → 401 Unauthorized
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: wrong-key" \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'

# Response:
# HTTP 401
# {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}

# Test 3: Đúng API key → 200 OK
curl -X POST http://localhost:8000/ask \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'

# Response:
# HTTP 200
# {"question":"What is Docker?","answer":"Docker is a containerization platform...","model":"gpt-4o-mini","timestamp":"2026-04-17T..."}
```

**Nơi API key được verify**: `app/auth.py` → hàm `verify_api_key()`, sử dụng FastAPI `Security(APIKeyHeader)` dependency injection vào mỗi protected endpoint.

### Exercise 4.3: Rate Limiting

**Algorithm**: Sliding Window Counter  
**Limit**: 10 requests/minute per API key  
**Implementation**: `app/rate_limiter.py` — class `RateLimiter`

```bash
# Test: Gửi 12 request liên tiếp
for i in {1..12}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/ask \
    -H "X-API-Key: dev-key-change-me" \
    -H "Content-Type: application/json" \
    -d '{"question": "test"}')
  echo "Request $i: $STATUS"
done

# Output:
# Request 1: 200
# Request 2: 200
# ...
# Request 10: 200
# Request 11: 429  ← Rate limit exceeded
# Request 12: 429
```

**Response khi vượt limit (429 Too Many Requests):**
```json
{"detail": "Rate limit exceeded: 10 req/min. Retry after 58s."}
```
**Headers:**
- `X-RateLimit-Limit: 10`
- `X-RateLimit-Remaining: 0`
- `Retry-After: 58`

### Exercise 4.4: Cost Guard Implementation

**Approach**: Daily token budget tracking per user.

```python
# app/cost_guard.py
class CostGuard:
    def check_budget(self, user_id):
        # Raise 402 nếu user vượt $10/ngày
        if record.total_cost_usd >= self.daily_budget_usd:
            raise HTTPException(status_code=402, detail={"error": "Daily budget exceeded"})
    
    def record_usage(self, user_id, input_tokens, output_tokens):
        # Tính cost: $0.00015/1K input + $0.0006/1K output (GPT-4o-mini pricing)
        cost = input_tokens / 1000 * 0.00015 + output_tokens / 1000 * 0.0006
```

**Flow trong `/ask` endpoint:**
1. `cost_guard.check_budget(bucket)` — kiểm tra trước khi gọi LLM
2. Gọi LLM, nhận response
3. `cost_guard.record_usage(bucket, input_tokens, output_tokens)` — ghi nhận usage

**Response khi vượt budget (402 Payment Required):**
```json
{"detail": {"error": "Daily budget exceeded", "used_usd": 10.001, "budget_usd": 10.0, "resets_at": "midnight UTC"}}
```

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health Checks

**Liveness probe** (`/health`):
- Trả về 200 OK khi app đang chạy
- Chứa: uptime, version, environment, request count
- Platform dùng để **restart container** nếu fail

**Readiness probe** (`/ready`):
- Trả về 200 OK chỉ khi app hoàn toàn sẵn sàng nhận traffic
- Trả về 503 trong quá trình startup (`_is_ready = False`)
- Load balancer dùng để **stop routing** khi app đang khởi động

```python
# app/main.py
@app.get("/health")
def health():
    return {"status": "ok", "uptime_seconds": ..., "version": ...}

@app.get("/ready")
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}
```

### Exercise 5.2: Graceful Shutdown

```python
# app/main.py
def _handle_signal(signum, _frame):
    logger.info(json.dumps({"event": "signal_received", "signum": signum}))

signal.signal(signal.SIGTERM, _handle_signal)

# uvicorn với timeout_graceful_shutdown=30 giây
uvicorn.run(..., timeout_graceful_shutdown=30)
```

**Flow khi shutdown:**
1. Platform gửi `SIGTERM` signal
2. `_handle_signal()` log sự kiện
3. Uvicorn dừng nhận request mới
4. Chờ tối đa 30 giây cho in-flight requests hoàn thành
5. Container dừng hoàn toàn

### Exercise 5.3: Stateless Design

**Vấn đề với stateful (in-memory)**: Mỗi instance giữ state riêng → scale ngang không đồng bộ, session bị mất khi restart.

**Giải pháp**: Dùng Redis làm shared state store.

```
Client → Load Balancer → Instance 1 ─┐
                       → Instance 2 ─┼─→ Redis (shared state)
                       → Instance 3 ─┘
```

**Trong code hiện tại**: Rate limiter và cost guard dùng in-memory dict. Để thực sự stateless, thay `defaultdict(deque)` bằng Redis commands (`ZADD`, `ZCOUNT`, `INCR`).

**docker-compose.yml** đã include Redis service:
```yaml
services:
  agent:
    environment:
      - REDIS_URL=redis://redis:6379/0
  redis:
    image: redis:7-alpine
```

### Exercise 5.4: Load Balancing

```bash
# Scale lên 3 instances
docker compose up --scale agent=3

# Kết quả: 3 containers agent_1, agent_2, agent_3
# Load balancer distribute traffic round-robin
# Redis đảm bảo state nhất quán giữa các instances
```

### Exercise 5.5: Test Stateless

```bash
# Gửi nhiều request, kiểm tra state persist
for i in {1..5}; do
  curl -X POST http://localhost:8000/ask \
    -H "X-API-Key: dev-key-change-me" \
    -H "Content-Type: application/json" \
    -d '{"question": "Request '$i'"}'
  sleep 0.5
done

# Rate limit counter tích lũy đúng → state persistent
# Thử kill 1 container → 2 containers còn lại vẫn hoạt động
# Counter tiếp tục từ Redis (nếu dùng Redis), hoặc reset (nếu in-memory)
```
