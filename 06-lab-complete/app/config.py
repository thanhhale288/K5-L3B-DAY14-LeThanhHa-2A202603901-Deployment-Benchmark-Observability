"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

Mỗi giá trị đọc bằng os.getenv(TÊN, mặc_định):
  • Có đặt biến môi trường → dùng giá trị đó.
  • Không đặt → dùng mặc định "hợp lý khi chạy local".
Không có secret thật nào được viết trong file này: AGENT_API_KEY mặc định rỗng,
nghĩa là nếu quên đặt key thì mọi request tới /ask đều bị từ chối (xem app/auth.py).
"""
import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass
class Settings:
    # default_factory = đọc biến môi trường lúc tạo Settings(), không phải lúc định nghĩa class
    port: int = field(default_factory=lambda: _int("PORT", 8000))
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    agent_api_key: str = field(default_factory=lambda: os.getenv("AGENT_API_KEY", ""))
    redis_url: str = field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))
    rate_limit_per_minute: int = field(default_factory=lambda: _int("RATE_LIMIT_PER_MINUTE", 10))
    daily_budget_usd: float = field(default_factory=lambda: _float("DAILY_BUDGET_USD", 1.0))


settings = Settings()
