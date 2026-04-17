# Deployment Information

## Public URL

```
https://lab12-production-c840.up.railway.app
```

---

## Platform

**Railway.app** — deploy từ Dockerfile, free tier có sẵn.

---

## Test Commands

### Health Check
```bash
curl https://lab12-production-c840.up.railway.app/health
# Expected: {"status":"ok","version":"1.0.0","environment":"production",...}
```

### Authentication Required (401)
```bash
curl -X POST https://lab12-production-c840.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: HTTP 401 {"detail":"Invalid or missing API key..."}
```

### API Test with Authentication (200)
```bash
curl -X POST https://lab12-production-c840.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is Docker?"}'
# Expected: HTTP 200 {"question":"...","answer":"...","model":"gpt-4o-mini",...}
```

### Rate Limiting Test (429)
```bash
for i in {1..12}; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://lab12-production-c840.up.railway.app/ask \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"question": "test"}')
  echo "Request $i: $STATUS"
done
# Expected: Requests 11+ return 429 Too Many Requests
```

### Web Chat UI
```
https://lab12-production-c840.up.railway.app/chat
```

---

## Environment Variables Set on Railway

| Variable | Value | Description |
|----------|-------|-------------|
| `PORT` | (auto-injected) | Railway inject tự động |
| `AGENT_API_KEY` | `your-secret-key` | API key để authenticate |
| `ENVIRONMENT` | `production` | Disable debug, docs |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max 10 req/min per key |
| `DAILY_BUDGET_USD` | `10.0` | Max $10/day LLM budget |

---

## Deploy Instructions (Railway)

### Step 1: Setup Railway
```bash
# Cài Railway CLI
npm install -g @railway/cli

# Login
railway login
```

### Step 2: Deploy
```bash
# Từ thư mục root của repo
railway init
railway up
```

### Step 3: Set Environment Variables
```bash
railway variables set AGENT_API_KEY=your-very-secret-key-here
railway variables set ENVIRONMENT=production
railway variables set RATE_LIMIT_PER_MINUTE=10
railway variables set DAILY_BUDGET_USD=10.0
```

### Step 4: Get Public URL
```bash
railway domain
# Hoặc vào dashboard Railway → Settings → Domains
```

---

## Local Run (for testing)

```bash
# Cài dependencies
pip install -r requirements.txt

# Set API key
export AGENT_API_KEY=dev-key-change-me

# Chạy app
uvicorn app.main:app --reload

# Mở chat UI
# http://localhost:8000/chat
```

---

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
