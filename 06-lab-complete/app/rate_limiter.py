"""
Rate limiting (tiêu chí 7): sliding window 60 giây, state lưu trong Redis.

Mỗi API key có 1 sorted set "rl:<hash>": member = id duy nhất của request,
score = thời điểm request. Mỗi lần gọi:
  ZREMRANGEBYSCORE  xoá request cũ hơn 60 giây
  ZCARD             đếm request còn lại trong cửa sổ
  ZADD              ghi request này
  EXPIRE            tự xoá key nếu không ai gọi nữa
"""
import hashlib
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    # Băm key để không lưu API key thật trong Redis
    rkey = "rl:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    now = time.time()
    try:
        r.zremrangebyscore(rkey, 0, now - WINDOW_SECONDS)
        count = r.zcard(rkey)
        if count >= settings.rate_limit_per_minute:
            oldest = r.zrange(rkey, 0, 0, withscores=True)
            wait = int(oldest[0][1] + WINDOW_SECONDS - now) + 1 if oldest else WINDOW_SECONDS
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": str(max(wait, 1))},
            )
        pipe = r.pipeline()
        pipe.zadd(rkey, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.expire(rkey, WINDOW_SECONDS + 5)
        pipe.execute()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable")
