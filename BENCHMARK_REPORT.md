# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Lê Thanh Hà (2A202603901)
**Ngày chạy:** 2026-11-26
**Môi trường:** MacBook (macOS), Python 3.13 venv, Docker qua Colima 4 CPU / 8GB RAM

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Mock LLM trả lời bình thường khoảng 200 ms; 500 ms cho phép dư gấp hơn 2 lần mà người dùng vẫn thấy nhanh. Dùng p95 vì average che mất nhóm request chậm. |
| Error rate `/ask` | < 2 % | Upstream LLM mặc định lỗi khoảng 1%; 2% cho phép dao động ngẫu nhiên nhưng vẫn báo động khi lỗi tăng gấp đôi (retry của client sẽ khắc phục lỗi lẻ). |
| Accuracy trên golden dataset | ≥ 100 % (mục tiêu) | Bộ 23 câu cố định là câu hỏi cốt lõi của sản phẩm; mỗi câu sai là một lỗi người dùng gặp thật. Mức tối thiểu của quality gate sẽ ghi ở mục 3. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.81 | 198.1 | 236.1 | 1709.3 | 0.33% | PASS |
| 10 | 35.7 | 196.0 | 228.5 | 1710.6 | 1.00% | PASS |
| 50 | 102.36 | 205.0 | 560.3 | 1707.8 | 1.00% | FAIL |
| 100 | 55.05 | 375.7 | 3597.1 | 3925.9 | 1.33% | FAIL |

**Nhận xét:** RPS có tăng gần tuyến tính ở mức thấp, rồi không còn tuyến tính: từ 1 lên 10 request song song RPS tăng 3,81 → 35,7 (gấp ~9,4 lần) vì mỗi request chủ yếu chờ mock LLM (~200 ms) nên nhiều request chờ cùng lúc không tranh nhau. Từ 10 lên 50 RPS chỉ tăng gấp ~2,9 lần (102,4) và p95 vượt SLO (560 ms), rồi ở 100 RPS **giảm** còn 55 với p95 3597 ms. Giải thích (suy luận, chưa đo riêng): agent chạy một process/một event loop nên khi quá tải các request xếp hàng chờ nhau, độ trễ tăng thay vì thông lượng tăng; thêm nữa mỗi lần đo chỉ 300 request nên ở mức 100 chỉ có ~3 "đợt" và số liệu dao động. Điểm tốt nhất của máy này là khoảng 10–50 request song song; trên mức đó phải scale thêm instance (Part 7 bước 2). Error rate ~1% ở mọi mức là lỗi upstream giả lập `MOCK_ERROR_RATE=0.01` (503), không phải do tải.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 195.4 | 222.1 | 229.6 |
| 0.03 (mặc định) | 249.8 | 233.5 | 1706.2 |
| 0.1 | 304.8 | 1681.9 | 1721.2 |

**Nhận xét:** **p99 nhạy nhất** với request chậm ở mức 3%: khi `MOCK_SLOW_RATE=0.03`, p95 gần như không đổi (233,5 ms) nhưng p99 nhảy từ 229,6 lên 1706,2 ms. Khi tăng lên 0,1 thì request chậm đã đủ nhiều để kéo cả p95 lên 1681,9 ms. Average thì tăng chậm hơn nhiều (195 → 250 → 305 ms) và vẫn trông "chấp nhận được" dù cứ 100 người có 1–3 người chờ gần 2 giây. Vì vậy SLO phải đặt theo p95/p99: average trộn lẫn nhóm chậm vào số đông nhanh nên che mất đúng nhóm người dùng đang gặp vấn đề.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.7 | 108.8 | 117.3 |
| Tổng cost (USD) | 0.000412 | 0.000758 | 0.000822 |
| Cost / câu đúng (USD) | 0.00041175 | 0.00003607 | 0.00003573 |
| Quality gate | FAIL (ngưỡng ≥ 80%) | PASS (ngưỡng ≥ 80%) | PASS (ngưỡng ≥ 100%) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 ("JWT khác gì API key trong xác thực?") | `token`, `hết hạn`, `chữ ký` | Knowledge base không có tài liệu nào khớp "jwt"/"api key" nên agent trả câu chung chung. Thêm một tài liệu với từ khoá `["jwt", "api key"]` giải thích API key là chuỗi tĩnh không tự hết hạn, còn JWT là token có chữ ký và thời hạn (`exp`). |
| scaling-03 ("Kubernetes HPA scale dựa trên những chỉ số nào?") | `cpu`, `memory`, `custom metrics` | Không có tài liệu nào khớp "kubernetes"/"hpa". Thêm tài liệu với từ khoá `["kubernetes", "hpa"]` nêu HPA scale theo CPU, memory và custom metrics. |

Chỉ sửa `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` (không đụng `golden_dataset.jsonl`), chọn từ khoá riêng cho từng câu để không "cướp" câu khác; kết quả: 23/23 đúng, 0 câu regression so với v2 ban đầu.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

v1 không có retrieval nên chỉ đúng 1/23 (4,3%); v2 thêm bước tìm tài liệu (RAG) nên lên 91,3% rồi 100% sau khi sửa KB. Cái giá: prompt dài hơn nên token trung bình/câu tăng từ 57,7 lên khoảng 109–117 (gần gấp đôi) và tổng chi phí tăng tương ứng, thêm bước retrieval ~20 ms (p95 v1 190 ms so với v2 221 ms ở lần chạy đầu). Nhưng **cost trên mỗi câu ĐÚNG** giảm mạnh, từ ~$0,000412 (v1, chỉ 1 câu đúng) xuống ~$0,000036 (v2): v1 rẻ hơn mỗi câu nhưng gần như toàn câu sai nên tiền bỏ ra gần như vô ích. Lưu ý: p95 1551,8 ms ở lần chạy cuối là do request "chậm bất thường" ngẫu nhiên của mock (MOCK_SLOW_RATE=0,03, 23 mẫu nên chỉ cần 1–2 request chậm là p95 nhảy), không phải do thay đổi KB.

**Quality gate là gì và dùng thế nào:** `run_eval.py` trả exit code khác 0 khi accuracy dưới ngưỡng (`--min-accuracy`) hoặc có câu bị regression so với `--baseline`. Đưa lệnh này vào CI trước bước deploy thì phiên bản làm chất lượng tụt sẽ bị chặn tự động, không cần ai đọc báo cáo. v1 fail ngưỡng 80%, v2 pass.

---

## 4. Observability stack (production)

### 4.0 Exercise 7.4 — đọc dashboard khi có tải

Stack chạy bằng `docker compose -p k5-day14-observability up -d --build --scale agent=2` (2 agent + Nginx + Prometheus + Grafana + Jaeger + Locust). Tải: Locust 30 user, ramp-up 5, chạy khoảng 2,5 phút. Số bên dưới lấy bằng truy vấn Prometheus (cùng PromQL với các panel Grafana) tại thời điểm đó, cửa sổ 1 phút.

1. **p95 và avg:** p95 `/ask` ≈ **296 ms**, avg ≈ **239 ms**. Khoảng cách ~57 ms cho thấy có một nhóm nhỏ request chậm hơn hẳn kéo đuôi phân phối lên (đúng với `MOCK_SLOW_RATE=0.03`), trong khi phần lớn request nhanh nên average trông ổn. Đó là lý do SLO đặt theo p95/p99. (Error rate cùng lúc ≈ 1,5%, gần mức 1% do `MOCK_ERROR_RATE` cộng dao động ngẫu nhiên.)
2. **Nginx có chia đều cho 2 instance không?** Có: ≈ 9,33 req/s và 9,24 req/s (chênh dưới 1%), khớp với round-robin mặc định của Nginx.
3. **Vì sao input tokens/s lớn hơn output tokens/s?** Đo được input ≈ 1351 token/s so với output ≈ 718 token/s. Ở agent v2 prompt gồm câu hỏi **cộng thêm tài liệu lấy từ knowledge base (context RAG)**, nên dài hơn nhiều so với câu trả lời.
4. **`curl http://localhost:8080/metrics` trả gì?** **404**. Nginx cố tình không chuyển tiếp `/metrics` ra ngoài, để người ngoài không đọc được số liệu nội bộ; Prometheus scrape trực tiếp từng agent trong mạng Docker nên vẫn lấy được (cả 2 target `up`).

> Lưu ý: file `production/Dockerfile` của lab bị lỗi khi chạy ("No module named 'uvicorn'", container restart liên tục) vì `useradd -d /app` làm HOME=/app còn thư viện nằm ở `/home/agent/.local`. Mình thêm một dòng `ENV PYTHONUSERBASE=/home/agent/.local` để sửa; không đổi gì khác.

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [x] Một trace lỗi trong Jaeger (có event `exception`)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (đổi lúc 20:16:24 → vào trạng thái pending 20:16:52 → firing ~20:17:52; script đo thấy firing lúc 20:17:56) | ~92 giây | Panel Error rate (suy luận từ ý nghĩa panel; mình chưa nhìn tận mắt panel) |
| B | `MOCK_SLOW_RATE=0.3` | _(chưa làm)_ | | |
| C | `LLM_MODEL=mock-llm-large` | _(chưa làm; không có số liệu sạch)_ | | |
| D | `docker pause` 1 instance (`agent-1`, đổi lúc 20:18:13) | `AgentInstanceDown` (pending 20:18:27, firing ~20:18:57) | ~44 giây | Panel/instance up (suy luận); Locust ghi nhận lỗi 502/504 từ Nginx |
| E | `AGENT_VERSION=v1` | _(chưa làm)_ | | |

Ghi chú về cách làm: làm 2 thí nghiệm (A rồi D) và **không trả cấu hình A về cũ** giữa hai thí nghiệm, nên có ≥ 2 alert firing cùng lúc để chụp trang Alerts. Trước khi chạy, `promtool test rules` trên `alert_rules_test.yml` báo `SUCCESS`. Quan sát thêm: (1) `LLMCostBurnRateHigh` đã firing ngay từ đầu (tốc độ đo được ~$2,06/giờ, vừa trên ngưỡng $2) chỉ vì 30 user Locust chạy lâu, nên không làm được thí nghiệm C "sạch" và mình bỏ qua; (2) ngay sau khi `docker compose up -d` tạo lại agent, Nginx trả 502 một lúc vì còn giữ địa chỉ IP cũ của container; (3) khi pause `agent-1`, Locust thấy 504/502 từ Nginx trong lúc Prometheus chưa kịp đánh dấu instance down.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Mình **chưa chạy thí nghiệm E**, nên đây là trả lời dựa trên số đo ở mục 3 chứ không phải kết quả quan sát: agent v1 vẫn trả 200 nhanh và rẻ, nên error rate, latency, up đều bình thường, nhưng accuracy chỉ 4,3% (1/23) so với v2. Các alert hạ tầng chỉ nhìn "chạy được chưa", không nhìn "trả lời đúng chưa". Cách bắt: (1) chạy **eval định kỳ** trên golden dataset với agent đang chạy thật (hoặc canary) và báo khi accuracy tụt dưới ngưỡng, đúng quality gate ở mục 3; (2) metric `agent_info{version=...}` trong `/metrics` để biết phiên bản nào đang chạy và so với phiên bản mong đợi; (3) thu phản hồi người dùng (thumbs up/down) và chấm mẫu ngẫu nhiên một phần câu trả lời; (4) chạy eval trong CI trước khi deploy để chặn từ đầu.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `1a8e632d1627b9197ddb719e04452ab0` (chọn request chậm nhất trong log của agent lúc chạy tải, rồi mở lại đúng trace đó trong Jaeger qua `/api/traces/<trace_id>`)
- Tổng thời gian: 1784,5 ms (span gốc `POST /ask`)
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (**1646,6 ms, 92%**). Các span còn lại: `agent.retrieve_context` 130,5 ms (7%, cũng chậm bất thường so với ~25 ms bình thường) và `agent.run` 1777,9 ms bao trùm cả hai.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-26T13:04:23.132535+00:00", "level": "INFO", "service": "observable-agent", "instance": "d747c76a78cb", "event": "llm_call", "trace_id": "1a8e632d1627b9197ddb719e04452ab0", "span_id": "918c6895dc1fe12a", "request_id": "9de1bab93bce", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1644.9}
{"ts": "2026-11-26T13:04:23.133287+00:00", "level": "INFO", "service": "observable-agent", "instance": "d747c76a78cb", "event": "http_request", "trace_id": "1a8e632d1627b9197ddb719e04452ab0", "span_id": "918c6895dc1fe12a", "request_id": "9de1bab93bce", "method": "POST", "route": "/ask", "status": 200, "ms": 1782.0}
```

**Kết luận:** thủ phạm là bước gọi LLM, không phải code của agent. Đây là request nằm trong nhóm ~3% "chậm bất thường" của `MOCK_SLOW_RATE`.

**Trace lỗi (bổ sung):** `trace_id` `7151b50938171c7673a3d207a0445af0`, 101,5 ms, span `POST /ask`, `agent.run` và `chat mock-llm-small` đều có `error=true`; span `chat mock-llm-small` và `agent.run` có event `exception`. Log `llm_error` cùng `trace_id` ghi `Upstream LLM error: 503 Service Unavailable (mock)` và `http_request` ghi `status: 503`.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59.99 | 200 | 280 | 1700 | 63 / 7115 (0.89%) |
| 3 | 59.65 | 200 | 260 | 1700 | 55 / 7127 (0.77%) |

Số liệu là dòng `/ask` trong `production/benchmark-results/scale_1_stats.csv` và `scale_3_stats.csv` (Locust headless, 100 user, ramp-up 10, 2 phút; các lần chạy trước đó đã đưa cấu hình về mặc định `MOCK_ERROR_RATE=0.01`, `mock-llm-small`, v2).

**Giải thích kết quả:** Scale từ 1 lên 3 instance **gần như không đổi gì**: RPS 59,99 → 59,65, p50 đều 200 ms, p99 đều 1700 ms, p95 chỉ 280 → 260 ms (nằm trong dao động ngẫu nhiên). Failures ~0,8–0,9% ở cả hai, đúng bằng `MOCK_ERROR_RATE=0.01` chứ không phải do thiếu máy. Nghĩa là **agent không phải nút thắt ở mức tải này**: mỗi request chủ yếu chờ bước gọi LLM (~120–200 ms trong mock, và ~3% request chậm tới ~1,7 s, như đã thấy trong trace ở mục 4.3), thời gian chờ này không giảm khi thêm instance. Một instance đã đủ xử lý ~60 req/s nên instance thứ 2, 3 chỉ ngồi chờ. Thông lượng ~66 req/s (cả `/ask` lẫn `/health`) còn bị **chính tải của Locust giới hạn**: `locustfile.py` đặt `wait_time = between(0.5, 2)` (trung bình 1,25 s nghỉ giữa các request) nên 100 user chỉ tạo ra tối đa khoảng 100 / (1,25 + ~0,22) ≈ 68 req/s, trùng với số đo (65,9 và 65,6). Vì vậy dù có thêm instance, tải đưa vào cũng không tăng. Muốn p95/p99 tốt hơn phải giảm latency của LLM (model nhanh hơn, cache, timeout + retry cho request chậm), không phải thêm agent. Thêm instance chỉ giúp khi CPU của agent hoặc số kết nối là điểm nghẽn, mà ở đây chưa phải.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Trung bình che mất đuôi.** Chỉ 3% request chậm đã đẩy p99 từ ~230 ms lên ~1700 ms trong khi avg chỉ nhích nhẹ, nên SLO phải đặt theo p95/p99 (mục 2.2).
  2. **Trace + log có chung `trace_id` giúp tìm nguyên nhân rất nhanh:** từ một request chậm 1784 ms, trace chỉ ra ngay bước gọi LLM chiếm 92% (mục 4.3), thay vì đoán trong code của mình.
  3. **Scale ngang không phải lúc nào cũng nhanh hơn:** khi nút thắt là LLM bên ngoài thì 1 hay 3 instance cho cùng p95 (mục 5); và alert phải được kiểm chứng bằng cách thật sự "phá" hệ thống (mục 4.2), vì có sự cố như đổi sang agent v1 không làm alert nào kêu mà chất lượng vẫn tụt.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

Mình sẽ thêm: (a) alert **chất lượng** chạy eval định kỳ trên golden dataset (accuracy giảm → báo), vì thí nghiệm E cho thấy alert hạ tầng không bắt được lỗi trả lời sai; (b) alert **p99** và tỉ lệ request vượt timeout, không chỉ p95; (c) alert **ngân sách chi phí theo ngày** thay vì chỉ tốc độ đốt tiền theo giờ; (d) metric tỉ lệ hit của retrieval (câu hỏi không tìm thấy tài liệu) và độ dài prompt; (e) alert Redis (kết nối, bộ nhớ) vì rate limit và cost guard phụ thuộc vào nó.

---

## Phụ lục: Exercise 7.1 (metrics của `develop/app.py`)

- **Counter** (chỉ tăng): `http_requests_total{method,route,status}`, `llm_requests_total`, `llm_tokens_total`, `llm_cost_usd_total`.
- **Gauge** (lên xuống): `agent_in_flight_requests` (số request đang xử lý), `agent_info` (luôn = 1, mang nhãn phiên bản).
- **Histogram** (phân phối theo bucket): `http_request_duration_seconds`, `llm_request_duration_seconds`.
- **Vì sao label `route` dùng `route.path` (template như `/ask`) chứ không dùng URL thật?** Mỗi giá trị label khác nhau tạo một chuỗi thời gian riêng. URL thật có thể chứa id/tham số (ví dụ `/chat/<session_id>/history`) nên số chuỗi tăng không giới hạn ("bùng nổ cardinality"), làm Prometheus tốn RAM. Template chỉ có vài giá trị cố định; request không khớp route nào được gom vào `unmatched`.
- **Metric đã thêm:** Histogram `agent_question_length_chars` (buckets 10–2000 ký tự) trong `develop/app.py`, ghi bằng `QUESTION_LENGTH.observe(len(body.question))` ở đầu `/ask`. Kiểm tra `/metrics` sau 1 request 23 ký tự: `agent_question_length_chars_count 1.0`, `agent_question_length_chars_sum 23.0`.
