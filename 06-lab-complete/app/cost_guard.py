"""
Cost guard (tiêu chí 8).

  • Cộng dồn chi phí LLM (tính theo token) vào Redis, theo từng ngày (UTC)
  • Tổng chi phí hôm nay >= DAILY_BUDGET_USD → HTTP 402
"""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _key() -> str:
    return "cost:" + datetime.now(timezone.utc).strftime("%Y-%m-%d")


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    try:
        spent = float(r.get(_key()) or 0)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Cost guard unavailable")
    if spent >= settings.daily_budget_usd:
        raise HTTPException(status_code=402, detail="Daily budget exhausted")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    try:
        pipe = r.pipeline()
        pipe.incrbyfloat(_key(), cost)
        pipe.expire(_key(), 3 * 24 * 3600)  # key tự xoá sau 3 ngày
        pipe.execute()
    except redis.RedisError:
        pass  # đã trả lời xong, không làm hỏng response chỉ vì không ghi được chi phí
    return cost
