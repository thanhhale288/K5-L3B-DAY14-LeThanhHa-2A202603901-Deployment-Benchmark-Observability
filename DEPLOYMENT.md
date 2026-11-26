# Deployment Information

## Public URL
https://k5-l3b-day14-lethanhha-2a202603901.onrender.com

## Platform
Render (Web Service chạy Docker, gói Free) + Render Key Value (Redis)

Root Directory: `06-lab-complete` · Health Check Path: `/health`

## Test Commands

Thay `<YOUR_KEY>` bằng giá trị `AGENT_API_KEY` đã đặt trên Render (không ghi vào repo).
Gói Free ngủ khi không có request, lần gọi đầu có thể mất khoảng 50 giây.

### Health Check
```bash
curl -i https://k5-l3b-day14-lethanhha-2a202603901.onrender.com/health
# Expected: HTTP 200  {"status":"ok",...}
```

### Readiness (kiểm tra Redis)
```bash
curl -i https://k5-l3b-day14-lethanhha-2a202603901.onrender.com/ready
# Expected: HTTP 200  {"ready":true}
```

### API Test — không có key
```bash
curl -i -X POST https://k5-l3b-day14-lethanhha-2a202603901.onrender.com/ask \
  -H "Content-Type: application/json" -d '{"question":"Hi"}'
# Expected: HTTP 401
```

### API Test — có key
```bash
curl -i -X POST https://k5-l3b-day14-lethanhha-2a202603901.onrender.com/ask \
  -H "X-API-Key: <YOUR_KEY>" -H "Content-Type: application/json" \
  -d '{"question":"What is deployment?"}'
# Expected: HTTP 200  {"question":...,"answer":...}
```

## Environment Variables Set (trên Render dashboard, không có trong code)
- `AGENT_API_KEY` (secret)
- `REDIS_URL` (Internal URL của Render Key Value)
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE=10`
- `DAILY_BUDGET_USD=1.0`
- `PORT` do Render tự cấp

## Kết quả kiểm tra thật (đã chạy)
`/health` 200 · `/ready` 200 · `/ask` không key 401 · `/ask` sai key 401 · `/ask` đúng key 200 · 12 request liên tiếp: 200 ×9 rồi 429 ×3 (có `retry-after`).
`python check_production_ready.py --public-url <URL>` trong `06-lab-complete/`: **PASS 12/12 (44/44 checks)**.

## Screenshots
Xem `screenshots/dashboard.png`, `screenshots/running.png`, `screenshots/test.png`.
