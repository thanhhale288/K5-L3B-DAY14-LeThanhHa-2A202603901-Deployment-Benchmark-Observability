"""
API Key authentication (tiêu chí 6).

Yêu cầu:
  • Client gửi header  X-API-Key: <key>
  • Key phải trùng biến môi trường AGENT_API_KEY
  • Thiếu hoặc sai key → HTTP 401 (không phải 403 hay 422)
"""
import secrets

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# auto_error=False: nếu thiếu header, FastAPI KHÔNG tự trả lỗi mà đưa None vào hàm bên dưới,
# để mình tự trả 401. (Nếu khai báo header bắt buộc thì thiếu header sẽ ra 422.)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """Dependency cho FastAPI — dùng trong /ask: Depends(verify_api_key)."""
    expected = settings.agent_api_key
    # Thiếu header, hoặc server chưa cấu hình key (rỗng), hoặc key không khớp → 401.
    # compare_digest so sánh theo thời gian không đổi, tránh lộ key qua chênh lệch thời gian.
    # So sánh trên bytes (utf-8): compare_digest với str chứa ký tự không phải ASCII (vd "dán")
    # sẽ ném TypeError → 500. So bytes thì key lạ chỉ đơn giản là không khớp → 401.
    if (not api_key or not expected
            or not secrets.compare_digest(api_key.encode("utf-8"), expected.encode("utf-8"))):
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <your-key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
