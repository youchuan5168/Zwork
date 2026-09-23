"""Authenticated workbench facts, action tasks, and user-written reviews."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session

from app.core.actor import Actor
from app.db.session import get_session
from app.deps import get_actor
from app.services.career import CareerService

router = APIRouter(prefix="/api/career", tags=["career"])


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskInput(StrictInput):
    title: str = Field(min_length=1, max_length=160)
    details: str = Field(default="", max_length=2000)
    due_date: date | None = None
    application_id: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("标题不能为空")
        return value


class TaskDone(StrictInput):
    done: bool


class QuestionInput(StrictInput):
    question: str = Field(min_length=1, max_length=500)
    answer: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=2000)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value


class ReviewInput(StrictInput):
    application_id: int | None = Field(default=None, gt=0)
    schedule_id: int | None = Field(default=None, gt=0)
    occurred_on: date = Field(default_factory=date.today)
    # None = 保持已有题目不变；数组（含空数组）= 全量替换
    questions: list[QuestionInput] | None = Field(default=None, max_length=50)


def service(actor, session):
    return CareerService(session, actor)


@router.get("/briefing")
def briefing(day: date = Query(default_factory=date.today),
             actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return service(actor, session).briefing(day)


@router.get("/weekly")
def weekly(start: date | None = None, actor: Actor = Depends(get_actor),
           session: Session = Depends(get_session)):
    start = start or (date.today() - timedelta(days=date.today().weekday()))
    return service(actor, session).weekly(start)


@router.get("/tasks")
def list_tasks(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return service(actor, session).tasks()


@router.post("/tasks", status_code=201)
def create_task(body: TaskInput, actor: Actor = Depends(get_actor),
                session: Session = Depends(get_session)):
    return service(actor, session).create_task(body)


@router.put("/tasks/{task_id}")
def update_task(task_id: int, body: TaskInput, actor: Actor = Depends(get_actor),
                session: Session = Depends(get_session)):
    return service(actor, session).update_task(task_id, body)


@router.patch("/tasks/{task_id}/done")
def set_task_done(task_id: int, body: TaskDone, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    return service(actor, session).set_task_done(task_id, body.done)


@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, actor: Actor = Depends(get_actor),
                session: Session = Depends(get_session)):
    service(actor, session).delete_task(task_id)
    return {"ok": True}


@router.get("/reviews")
def list_reviews(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    svc = service(actor, session)
    return [svc.review_payload(row) for row in svc.reviews()]


@router.post("/reviews", status_code=201)
def create_review(body: ReviewInput, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    svc = service(actor, session)
    return svc.review_payload(svc.create_review(body))


@router.put("/reviews/{review_id}")
def update_review(review_id: int, body: ReviewInput, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    svc = service(actor, session)
    return svc.review_payload(svc.update_review(review_id, body))


@router.delete("/reviews/{review_id}")
def delete_review(review_id: int, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    service(actor, session).delete_review(review_id)
    return {"ok": True}


@router.get("/interviews/{schedule_id}/context")
def interview_context(schedule_id: int, actor: Actor = Depends(get_actor),
                      session: Session = Depends(get_session)):
    return service(actor, session).interview_context(schedule_id)


@router.get("/applications/{application_id}/followup-context")
def followup_context(application_id: int, actor: Actor = Depends(get_actor),
                     session: Session = Depends(get_session)):
    return service(actor, session).followup_context(application_id)
