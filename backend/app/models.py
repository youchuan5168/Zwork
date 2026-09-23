"""数据表模型（SQLModel）。"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, Integer, ForeignKeyConstraint, Index, Text, JSON, text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlmodel import Field, Relationship, SQLModel


def _now() -> datetime:
    return datetime.now()


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=64)
    password_hash: str
    created_at: datetime = Field(default_factory=_now)
    token_version: int = Field(
        default=0, sa_column=Column(Integer, nullable=False, server_default=text("0"))
    )
    is_active: bool = Field(default=True, nullable=False)
    bootstrap_slot: Optional[int] = Field(default=None, unique=True, index=True)


class Company(SQLModel, table=True):
    __tablename__ = "companies"
    __table_args__ = (
        Index("uq_companies_owner_name", "user_id", "name", unique=True),
        Index("uq_companies_id_owner", "id", "user_id", unique=True),
    )
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=128)
    industry: str = Field(default="", max_length=64)
    website: str = Field(default="", max_length=256)
    notes: str = Field(default="")
    created_at: datetime = Field(default_factory=_now)

    applications: list["Application"] = Relationship(
        back_populates="company",
        sa_relationship_kwargs={
            "cascade": "save-update, merge",
            "primaryjoin": "and_(Company.id == foreign(Application.company_id), Company.user_id == Application.user_id)",
        },
    )


class Application(SQLModel, table=True):
    __tablename__ = "applications"
    __table_args__ = (
        Index("uq_applications_id_owner", "id", "user_id", unique=True),
        Index("ix_applications_company_owner", "company_id", "user_id"),
        ForeignKeyConstraint(
            ["company_id", "user_id"],
            ["companies.id", "companies.user_id"],
            name="fk_applications_company_owner",
        ),
    )
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: Optional[int] = Field(default=None)
    company_name: str = Field(index=True, max_length=128)
    position: str = Field(index=True, max_length=128)
    channel: str = Field(default="", max_length=512)
    apply_date: date = Field(default_factory=date.today, index=True)
    current_stage: str = Field(default="not_started", index=True, max_length=32)
    notes: str = Field(default="")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    company: Optional[Company] = Relationship(
        back_populates="applications",
        sa_relationship_kwargs={
            "primaryjoin": "and_(Company.id == foreign(Application.company_id), Company.user_id == Application.user_id)"
        },
    )
    stages: list["ApplicationStage"] = Relationship(
        back_populates="application",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "primaryjoin": "and_(Application.id == foreign(ApplicationStage.application_id), Application.user_id == ApplicationStage.user_id)",
        },
    )
    schedules: list["Schedule"] = Relationship(
        back_populates="application",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "primaryjoin": "and_(Application.id == foreign(Schedule.application_id), Application.user_id == Schedule.user_id)",
        },
    )


class ApplicationStage(SQLModel, table=True):
    __tablename__ = "application_stages"
    __table_args__ = (
        Index("ix_application_stages_application_owner", "application_id", "user_id"),
        ForeignKeyConstraint(
            ["application_id", "user_id"],
            ["applications.id", "applications.user_id"],
            name="fk_application_stages_application_owner",
        ),
    )
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: int = Field(index=True)
    stage: str = Field(max_length=32)
    changed_at: datetime = Field(default_factory=_now)

    application: Application = Relationship(
        back_populates="stages",
        sa_relationship_kwargs={
            "primaryjoin": "and_(Application.id == foreign(ApplicationStage.application_id), Application.user_id == ApplicationStage.user_id)"
        },
    )


class Schedule(SQLModel, table=True):
    __tablename__ = "schedules"
    __table_args__ = (
        Index("ix_schedules_application_owner", "application_id", "user_id"),
        ForeignKeyConstraint(
            ["application_id", "user_id"],
            ["applications.id", "applications.user_id"],
            name="fk_schedules_application_owner",
        ),
    )
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)

    id: Optional[int] = Field(default=None, primary_key=True)
    application_id: Optional[int] = Field(default=None, index=True)
    title: str = Field(max_length=128)
    type: str = Field(default="其他", max_length=32)  # 笔试/一面/二面/HR面/其他
    sched_date: date = Field(index=True)
    sched_time: str = Field(default="", max_length=16)
    link: str = Field(default="", max_length=512)
    location: str = Field(default="", max_length=128)
    done: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=_now)

    application: Optional[Application] = Relationship(
        back_populates="schedules",
        sa_relationship_kwargs={
            "primaryjoin": "and_(Application.id == foreign(Schedule.application_id), Application.user_id == Schedule.user_id)"
        },
    )


class AuthThrottle(SQLModel, table=True):
    __tablename__ = "auth_throttles"
    key: str = Field(primary_key=True, max_length=64)
    window_started: int = Field(index=True)
    attempts: int


class AgentRun(SQLModel, table=True):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("uq_agent_runs_id_owner", "id", "user_id", unique=True),
        Index("uq_agent_runs_request", "user_id", "request_key", unique=True),
        Index("uq_agent_runs_active", "user_id", "active_slot", unique=True),
    )
    id: str = Field(primary_key=True, max_length=32)
    user_id: int = Field(foreign_key="users.id", index=True)
    request_key: str = Field(max_length=64)
    active_slot: Optional[int] = None
    token_version: int
    status: str = Field(default="queued", max_length=32)
    revision: int = 0
    skill: str = Field(default="assistant", max_length=32)
    model: str = Field(max_length=128)
    prompt_version: str = Field(max_length=64)
    prompt_hash: str = Field(max_length=64)
    tool_version: str = Field(max_length=32)
    timezone: str = Field(max_length=64)
    input_text: str = Field(sa_column=Column(Text, nullable=False))
    output_text: str = Field(default="", sa_column=Column(Text, nullable=False))
    state: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    pricing: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    pending: Optional[dict] = Field(default=None, sa_column=Column(JSON, nullable=True))
    steps: int = 0
    tool_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    execution_ms: int = 0
    error_code: str = Field(default="", max_length=64)
    created_at: datetime
    updated_at: datetime
    lease_until: Optional[datetime] = None


class AgentEvent(SQLModel, table=True):
    __tablename__ = "agent_events"
    __table_args__ = (
        Index("uq_agent_events_sequence", "run_id", "sequence", unique=True),
        Index("ix_agent_events_run_owner", "run_id", "user_id"),
        ForeignKeyConstraint(
            ["run_id", "user_id"], ["agent_runs.id", "agent_runs.user_id"],
            name="fk_agent_events_run_owner", ondelete="CASCADE",
        ),
    )
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(max_length=32)
    user_id: int = Field(foreign_key="users.id", index=True)
    sequence: int
    kind: str = Field(max_length=64)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    created_at: datetime


class CareerDocument(SQLModel, table=True):
    __tablename__ = "career_documents"
    __table_args__ = (Index("uq_career_documents_id_owner", "id", "user_id", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    kind: str = Field(max_length=16)
    title: str = Field(max_length=128)
    current_version: int = Field(default=1)
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CareerDocumentVersion(SQLModel, table=True):
    __tablename__ = "career_document_versions"
    __table_args__ = (
        Index("uq_career_document_versions_owner_id", "id", "user_id", unique=True),
        Index("uq_career_document_versions_number", "document_id", "version", unique=True),
        ForeignKeyConstraint(
            ["document_id", "user_id"], ["career_documents.id", "career_documents.user_id"],
            name="fk_career_document_versions_owner", ondelete="CASCADE",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    document_id: int = Field(index=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    version: int
    content: str = Field(sa_column=Column(Text().with_variant(LONGTEXT, "mysql"), nullable=False))
    source_name: str = Field(default="", max_length=128)
    content_sha256: str = Field(max_length=64)
    created_at: datetime = Field(default_factory=_now)


class CareerDocumentChunk(SQLModel, table=True):
    __tablename__ = "career_document_chunks"
    __table_args__ = (
        Index("uq_career_document_chunks_ordinal", "version_id", "ordinal", unique=True),
        ForeignKeyConstraint(
            ["version_id", "user_id"],
            ["career_document_versions.id", "career_document_versions.user_id"],
            name="fk_career_document_chunks_owner", ondelete="CASCADE",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    version_id: int = Field(index=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    ordinal: int
    content: str = Field(sa_column=Column(Text, nullable=False))


class CareerMemory(SQLModel, table=True):
    __tablename__ = "career_memories"
    __table_args__ = (
        ForeignKeyConstraint(
            ["source_version_id", "user_id"],
            ["career_document_versions.id", "career_document_versions.user_id"],
            name="fk_career_memories_source_owner", ondelete="CASCADE",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    category: str = Field(max_length=24)
    content: str = Field(sa_column=Column(Text, nullable=False))
    source_version_id: Optional[int] = Field(default=None, index=True)
    valid_until: Optional[date] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CareerTask(SQLModel, table=True):
    __tablename__ = "career_tasks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    title: str = Field(max_length=160)
    details: str = Field(default="", max_length=2000)
    due_date: Optional[date] = Field(default=None, index=True)
    done: bool = Field(default=False, index=True)
    completed_at: Optional[datetime] = None
    application_id: Optional[int] = Field(default=None, index=True)
    source_label: str = Field(default="", max_length=256)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CareerReview(SQLModel, table=True):
    __tablename__ = "career_reviews"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    application_id: Optional[int] = Field(default=None, index=True)
    schedule_id: Optional[int] = Field(default=None, index=True)
    source_label: str = Field(default="", max_length=256)
    occurred_on: date = Field(index=True)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    questions: list["InterviewQuestion"] = Relationship(
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "primaryjoin": "and_(CareerReview.id == foreign(InterviewQuestion.review_id), CareerReview.user_id == InterviewQuestion.user_id)",
        },
    )


class InterviewQuestion(SQLModel, table=True):
    """结构化逐题记录：面试中被问到的问题，随复盘整存整取。"""

    __tablename__ = "interview_questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    review_id: int = Field(index=True, nullable=False)
    # 冗余自所属复盘，保存时同步，供按岗位聚合题目集
    application_id: Optional[int] = Field(default=None, index=True)
    question: str = Field(max_length=500)
    answer: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=2000)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class RecruitmentPreference(SQLModel, table=True):
    __tablename__ = "recruitment_preferences"
    __table_args__ = (Index("uq_recruitment_preferences_user", "user_id", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False)
    platform: str = Field(default="boss", max_length=32)
    keyword: str = Field(default="", max_length=128)
    city: str = Field(default="", max_length=64)
    resume_document_id: Optional[int] = Field(default=None)
    updated_at: datetime = Field(default_factory=_now)


class RecruitmentJob(SQLModel, table=True):
    __tablename__ = "recruitment_jobs"
    __table_args__ = (
        Index("uq_recruitment_jobs_owner_url", "user_id", "url_key", unique=True),
        Index("ix_recruitment_jobs_owner_status", "user_id", "status"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True, nullable=False)
    platform: str = Field(max_length=32)
    url: str = Field(max_length=1024)
    url_key: str = Field(max_length=64)
    company_name: str = Field(max_length=128)
    position: str = Field(max_length=128)
    city: str = Field(default="", max_length=64)
    salary: str = Field(default="", max_length=64)
    description: str = Field(default="", sa_column=Column(Text, nullable=False))
    notes: str = Field(default="", sa_column=Column(Text, nullable=False))
    status: str = Field(default="saved", max_length=24)
    result_kind: str = Field(default="", max_length=24)
    application_id: Optional[int] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class UserLlmConfig(SQLModel, table=True):
    __tablename__ = "user_llm_configs"
    __table_args__ = (Index("uq_user_llm_configs_user", "user_id", unique=True),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", nullable=False)
    protocol: str = Field(default="openai_responses", max_length=32)
    api_url: str = Field(max_length=512)
    model: str = Field(max_length=128)
    encrypted_api_key: str = Field(sa_column=Column(Text, nullable=False))
    updated_at: datetime = Field(default_factory=_now)
