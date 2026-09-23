"""请求/响应入参模型（Pydantic）。"""

from datetime import date
import re
from typing import Optional
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=15, max_length=72)

    @field_validator("username")
    @classmethod
    def username_policy(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z0-9_.-]{2,64}", value):
            raise ValueError("新用户名须为 2～64 位字母、数字或 _.-")
        return value

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("密码的 UTF-8 编码长度不能超过 72 字节")
        return value


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=15, max_length=72)

    @field_validator("new_password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        return RegisterIn.password_byte_limit(value)


class ApplicationIn(BaseModel):
    company_id: Optional[int] = None
    company_name: str = Field(min_length=1, max_length=128)
    position: str = Field(min_length=1, max_length=128)
    channel: str = Field(default="", max_length=512)  # 支持粘贴长链接作为渠道记录
    apply_date: date = Field(default_factory=date.today)
    current_stage: str = Field(default="not_started", max_length=32)
    notes: str = Field(default="")


class StageIn(BaseModel):
    stage: str = Field(max_length=32)


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    industry: str = Field(default="", max_length=64)
    website: str = Field(default="", max_length=256)
    notes: str = Field(default="")


class ScheduleIn(BaseModel):
    application_id: Optional[int] = None
    title: str = Field(min_length=1, max_length=128)
    type: str = Field(default="其他", max_length=32)
    sched_date: date
    sched_time: str = Field(default="", max_length=16)
    link: str = Field(default="", max_length=512)
    location: str = Field(default="", max_length=128)
    done: bool = False


class LlmConfigIn(BaseModel):
    protocol: str = Field(default="openai_responses", max_length=32)
    api_url: str = Field(min_length=12, max_length=512)
    model: str = Field(min_length=1, max_length=128)
    api_key: Optional[str] = Field(default=None, max_length=256)

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, value):
        if value not in {"openai_responses", "deepseek_chat"}:
            raise ValueError("接口协议仅支持 openai_responses 或 deepseek_chat")
        return value

    @field_validator("api_url")
    @classmethod
    def validate_url(cls, value):
        from app.core.config import Settings
        try:
            return Settings.validate_agent_api_url(value)
        except ValueError:
            raise ValueError(
                "接口地址必须是 HTTPS 完整端点（不含查询参数），如 https://api.openai.com/v1/responses"
            ) from None

    @model_validator(mode="after")
    def validate_protocol_matches_url(self):
        path = re.sub(r"/+$", "", urlsplit(self.api_url).path)
        if self.protocol == "openai_responses" and path.endswith("/chat/completions"):
            raise ValueError("该地址是 Chat Completions 端点，请将接口协议改为「Chat Completions 兼容」")
        if self.protocol == "deepseek_chat" and path.endswith("/responses"):
            raise ValueError("该地址是 OpenAI Responses 端点，请将接口协议改为「OpenAI Responses」")
        return self


class LlmConfigOut(BaseModel):
    configured: bool
    protocol: str = "openai_responses"
    api_url: str = ""
    model: str = ""
    key_masked: str = ""
    updated_at: str = ""
