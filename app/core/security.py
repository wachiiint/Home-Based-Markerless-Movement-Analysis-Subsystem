import secrets

from fastapi import Depends, Header, HTTPException, status

from app.core.config import Settings, get_settings


async def require_service_key(
    x_internal_service_key: str | None = Header(default=None, alias="X-Internal-Service-Key"),
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_internal_service_key or not secrets.compare_digest(
        x_internal_service_key,
        settings.service_api_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid service key",
        )
