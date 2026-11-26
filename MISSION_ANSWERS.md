# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns tìm thấy trong `01-localhost-vs-production/develop/app.py`

1. **API key và chuỗi kết nối database viết thẳng trong code** (dòng 17–18: `OPENAI_API_KEY = "sk-hardcoded-..."`, `DATABASE_URL = "postgresql://admin:password123@..."`). Push lên GitHub là lộ ngay, và muốn đổi key phải sửa code.
2. **Không có quản lý cấu hình** (dòng 21–22: `DEBUG = True`, `MAX_TOKENS = 500` cố định). Không đổi được giữa dev/staging/production nếu không sửa code.
3. **Dùng `print()` thay vì logging có cấu trúc** (dòng 33, 38). Không có level, không có thời gian, không phải JSON nên máy khó lọc/tìm.
4. **In secret ra log** (dòng 34: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")`). Khi chạy thật, key nằm trong log của nền tảng, ai xem log cũng thấy. Đã xác nhận khi chạy: log in ra `Using key: sk-hardcoded-fake-key-never-do-this`.
5. **Không có health check** (dòng 42–43). Gọi `GET /health` trả 404 (đã kiểm tra), nên nền tảng cloud không biết agent còn sống hay đã treo để restart.
6. **Port cố định 8000 và không đọc từ biến môi trường** (dòng 52: `port=8000`). Railway/Render cấp port qua biến `PORT`, nên app sẽ không nhận được traffic. Khi cổng 8000 bị chiếm thì không đổi port được nếu không sửa code (khác bản production chỉ cần đặt `PORT`).
7. **`host="localhost"`** (dòng 51). Chỉ nhận kết nối từ chính máy; trong container sẽ không ai truy cập được từ bên ngoài (cần `0.0.0.0`).
8. **`reload=True` (chế độ debug) luôn bật** (dòng 53). Tự restart khi file đổi, tốn tài nguyên và không an toàn ở production.
9. **Không xử lý tắt máy (graceful shutdown)**: không có handler SIGTERM hay lifespan, nên khi bị dừng có thể cắt ngang request đang chạy.
10. **Không xác thực, không kiểm tra dữ liệu vào** (dòng 30–31): ai cũng gọi được `/ask`; câu hỏi nhận qua query string nên gửi JSON bị 422 (đã kiểm tra).

### Exercise 1.2: Chạy bản develop

Môi trường: Python 3.13.9 trong venv `.venv`, `fastapi 0.115.0`, `uvicorn 0.30.0`. Chạy bằng `python app.py` đúng cổng 8000 (bản develop viết cứng port 8000 trong `uvicorn.run`, đây cũng là anti-pattern số 6).

```bash
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 422 Unprocessable Content        # bản develop không nhận JSON, chỉ nhận query

$ curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/health
404                                        # không có health check
```

Quan sát: app **chạy được** nhưng không production-ready (xem 10 vấn đề ở trên).

### Exercise 1.3: Bảng so sánh develop và production

Đã chạy bản production với `python app.py` (port 8000 lấy từ `PORT`, mặc định 8000):

```bash
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":3.7,"version":"1.0.0","environment":"development","timestamp":"..."}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) ...","model":"gpt-4o-mini"}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{}'
HTTP/1.1 422 Unprocessable Content
{"detail":"question field is required"}
```

Khi gửi SIGTERM, log ghi `Shutting down → Waiting for application shutdown → Application shutdown complete → Finished server process`: tắt có trình tự.

| Tính năng | Develop | Production | Tại sao quan trọng? |
|---|---|---|---|
| Cấu hình | Viết cứng trong code (`app.py` dòng 17–22, 52) | Đọc từ biến môi trường qua `config.py` (`os.getenv`), có giá trị mặc định | Đổi cấu hình giữa máy dev / staging / cloud mà không sửa code; không để secret trong repo |
| Secret (API key, DB URL) | Nằm trong code, còn bị in ra log | Lấy từ env (`OPENAI_API_KEY`, `AGENT_API_KEY`), không log secret | Lộ secret = bị lạm dụng và mất tiền; secret chỉ nên nằm ngoài code |
| Port / host | Cứng `localhost:8000` | `HOST`, `PORT` từ env, mặc định `0.0.0.0` | Cloud cấp port động qua `PORT`; trong container phải bind `0.0.0.0` mới truy cập được |
| Health check | Không có (`/health` → 404) | `GET /health` (liveness) và `GET /ready` (readiness) | Nền tảng biết khi nào phải restart (health) và khi nào chưa nên gửi traffic (ready) |
| Logging | `print()` chữ tự do, lộ secret | Dùng `logging` với `json.dumps({...})` và không log secret* | Log có cấu trúc dễ tìm/lọc/cảnh báo; không rò rỉ dữ liệu nhạy cảm |
| Shutdown | Không xử lý; bị dừng đột ngột | `lifespan` + handler SIGTERM; log "shutting down gracefully" | Hoàn thành request đang chạy, không mất dữ liệu khi deploy/scale |
| Debug / reload | `reload=True` luôn bật | `reload` chỉ bật khi `DEBUG=true` | Reload ở production tốn tài nguyên và không an toàn |
| Kiểm tra input | Query string `question: str`, không báo lỗi rõ | Đọc JSON, thiếu `question` → 422 + thông báo `question field is required` | Trả mã lỗi rõ ràng thay vì lỗi chung chung |
| Lifecycle | Không có | `lifespan` khởi tạo / dọn dẹp, cờ `is_ready` | Khởi tạo kết nối trước khi nhận traffic, dọn dẹp khi tắt |
| CORS | Không có | `CORSMiddleware` chỉ cho `ALLOWED_ORIGINS` | Kiểm soát trang web nào được gọi API từ trình duyệt |

\* Ghi chú quan sát thực tế: trong `production/app.py`, `config.py` được import (dòng 24) và gọi `logging.warning(...)` **trước** `logging.basicConfig(...)` (dòng 28). Vì vậy `basicConfig` không còn tác dụng, và khi chạy mình **không thấy** các dòng log JSON `agent_request`/`startup` (chỉ có log của uvicorn và dòng `WARNING:root:OPENAI_API_KEY not set`). Ý tưởng của bản production là đúng, nhưng định dạng JSON chưa thật sự được áp dụng trong lần chạy này. Đây là bài học cho Part 6: phải tự kiểm tra log ra đúng JSON thay vì tin vào cấu hình.

### Checkpoint 1 — tự kiểm tra

- Hardcode secret nguy hiểm vì code thường được push lên Git, ai có quyền đọc repo là lấy được key (và key còn nằm mãi trong lịch sử commit).
- Dùng biến môi trường: đặt giá trị ngoài code (ví dụ `PORT=8000 python app.py`), code đọc bằng `os.getenv`.
- Health check giúp nền tảng phát hiện agent treo để restart, còn `/ready` giúp load balancer chỉ gửi traffic khi agent sẵn sàng.
- Graceful shutdown = ngừng nhận request mới, xử lý xong request đang chạy rồi mới tắt.
- Một anti-pattern ở `develop/app.py` mà `production/app.py` đã sửa: `port=8000` cứng (dòng 52) → `port=settings.port` đọc từ `PORT` (dòng 197).

---

## Part 2: Docker

### Exercise 2.1: Câu hỏi về `02-docker/develop/Dockerfile`

1. **Base image:** `python:3.11` (dòng 8), bản Python đầy đủ gồm hệ điều hành Debian + Python + nhiều công cụ, khá nặng.
2. **Working directory:** `/app` (dòng 11, `WORKDIR /app`). Mọi lệnh sau đó chạy trong thư mục này trong container.
3. **Vì sao `COPY requirements.txt` trước:** Docker lưu cache theo từng lớp (layer). Danh sách thư viện ít đổi còn code hay đổi. Nếu copy và cài thư viện trước, khi chỉ sửa code thì Docker dùng lại lớp `pip install` đã cache, không phải cài lại; build nhanh hơn nhiều.
4. **CMD vs ENTRYPOINT:** `CMD` là lệnh mặc định, có thể bị ghi đè khi `docker run <image> <lệnh khác>`. `ENTRYPOINT` là lệnh cố định của container, tham số thêm vào chỉ được nối vào sau nó (muốn đổi phải dùng `--entrypoint`). File này dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Build và chạy bản develop

```bash
$ docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .      # chạy từ GỐC repo
$ docker run -d --name k5-dev -p 8000:8000 my-agent:develop
$ curl -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker?"
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":3.9,"container":true}
```

(`-p 8000:8000` nối cổng 8000 của máy với cổng 8000 trong container. Bản develop nhận `question` qua query string.)

### Exercise 2.3: Multi-stage build

- **Stage 1 (`builder`, `python:3.11-slim`):** cài `gcc`, `libpq-dev` và chạy `pip install --user -r requirements.txt` để cài thư viện vào `/root/.local`. Stage này chỉ dùng để build, không được deploy.
- **Stage 2 (`runtime`, `python:3.11-slim`):** tạo user thường `appuser` (không chạy bằng root), chỉ `COPY --from=builder /root/.local` sang (chỉ lấy kết quả cài đặt), copy code `main.py` và `utils/mock_llm.py`, có `HEALTHCHECK`, chạy `uvicorn` với 2 worker bằng `appuser`.
- **Vì sao image nhỏ hơn:** (1) dùng `slim` thay vì bản Python đầy đủ; (2) trình biên dịch `gcc`, `libpq-dev`, cache apt chỉ nằm ở stage builder và không được chép sang runtime; (3) runtime chỉ chứa Python + thư viện + code.

Kích thước đo bằng `docker images my-agent`:

```
REPOSITORY   TAG        SIZE
my-agent     advanced   266MB
my-agent     develop    1.67GB
```

- Develop: **1670 MB** (1.67 GB)
- Production (advanced): **266 MB**
- Chênh lệch: (1670 − 266) / 1670 ≈ **84%** nhỏ hơn. Production cũng đạt yêu cầu "< 500 MB".

(Ghi chú: `docker image inspect` cho số khác, 415 MB và 57,5 MB, vì đó là dung lượng nén của nội dung các lớp. Mình dùng số từ `docker images` theo yêu cầu đề; tỉ lệ nhỏ hơn vẫn xấp xỉ 86%.)

### Exercise 2.4: Docker Compose stack

Đã chạy bằng `docker compose -p k5-day14-docker up -d --build` trong `02-docker/production/` (sau `touch .env.local`).

**Các service** (đọc từ `docker-compose.yml`):

| Service | Image | Vai trò | Cổng mở ra ngoài |
|---|---|---|---|
| nginx | `nginx:alpine` | Reverse proxy + load balancer, giới hạn 10 req/s mỗi IP | 80, 443 |
| agent | build từ Dockerfile production | FastAPI agent (2 worker) | không, chỉ qua Nginx |
| redis | `redis:7-alpine` | Cache cho session, rate limiting | không |
| qdrant | `qdrant/qdrant:v1.9.0` | Vector database cho RAG | không |

**Sơ đồ:**

```
Client ──► Nginx :80 ──► Agent :8000 ──► Redis :6379
                              │
                              └────────► Qdrant :6333
        (tất cả nằm chung mạng nội bộ "internal"; chỉ Nginx mở cổng ra máy)
```

**Giao tiếp:** các container cùng mạng bridge `internal`, gọi nhau bằng **tên service** (ví dụ `agent:8000`, `redis://redis:6379/0`). Agent chỉ khởi động khi `redis` và `qdrant` báo `healthy` (`depends_on` + `service_healthy`); Nginx chờ agent. Khi chạy, cả 4 container đều `Up`, `agent`, `redis`, `qdrant` ở trạng thái `healthy`.

**Test qua Nginx (cổng 80):**

```bash
$ curl -i http://localhost/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":19.1,"version":"2.0.0","timestamp":"..."}

$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
HTTP/1.1 200 OK
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Kiểm tra thêm: `docker compose exec agent id` → `uid=999(appuser)`, xác nhận container chạy bằng user thường, không phải root. Đã dọn bằng `docker compose -p k5-day14-docker down`.

### Checkpoint 2 — tự kiểm tra

- Dockerfile là công thức build image; mỗi dòng tạo một layer được cache.
- Multi-stage build giúp image nhỏ (84% so với bản develop) và sạch hơn (không có công cụ build, chạy non-root).
- Docker Compose chạy nhiều container cùng lúc bằng một lệnh, dùng chung mạng và gọi nhau bằng tên service.
- Debug container: `docker logs <tên>`, `docker exec -it <tên> sh`, `docker compose -p <tên dự án> ps`.

## Part 3: Cloud Deployment

_(chưa làm — T6)_

## Part 4: API Security

Môi trường: venv `.venv`, `PyJWT 2.9.0`, chạy đúng cổng 8000. Token JWT trong output bên dưới đã được **che**.

### Exercise 4.1: API Key authentication (`04-api-gateway/develop/app.py`)

- **API key được kiểm tra ở đâu?** Hàm `verify_api_key` (dòng 39–54), gắn vào `/ask` bằng `Depends(verify_api_key)` (dòng 70). Header đọc bằng `APIKeyHeader(name="X-API-Key", auto_error=False)` (dòng 36); key đúng lấy từ biến môi trường `AGENT_API_KEY` (dòng 35).
- **Sai key thì sao?** Thiếu header → **401**; có header nhưng sai giá trị → **403** (không phải 401). Thực nghiệm bên dưới. (Lưu ý cho Part 6: script chấm yêu cầu cả thiếu lẫn sai key đều là 401.)
- **Rotate key thế nào?** Đổi giá trị biến môi trường `AGENT_API_KEY` trên server rồi khởi động lại; key cũ lập tức vô hiệu. Không phải sửa code. Hạn chế: chỉ có một key chung, đổi key là mọi client phải đổi theo.

```bash
$ AGENT_API_KEY=secret-key-123 python app.py

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: sai-key" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 4.2: JWT authentication (`04-api-gateway/production`)

Flow đọc từ `auth.py`: `POST /auth/token` kiểm tra username/password → tạo JWT (HS256) chứa `sub`, `role`, `iat`, `exp` (hết hạn sau 60 phút), ký bằng `JWT_SECRET`. Mỗi request sau đó gửi `Authorization: Bearer <token>`; server chỉ cần kiểm tra chữ ký và hạn, không tra database. Token hết hạn → 401, token sai/giả → 403.

```bash
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hi"}'
HTTP/1.1 401 Unauthorized
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

$ curl -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
{"access_token":"eyJhbGciOiJI...[đã che]","token_type":"bearer","expires_in_minutes":60,...}

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
{"question":"Explain JWT","answer":"...","usage":{"requests_remaining":9,"budget_remaining_usd":1.6e-05}}

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer abc.def.ghi" -H "Content-Type: application/json" -d '{"question":"x"}'
HTTP/1.1 403 Forbidden
{"detail":"Invalid token."}
```

(Dùng tài khoản `student` / `demo123` và endpoint `/auth/token` theo README K5, khác với `CODE_LAB.md`.)

### Exercise 4.3: Rate limiting (`rate_limiter.py`)

- **Thuật toán:** *sliding window* (cửa sổ trượt). Mỗi user có một `deque` các thời điểm gọi; mỗi lần kiểm tra thì bỏ các mốc cũ hơn 60 giây, đếm số còn lại, nếu ≥ giới hạn thì trả 429, ngược lại ghi thêm mốc hiện tại.
- **Giới hạn:** user thường **10 request/phút** (`rate_limiter_user`), admin **100 request/phút** (`rate_limiter_admin`).
- **Admin "bypass" thế nào?** Không phải bỏ qua hoàn toàn: app chọn limiter theo `role` trong JWT (`app.py` dòng 143: `rate_limiter_admin if role == "admin"`), nên admin có hạn mức cao hơn gấp 10 lần.
- Lưu ý: limiter lưu trong **RAM** (`defaultdict(deque)`), nên mất khi restart và không dùng chung giữa nhiều instance. Production phải chuyển sang Redis (đúng yêu cầu Part 6).

Kết quả vòng lặp: request đầu (200) + 15 request lặp = 16 request liên tiếp bằng token `student`:

```
req  1 -> 200   (response: requests_remaining = 9)
req  2..10 -> 200
req 11..16 -> 429
```

Response khi chạm giới hạn:

```
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
retry-after: 59
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

Kiểm chứng admin: dùng token `teacher` / `teach456` gọi 15 lần liên tiếp → cả 15 lần đều **200** (không bị chặn ở mức 10).

### Exercise 4.4: Cost guard (`cost_guard.py`)

File production đã cài sẵn `CostGuard` (lưu trong RAM). Cách làm:

1. **Tính tiền theo token:** `chi phí = input_tokens/1000 × 0.00015 + output_tokens/1000 × 0.0006` (đô-la, giá tham khảo gpt-4o-mini).
2. **Trước khi gọi LLM**, `check_budget(user)` kiểm tra: tổng chi phí **toàn hệ thống** ≥ $10/ngày → **503**; tổng chi phí **của user** ≥ $1/ngày → **402 Payment Required**; ≥ 80% ngân sách thì ghi log cảnh báo.
3. **Sau khi gọi LLM**, `record_usage(user, in_tokens, out_tokens)` cộng token và chi phí vào bản ghi của user trong ngày. Bản ghi gắn với ngày (`YYYY-MM-DD`), sang ngày mới sẽ tạo bản ghi mới → tự reset.
4. Thứ tự trong `/ask`: xác thực JWT → rate limit → `check_budget` → gọi LLM → `record_usage`.

Xác nhận qua `/me/usage` sau 10 request: `cost_usd: 0.000186`, `budget_usd: 1.0`, `budget_used_pct: 0.0`. Với mock LLM mỗi request chỉ tốn ~0,00002 USD nên **không thể chạm ngưỡng 402 bằng test thường**; mình chỉ kiểm chứng logic bằng cách đọc code (không bịa kết quả 402).

Phiên bản Redis theo đề bài (để dùng ở Part 6 vì state phải chịu được nhiều worker và restart):

```python
month_key = datetime.now().strftime("%Y-%m")
key = f"budget:{user_id}:{month_key}"
current = float(r.get(key) or 0)
if current + estimated_cost > 10: return False
r.incrbyfloat(key, estimated_cost); r.expire(key, 32*24*3600)
```

**Vì sao cần cả rate limit lẫn cost guard?** Rate limit bảo vệ **tốc độ** (chống bị dội liên tục), cost guard bảo vệ **tiền** (một người gọi chậm nhưng gửi câu rất dài vẫn đốt nhiều token mà không chạm rate limit).

### Checkpoint 3 — tự kiểm tra

- Đã thấy 401 (thiếu key/token), 403 (sai key/token), 200 (đúng), 429 (vượt 10 request/phút) bằng lệnh curl của mình.
- Hiểu flow JWT: lấy token một lần, gửi kèm mỗi request, server chỉ kiểm tra chữ ký và thời hạn.
- Rate limit theo tốc độ, cost guard theo tiền; cả hai bản lab đều lưu trong RAM nên Part 6 phải dùng Redis.

## Part 5: Scaling & Reliability

Ghi chú: code của Exercise 5.1–5.3 đã được viết sẵn trong repo (không có chỗ `TODO`), nên mình đọc code, giải thích và **chạy thật** để kiểm chứng. Stack chạy với tên dự án `-p k5-day14-scaling`, cổng 8080 (đã tắt container `odysseus-searxng-1` đang chiếm cổng này theo yêu cầu).

### Exercise 5.1: Health check và readiness (`05-scaling-reliability/develop/app.py`)

- **`GET /health` (liveness, dòng 104–144):** trả 200 cùng `status`, `uptime_seconds`, `version`, `environment`, `timestamp` và kiểm tra bộ nhớ (`checks.memory`). Trả `degraded` nếu RAM > 90%. Nền tảng gọi định kỳ; nếu lỗi/timeout thì **restart container**.
- **`GET /ready` (readiness, dòng 147–168):** trả 200 `{"ready": true, "in_flight_requests": N}` khi cờ `_is_ready = True` (sau khi khởi động xong), ngược lại **503**. Load balancer dùng nó để quyết định có gửi traffic vào instance này không (không cần restart).
- **Khác nhau:** liveness = "còn sống không" (hỏng → restart); readiness = "sẵn sàng phục vụ chưa" (chưa → tạm không gửi traffic). Ở bản stateless (`production/app.py`) `/ready` còn ping Redis và trả 503 nếu Redis lỗi.

```bash
$ python app.py
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":2.8,"version":"1.0.0","environment":"development",...,"checks":{"memory":{"status":"ok","used_percent":80.4}}}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true,"in_flight_requests":1}
```

### Exercise 5.2: Graceful shutdown

Cách làm trong code: `lifespan` đặt `_is_ready = False` khi tắt, rồi chờ `_in_flight_requests` về 0 (tối đa 30 giây); middleware `track_requests` đếm số request đang xử lý; `uvicorn.run(..., timeout_graceful_shutdown=30)`. Handler SIGTERM chỉ ghi log (uvicorn tự xử lý việc tắt).

Thử nghiệm: gửi một request rồi gửi `SIGTERM` ngay sau 30 ms:

```
$ (curl -i -X POST "http://localhost:8000/ask?question=Long%20task") &  ;  kill -TERM <pid>
HTTP/1.1 200 OK
{"answer":"Đây là câu trả lời từ AI agent (mock)..."}

# log của server (theo thứ tự):
INFO:     Shutting down
INFO:     127.0.0.1 - "POST /ask?question=Long%20task HTTP/1.1" 200 OK     <- request đang chạy vẫn được trả lời
INFO:     Waiting for application shutdown.
... 🔄 Graceful shutdown initiated...
... Received signal 15 — uvicorn will handle graceful shutdown
... ✅ Shutdown complete
INFO:     Finished server process
```

Kết luận: request đang xử lý **vẫn hoàn thành (200)** dù server đã nhận lệnh tắt. (Mock LLM chỉ ~0,1 giây nên đây là bằng chứng vừa đủ, không phải test với request dài.)

### Exercise 5.3: Stateless design (`05-scaling-reliability/production/app.py`)

- **Anti-pattern:** giữ lịch sử trong biến Python (`conversation_history = {}`). Mỗi instance có RAM riêng nên instance 2 không thấy dữ liệu mà instance 1 đã ghi; restart cũng mất sạch.
- **Cách làm đúng trong file:** mọi state lưu ở Redis: `save_session` dùng `setex("session:<id>", 3600, json)`, `load_session` dùng `get`, `append_to_history` cộng thêm tin nhắn (giữ tối đa 20 tin = 10 lượt). Bất kỳ instance nào cũng đọc/ghi cùng một chỗ.
- **Điểm cần lưu ý:** code có fallback sang dict trong RAM nếu không nối được Redis (`USE_REDIS=False`, in cảnh báo "not scalable"). Khi chạy trong compose, log cả 3 instance đều ghi `Storage: Redis ✅`, và response có `"storage":"redis"`.

### Exercise 5.4: Load balancing với Nginx

```bash
$ cd 05-scaling-reliability/production && touch .env.local
$ docker compose -p k5-day14-scaling up -d --build --scale agent=3
$ docker compose -p k5-day14-scaling ps
agent  k5-day14-scaling-agent-1  Up (healthy)
agent  k5-day14-scaling-agent-2  Up (healthy)
agent  k5-day14-scaling-agent-3  Up (healthy)
nginx  k5-day14-scaling-nginx-1  Up   0.0.0.0:8080->80/tcp
redis  k5-day14-scaling-redis-1  Up (healthy)
```

Nginx dùng DNS của Docker (`resolver 127.0.0.11`, `server agent:8000`) nên `agent` trỏ tới cả 3 container và request được chia vòng tròn. Gọi 10 request tới `POST http://localhost:8080/chat` (không session), đếm `served_by`:

```
4 instance-04ffdc
3 instance-29f882
3 instance-2d9b4c      -> chia gần đều cho 3 instance, tất cả "storage": "redis"
```

**Thử tắt một instance** (`docker stop k5-day14-scaling-agent-2`): tạo một session, rồi gửi tiếp 6 request cùng `session_id`. Cả 6 đều **200**, chỉ còn 2 instance phục vụ (`instance-29f882`, `instance-2d9b4c`), và history của session có **14 tin nhắn** (7 lượt × 2) không mất tin nào. Đã bật lại agent-2 sau đó.

### Exercise 5.5: Test stateless (`python test_stateless.py`)

Script tạo một session, gửi 5 câu hỏi liên tiếp rồi đọc lại history (script **không** tự tắt instance nào, khác mô tả trong `CODE_LAB.md`):

```
Session ID: 107e18f6-...
Request 1: [instance-04ffdc]   Request 2: [instance-29f882]   Request 3: [instance-2d9b4c]
Request 4: [instance-04ffdc]   Request 5: [instance-29f882]
Instances used: {'instance-04ffdc', 'instance-29f882', 'instance-2d9b4c'}
✅ All requests served despite different instances!
Total messages: 10      (5 câu hỏi + 5 câu trả lời)
✅ Session history preserved across all instances via Redis!
```

**Giải thích:** 5 request cùng session được 3 instance khác nhau xử lý, nhưng history vẫn đủ 10 tin vì mọi instance đều đọc/ghi cùng một Redis. Nếu lưu trong RAM thì mỗi instance chỉ thấy 1–2 tin. Đã dọn bằng `docker compose -p k5-day14-scaling down`; cổng 8080 đã trả lại.

### Checkpoint 4 — tự kiểm tra

- `/health` (còn sống? hỏng thì restart) khác `/ready` (sẵn sàng nhận traffic? chưa thì tạm đừng gửi), nên Part 6 yêu cầu `/health` luôn 200 còn `/ready` 503 khi mất Redis.
- State trong RAM hỏng khi chạy nhiều instance vì mỗi instance có bộ nhớ riêng, và restart là mất; Redis là nơi chung.
- Graceful shutdown: nhận SIGTERM → ngừng nhận mới → xong request đang chạy → thoát.
- Load balancing: Nginx chia vòng tròn tới các instance, một instance chết thì traffic dồn sang các instance còn lại.

## Output `check_production_ready.py` (📋 Checklist Deliverable)

_(chưa làm — T5c)_

---

## AI log

| # | Hỏi AI gì | Nhận được gì | Mình tự sửa / kiểm tra thế nào |
|---|---|---|---|
| 1 | Làm giúp Exercise 1.1–1.3 (đọc `develop/app.py`, `production/app.py`, chạy cả hai và điền bảng so sánh) | Danh sách anti-pattern kèm số dòng, các lệnh curl, bảng so sánh và ghi chú về thứ tự `basicConfig` | Đã đối chiếu từng số dòng với file thật; đã chạy lại cả hai bản và kiểm tra mã 200/404/422 cùng log. Cần đọc lại mục này và tự giải thích được trước khi nộp. |
| 2 | Làm giúp Part 2 (trả lời Exercise 2.1, build/chạy hai image, đo kích thước, chạy compose stack và test qua Nginx) | Câu trả lời, các lệnh docker, bảng service, sơ đồ | Đã tự chạy lại lệnh và đọc output `docker images`, `docker compose ps`, curl qua Nginx. Cần đọc lại và tự giải thích multi-stage / cache layer trước khi nộp. |
| 3 | Làm giúp Part 4 (đọc code, chạy bản API key và bản JWT, chạy vòng lặp 429, viết giải thích cost guard) | Các lệnh curl, kết quả 401/403/200/429, giải thích thuật toán sliding window và cost guard | Đã tự chạy và đọc output thật; token đã che. Cost guard 402 chưa thử được bằng chạy thật (chi phí mock quá nhỏ), chỉ giải thích qua code. Cần đọc lại và tự giải thích trước khi nộp. |
| 4 | Làm giúp Part 5 (đọc code 5.1–5.3, test SIGTERM, chạy stack 3 instance, `test_stateless.py`, thử tắt 1 instance) | Lệnh, output, giải thích liveness/readiness, graceful shutdown, stateless | Đã tự chạy và đọc output thật (kể cả đếm `served_by`, tắt agent-2). Test shutdown chỉ dùng request ~0,1 giây. Cần đọc lại và tự giải thích trước khi nộp. |
| 5 | Viết giúp Part 6 bước T5a: `app/config.py`, `app/auth.py`, JsonFormatter + `/health` + middleware log + handler lỗi 500 trong `app/main.py`, `.env.example` | Code 4 file, giải thích từng quyết định (auto_error=False, compare_digest, propagate=False…) | Đã tự chạy `check_production_ready.py --static-only` và chạy server thật: /health 200; thiếu/sai key 401; đúng key 200; body sai 422; 10/10 dòng log là JSON hợp lệ. Cần đọc lại và tự giải thích từng file trước khi nộp. |
| 6 | Viết giúp Part 6 bước T5b: `app/redis_client.py`, `rate_limiter.py` (Redis sorted set), `cost_guard.py` (incrbyfloat theo ngày), `/ready` và nối vào `/ask` | Code 3 file + sửa `main.py`, giải thích thuật toán và thứ tự xử lý | Đã chạy `check_production_ready.py --skip-docker`: tiêu chí 4–10 ✅, 11 ✅ phần chạy (Docker chưa kiểm tra). Cần đọc lại và tự giải thích trước khi nộp. |
| 7 | Viết giúp Part 6 bước T5c: `Dockerfile` (multi-stage, slim, non-root, HEALTHCHECK, exec CMD), `docker-compose.yml`, `.dockerignore`, `railway.toml`, `render.yaml` | 5 file cấu hình và giải thích | Đã chạy đầy đủ `check_production_ready.py`: PASS 12/12 (43/43 checks) và thử `docker compose up` thật. Chưa deploy lên cloud. Cần đọc lại và tự giải thích trước khi nộp. |
