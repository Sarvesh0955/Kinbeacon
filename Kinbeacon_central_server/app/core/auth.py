from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> Optional[str]:
    """Validates the optional X-API-Key header.

    If settings.api_key is unset (default for development/demo), requests are allowed.
    """
    if settings.api_key is not None:
        if not x_api_key or x_api_key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing X-API-Key header",
            )
    return x_api_key
