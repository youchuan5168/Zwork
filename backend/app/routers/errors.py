from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.errors import BusinessError


async def business_error_handler(_: Request, error: BusinessError):
    return JSONResponse(
        status_code=error.status_code, content={"detail": error.detail}, headers=error.headers
    )
