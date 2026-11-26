# ============================================================
# Production Dockerfile (tiêu chí 1): multi-stage, slim, non-root, HEALTHCHECK
# ============================================================

# ── Stage 1: builder — cài dependencies (có thể cần compiler, KHÔNG đưa sang image cuối)
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime — chỉ chép thư viện đã cài + code
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# User thường (không phải root) để giảm thiệt hại nếu app bị khai thác
RUN useradd --create-home --uid 1000 agent

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=agent:agent app ./app
COPY --chown=agent:agent utils ./utils

USER agent
EXPOSE 8000

# Gọi GET /health theo đúng PORT do platform cấp
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8000'), timeout=3)"

# `exec` để uvicorn thay shell làm PID 1 → nhận SIGTERM khi `docker stop` và tắt êm
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --timeout-graceful-shutdown 25"]
