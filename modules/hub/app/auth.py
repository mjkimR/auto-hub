import secrets

from app.common.config import get_auth_config
from app_base.core.log import logger
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(x_api_key: str = Security(api_key_header)) -> None:
    """Verify the API key provided in the request header.

    Usage:
        APIRouter(..., dependencies=[Depends(verify_api_key)])
    """
    secret_key = get_auth_config().APP_SECRET_KEY
    if not secret_key:
        logger.error("Authentication misconfigured: APP_SECRET_KEY is not set.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid or missing API key",
        )
    if not x_api_key or not secrets.compare_digest(x_api_key, secret_key.get_secret_value()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
