"""应用装配点；导入应用不连接数据库，支持独立测试实例。"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.middleware import SecurityMiddleware
from sqlalchemy import text
from app.core.config import Settings, settings
from app.core.errors import BusinessError
from app.routers.errors import business_error_handler
from app.db.session import initialize_database
from app.routers.api import api_router

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(
    config: Settings | None = None, *, engine=None, frontend_dist: Path | None = None,
    agent_provider=None,
):
    config = config or settings

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config.validate_runtime()
        application.state.engine = engine if engine is not None else initialize_database(config)
        try:
            yield
        finally:
            if engine is None:
                application.state.engine.dispose()

    application = FastAPI(
        title="Zwork API",
        version="0.3.0",
        lifespan=lifespan,
        docs_url=None if config.app_env == "production" else "/docs",
        redoc_url=None if config.app_env == "production" else "/redoc",
        openapi_url=None if config.app_env == "production" else "/openapi.json",
    )
    application.state.settings = config
    # 仅内部注入点，用于隔离 Provider 测试；HTTP 不允许选择 Provider 或传入密钥。
    application.state.agent_provider = agent_provider
    application.add_exception_handler(BusinessError, business_error_handler)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        # Never echo passwords, tokens, notes or uploaded personal data.
        details = [
            {"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": details})

    application.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    application.add_middleware(SecurityMiddleware, config=config)
    application.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)

    @application.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok"}

    @application.get("/api/ready", tags=["health"])
    def ready():
        try:
            with application.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return {"status": "ok"}
        except Exception:
            return JSONResponse(status_code=503, content={"status": "unavailable"})

    dist = (frontend_dist or FRONTEND_DIST).resolve()
    if (dist / "index.html").is_file():
        if (dist / "assets").is_dir():
            application.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @application.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="接口不存在")
            target = (dist / full_path).resolve()
            if not target.is_relative_to(dist):
                raise HTTPException(status_code=404, detail="文件不存在")
            return FileResponse(target if full_path and target.is_file() else dist / "index.html")
    else:

        @application.get("/")
        def root():
            return {
                "service": "Zwork",
                "hint": "前端未构建，请执行 npm run build；接口文档见 /docs",
            }

    return application
