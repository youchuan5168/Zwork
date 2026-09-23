"""模型适配层契约；领域层不依赖模型供应商。"""

from dataclasses import dataclass, field
from typing import Protocol, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunCreate(StrictModel):
    request_key: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    message: str = Field(min_length=1, max_length=12000)
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    skill: Literal[
        "assistant", "job_match", "career_manager",
        "daily_briefing", "interview_preparation", "application_follow_up", "weekly_review",
    ] = "assistant"

    @field_validator("message")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("请求不能为空")
        return value

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("无效的 IANA 时区") from None
        return value


class ApprovalDecision(StrictModel):
    approval_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    decision: Literal["approve", "reject"]


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: str


@dataclass(frozen=True)
class ModelTurn:
    text: str = ""
    calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class Provider(Protocol):
    async def complete(
        self, *, model: str, instructions: str, items: list, tools: list,
        max_output_tokens: int, timeout: float,
    ) -> ModelTurn: ...


class ProviderError(Exception):
    """只暴露稳定错误码，禁止透传供应商响应和密钥。"""
