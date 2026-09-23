"""应用配置：从 backend/.env 读取。"""

from pathlib import Path
from typing import Literal
from pydantic import SecretStr, Field, HttpUrl, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    app_env: Literal["development", "test", "production"] = "development"
    registration_open: bool = False
    allowed_hosts: list[str] = ["*"]
    jwt_expire_minutes: int = 30
    jwt_issuer: str = "qiuzhao"
    jwt_audience: str = "qiuzhao-api"
    auth_rate_window_seconds: int = 300
    auth_login_ip_limit: int = 20
    auth_login_account_limit: int = 10
    auth_register_ip_limit: int = 5
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    database_url: str | None = None
    auto_create_database: bool = True
    auto_create_tables: bool = True

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "qiuzhao"

    jwt_secret: str = "change-me"

    agent_enabled: bool = False
    agent_api_url: str = ""
    agent_provider: Literal["openai_responses", "deepseek_chat"] = "openai_responses"
    openai_api_key: SecretStr = SecretStr("")
    agent_model: str = ""
    agent_max_steps: int = 6
    agent_max_tool_calls: int = 10
    agent_max_total_tokens: int = 30000
    agent_max_output_tokens: int = 1500
    agent_timeout_seconds: int = 60
    agent_approval_ttl_seconds: int = 900
    agent_max_context_bytes: int = 20000
    agent_max_estimated_cost_usd: float = Field(default=0, ge=0, allow_inf_nan=False)
    agent_input_usd_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    agent_output_usd_per_million: float = Field(default=0, ge=0, allow_inf_nan=False)
    agent_run_limit_per_window: int = Field(default=30, ge=1)
    agent_rate_window_seconds: int = Field(default=3600, ge=1, le=86400)

    @field_validator("agent_api_url")
    @classmethod
    def validate_agent_api_url(cls, value):
        if not value:
            return value
        try:
            url = TypeAdapter(HttpUrl).validate_python(value)
            if (url.scheme != "https" or url.username is not None or url.password is not None
                    or url.query is not None or url.fragment is not None):
                raise ValueError
        except ValueError:
            raise ValueError("AGENT_API_URL 必须是无凭据、查询参数和片段的 HTTPS 完整端点") from None
        return str(url)

    @property
    def db_url(self) -> str | URL:
        return self.database_url or URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password,
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_db,
            query={"charset": "utf8mb4"},
        )

    def validate_runtime(self):
        if min(
            self.agent_max_steps, self.agent_max_tool_calls, self.agent_max_total_tokens,
            self.agent_max_output_tokens, self.agent_timeout_seconds,
            self.agent_approval_ttl_seconds, self.agent_max_context_bytes,
        ) <= 0:
            raise ValueError("Agent 预算参数必须为正数")
        if self.agent_enabled and (not self.agent_model or not self.openai_api_key.get_secret_value() or not self.agent_api_url):
            raise ValueError("启用 Agent 时必须设置 AGENT_MODEL、OPENAI_API_KEY 和 AGENT_API_URL")
        if self.agent_max_estimated_cost_usd and min(
            self.agent_input_usd_per_million, self.agent_output_usd_per_million,
        ) <= 0:
            raise ValueError("费用预算需配置输入/输出每百万 Token 的美元单价")
        if len(self.jwt_secret) < 32 or self.jwt_secret == "change-me":
            raise ValueError("JWT_SECRET 必须是至少 32 位的随机密钥，包括开发环境")
        if not 1 <= self.jwt_expire_minutes <= 60:
            raise ValueError("JWT_EXPIRE_MINUTES 必须为 1～60")
        if (
            min(
                self.auth_rate_window_seconds,
                self.auth_login_ip_limit,
                self.auth_login_account_limit,
                self.auth_register_ip_limit,
            )
            <= 0
        ):
            raise ValueError("认证限流参数必须为正数")
        if self.app_env == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret == "change-me":
                raise ValueError("生产环境 JWT_SECRET 必须是至少 32 位的随机密钥")
            if self.auto_create_database or self.auto_create_tables:
                raise ValueError("生产环境必须禁用自动建库建表，使用 Alembic 迁移")
            if not self.allowed_hosts or any("*" in host for host in self.allowed_hosts):
                raise ValueError("生产环境 ALLOWED_HOSTS 必须是明确域名，禁止通配符")
            if any(
                not origin.startswith("https://") or "*" in origin for origin in self.cors_origins
            ):
                raise ValueError("生产环境 CORS_ORIGINS 必须是明确的 HTTPS 来源")


settings = Settings()
