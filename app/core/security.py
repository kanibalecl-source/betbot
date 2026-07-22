import hmac

from fastapi import Header, HTTPException, status
from app.core.config import get_settings


def validate_security_configuration() -> None:
    settings = get_settings()
    key = str(settings.api_key or "")
    if settings.environment in {"staging", "production"} and len(key) < 32:
        raise RuntimeError("API_KEY with at least 32 characters is required in staging/production")


def api_key_matches(provided: str | None) -> bool:
    expected = str(get_settings().api_key or "")
    candidate = str(provided or "")
    return bool(expected) and hmac.compare_digest(candidate, expected)


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not api_key_matches(x_api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
