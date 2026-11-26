"""
Production AI Agent — Part 6 Final Project

T5a: /health, config từ env, log JSON, API key, xử lý lỗi gọn.
T5b: /ready, rate limit, cost guard (Redis), graceful shutdown (lifespan + SIGTERM của uvicorn).

Kiểm tra:
    python check_production_ready.py
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ──────────────────────────────────────────────────────────
# Log JSON (tiêu chí 10): mỗi dòng log của app là 1 JSON object
# ──────────────────────────────────────────────────────────
class JsonFormatter(logging.Formatter):
    """Biến mỗi log record thành đúng một dòng JSON."""

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        # Các trường thêm vào qua log_event(..., key=value)
        data.update(getattr(record, "fields", {}))
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False, default=str)


def _setup_logger() -> logging.Logger:
    log = logging.getLogger("agent")
    log.setLevel(logging.INFO)
    log.propagate = False  # không để root logger / uvicorn in lại theo định dạng khác
    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        log.addHandler(handler)
    return log


logger = _setup_logger()


def log_event(event: str, level: int = logging.INFO, **fields) -> None:
    """Ghi một dòng log JSON: log_event("request", path="/ask", status=200)."""
    logger.log(level, event, extra={"fields": fields})


START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    log_event("startup", environment=settings.environment, port=settings.port)
    yield
    # Shutdown: uvicorn nhận SIGTERM → ngừng nhận request mới, chờ request đang chạy xong, rồi tới đây
    log_event("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)


# ──────────────────────────────────────────────────────────
# Middleware: log mỗi request (không log header/key/nội dung câu hỏi)
# ──────────────────────────────────────────────────────────
@app.middleware("http")
async def access_log(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    log_event(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        ms=round((time.perf_counter() - start) * 1000, 1),
    )
    return response


# Lỗi không lường trước → 500 gọn, KHÔNG lộ stack trace cho client (chi tiết chỉ nằm trong log)
@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception):
    logger.error("unhandled_error", exc_info=exc, extra={"fields": {"path": request.url.path}})
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ──────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy, KHÔNG phụ thuộc Redis."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    """Readiness: 200 khi Redis ổn, 503 khi Redis không kết nối được (còn /health vẫn 200)."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"ready": True}


def _estimate_tokens(text: str) -> int:
    """Ước lượng thô: ~1.3 token / từ (mock LLM không trả số token thật)."""
    return max(1, int(len(text.split()) * 1.3))


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    # Thứ tự: xác thực (Depends) → rate limit → kiểm tra budget → gọi LLM → ghi chi phí
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    record_cost(_estimate_tokens(body.question), _estimate_tokens(answer))
    return {"question": body.question, "answer": answer}


# Graceful shutdown (tiêu chí 11): KHÔNG tự đăng ký handler SIGTERM, để uvicorn tự xử lý (xem lifespan).
