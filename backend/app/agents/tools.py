"""强类型工具注册表，身份来自服务端，数据权限复用 Service。"""

import json
from datetime import date
from typing import Literal
from pydantic import Field, ValidationError
from sqlmodel import Session
from app.agents.contracts import StrictModel
from app.core.errors import BusinessError
from app.services.applications import ApplicationService
from app.services.schedules import ScheduleService
from app.services.profile import ProfileService
from app.services.career import CareerService
from app.models import User

VERSION = "tools-v1"
MATCH_VERSION = "job-match-tools-v1"
CAREER_VERSION = "career-tools-v1"
Stage = Literal[
    "not_started", "applied", "screening", "written_test", "interview", "offer",
    "rejected", "withdrawn",
]


class SearchApplications(StrictModel):
    keyword: str | None = Field(max_length=128)
    stage: Stage | None
    limit: int = Field(ge=1, le=50)


class ApplicationHistory(StrictModel):
    application_id: int = Field(gt=0)


class UpcomingSchedules(StrictModel):
    start_date: date
    end_date: date
    limit: int = Field(ge=1, le=50)


class ChangeStage(StrictModel):
    application_id: int = Field(gt=0)
    stage: Stage


class MatchDocuments(StrictModel):
    resume_document_id: int = Field(gt=0)
    jd_document_id: int = Field(gt=0)


class SearchDocuments(StrictModel):
    query: str = Field(min_length=2, max_length=200)
    kind: Literal["resume", "jd", "project"] | None
    limit: int = Field(ge=1, le=5)


class GetProfile(StrictModel):
    pass


class GetDailyBriefing(StrictModel):
    day: date


class GetWeeklyReview(StrictModel):
    start: date


class GetInterviewContext(StrictModel):
    schedule_id: int = Field(gt=0)


class GetFollowupContext(StrictModel):
    application_id: int = Field(gt=0)


SPECS = {
    "search_applications": (SearchApplications, "按关键词和阶段搜索投递，返回有界结果", False),
    "get_application_history": (ApplicationHistory, "获取指定投递的阶段历史", False),
    "get_upcoming_schedules": (UpcomingSchedules, "查询日期区间内未完成安排，最多90天", False),
    "change_application_stage": (ChangeStage, "申请更新指定投递阶段，必须经用户审批", True),
}

MATCH_SPECS = {
    "match_documents": (MatchDocuments, "匹配用户的简历与 JD，返回版本、词面证据和待核实要求", False),
    "search_documents": (SearchDocuments, "检索当前版本的用户文档片段，返回来源版本", False),
    "get_profile": (GetProfile, "读取用户明确保存且未过期的求职记忆", False),
}

CAREER_READ_SPECS = {
    "get_daily_briefing": (GetDailyBriefing, "读取指定日期的待办、安排和停滞投递简报", False),
    "get_weekly_review": (GetWeeklyReview, "读取指定一周的投递、阶段、日程、复盘和已完成待办", False),
    "get_interview_context": (GetInterviewContext, "读取自己的一场面试日程、投递、JD 证据和既有复盘", False),
    "get_followup_context": (GetFollowupContext, "读取自己的投递、阶段历史与关联日程", False),
}

CAREER_SPECS = {
    "search_applications": SPECS["search_applications"],
    "get_upcoming_schedules": SPECS["get_upcoming_schedules"],
    **CAREER_READ_SPECS,
    "search_documents": MATCH_SPECS["search_documents"],
    "get_profile": MATCH_SPECS["get_profile"],
}

# Zwork 助手是统一的 AI 入口：既能处理基础投递查询/阶段审批，也能按需
# 读取简报、周回顾、面试上下文、文档和用户明确保存的画像信息。
ASSISTANT_SPECS = {
    **SPECS,
    **CAREER_READ_SPECS,
    "search_documents": MATCH_SPECS["search_documents"],
    "get_profile": MATCH_SPECS["get_profile"],
}

SKILL_SPECS = {
    "assistant": ASSISTANT_SPECS, "job_match": MATCH_SPECS,
    "career_manager": CAREER_SPECS,
    "daily_briefing": {"get_daily_briefing": CAREER_READ_SPECS["get_daily_briefing"],
                       "get_profile": MATCH_SPECS["get_profile"]},
    "interview_preparation": {
        "get_interview_context": CAREER_READ_SPECS["get_interview_context"],
        "search_documents": MATCH_SPECS["search_documents"],
        "get_profile": MATCH_SPECS["get_profile"],
    },
    "application_follow_up": {
        "search_applications": SPECS["search_applications"],
        "get_followup_context": CAREER_READ_SPECS["get_followup_context"],
        "get_profile": MATCH_SPECS["get_profile"],
    },
    "weekly_review": {"get_weekly_review": CAREER_READ_SPECS["get_weekly_review"],
                      "get_profile": MATCH_SPECS["get_profile"]},
}
SKILL_VERSIONS = {"assistant": VERSION, "job_match": MATCH_VERSION,
                  **{name: CAREER_VERSION for name in (
                      "career_manager", "daily_briefing", "interview_preparation",
                      "application_follow_up", "weekly_review",
                  )}}


def schemas(skill="assistant"):
    result = []
    for name, (model, description, _) in SKILL_SPECS[skill].items():
        parameters = model.model_json_schema()
        # Strict tool schemas require every declared property in `required`;
        # nullable fields remain explicit by accepting null in their type.
        parameters["required"] = list(parameters.get("properties", {}))
        result.append({"type": "function", "name": name, "description": description,
                       "parameters": parameters, "strict": True})
    return result


def validate(name, arguments, skill="assistant"):
    specs = SKILL_SPECS[skill]
    if name not in specs:
        raise BusinessError("工具不在白名单", 400)
    try:
        body = specs[name][0].model_validate_json(arguments, strict=True)
    except (ValidationError, ValueError, TypeError):
        raise BusinessError("工具参数无效", 400) from None
    if isinstance(body, UpcomingSchedules) and not 0 <= (body.end_date - body.start_date).days <= 90:
        raise BusinessError("日期区间必须在90天以内", 400)
    return body


def verify(session, actor, token_version):
    user = session.get(User, actor.user_id)
    if not user or not user.is_active or user.token_version != token_version:
        raise BusinessError("运行身份已撤销", 401)


def read(engine, actor, name, body, token_version):
    with Session(engine) as session:
        verify(session, actor, token_version)
        if name in CAREER_READ_SPECS:
            career = CareerService(session, actor)
            if name == "get_daily_briefing":
                result = career.briefing(body.day)
                keys = ("recent_applications", "stale_applications", "schedules", "tasks")
                return {**result, **{f"total_{key}": len(result[key]) for key in keys},
                        **{key: result[key][:12] for key in keys}}
            if name == "get_weekly_review":
                result = career.weekly(body.start)
                limits = {"applications": 12, "stage_changes": 20, "schedules": 12,
                          "reviews": 8, "completed_tasks": 12}
                return {**result, **{f"total_{key}": len(result[key]) for key in limits},
                        **{key: result[key][:limit] for key, limit in limits.items()}}
            if name == "get_interview_context":
                return career.interview_context(body.schedule_id)
            return career.followup_context(body.application_id)
        if name in MATCH_SPECS:
            profile = ProfileService(session, actor)
            if name == "match_documents":
                result = profile.match(body.resume_document_id, body.jd_document_id)
                return {**result, "matched": result["matched"][:8], "gaps": result["gaps"][:8],
                        "total_matched": len(result["matched"]), "total_gaps": len(result["gaps"])}
            if name == "search_documents":
                return {"items": profile.search(body.query, body.kind, body.limit)}
            return {"items": [
                {"id": row.id, "category": row.category, "content": row.content[:300],
                 "source_version_id": row.source_version_id}
                for row in profile.active_memories()[:10]
            ]}
        if name == "search_applications":
            total, rows = ApplicationService(session, actor).search(body.keyword, body.stage, body.limit)
            return {"total": total, "items": [
                {"id": a.id, "company_name": a.company_name, "position": a.position,
                 "apply_date": str(a.apply_date), "current_stage": a.current_stage}
                for a in rows[:body.limit]
            ]}
        if name == "get_application_history":
            rows = ApplicationService(session, actor).history(body.application_id)
            return {"items": [{"stage": a.stage, "changed_at": a.changed_at.isoformat()}
                              for a in rows[-50:]], "total": len(rows)}
        total, rows = ScheduleService(session, actor).upcoming(body.start_date, body.end_date, body.limit)
        return {"total": total, "items": [
            {"id": s.id, "title": s.title, "application_id": s.application_id,
             "date": str(s.sched_date), "time": s.sched_time, "type": s.type}
            for s in rows[:body.limit]
        ]}


def snapshot(engine, actor, body, token_version):
    with Session(engine) as session:
        verify(session, actor, token_version)
        row = ApplicationService(session, actor).get(body.application_id)
        return {"application_id": row.id, "company_name": row.company_name,
                "position": row.position, "stage": row.current_stage,
                "updated_at": row.updated_at.isoformat()}

def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
