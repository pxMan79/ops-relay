from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
import os

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key():
    return os.environ.get("API_TOKEN", "")


async def verify_api_key(api_key: str = Security(api_key_header)):
    expected = get_api_key()
    if not expected:
        return True
    if not api_key or api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return True
