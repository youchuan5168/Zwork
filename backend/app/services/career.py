"""Career workbench facts and user-owned actions; model suggestions never write here."""

from datetime import datetime, timedelta

from sqlalchemy.orm import selectinload
from sqlmodel import select

from app.core.errors import BusinessError
from app.db.session import transaction
from app.models import (
    Application, ApplicationStage, CareerReview, CareerTask, InterviewQuestion, Schedule,
)
from app.services.profile import ProfileService, tokens

ACTIVE_STAGES = {"not_started", "applied", "screening", "written_test", "interview"}
MAX_TASKS = 500
MAX_REVIEWS = 300
MAX_QUESTIONS_PER_REVIEW = 50


class CareerService:
    def __init__(self, session, actor):
        self.session = session
        self.actor = actor
        self.user_id = actor.user_id

    def application(self, application_id):
        row = self.session.exec(select(Application).where(
            Application.id == application_id, Application.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("投递记录不存在", 404)
        return row

    def schedule(self, schedule_id):
        row = self.session.exec(select(Schedule).where(
            Schedule.id == schedule_id, Schedule.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("日程不存在", 404)
        return row

    def tasks(self):
        return self.session.exec(select(CareerTask).where(
            CareerTask.user_id == self.user_id,
        ).order_by(CareerTask.done, CareerTask.due_date, CareerTask.id.desc())).all()

    def task(self, task_id):
        row = self.session.exec(select(CareerTask).where(
            CareerTask.id == task_id, CareerTask.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("待办不存在", 404)
        return row

    def task_source(self, application_id):
        if application_id is None:
            return ""
        app = self.application(application_id)
        return f"{app.company_name} · {app.position}"[:256]

    def create_task(self, body):
        if len(self.tasks()) >= MAX_TASKS:
            raise BusinessError("待办数量已达上限", 400)
        label = self.task_source(body.application_id)
        data = body.model_dump()
        data.update(title=body.title.strip(), details=body.details.strip())
        with transaction(self.session):
            row = CareerTask(**data, user_id=self.user_id, source_label=label)
            self.session.add(row)
        self.session.refresh(row)
        return row

    def update_task(self, task_id, body):
        row = self.task(task_id)
        label = self.task_source(body.application_id)
        with transaction(self.session):
            row.title = body.title.strip()
            row.details = body.details.strip()
            row.due_date = body.due_date
            row.application_id = body.application_id
            row.source_label = label
            row.updated_at = datetime.now()
            self.session.add(row)
        self.session.refresh(row)
        return row

    def set_task_done(self, task_id, done):
        row = self.task(task_id)
        with transaction(self.session):
            if row.done != done:
                row.done = done
                row.completed_at = datetime.now() if done else None
                row.updated_at = datetime.now()
                self.session.add(row)
        self.session.refresh(row)
        return row

    def delete_task(self, task_id):
        with transaction(self.session):
            self.session.delete(self.task(task_id))

    def reviews(self):
        return self.session.exec(select(CareerReview).options(
            selectinload(CareerReview.questions),
        ).where(
            CareerReview.user_id == self.user_id,
        ).order_by(CareerReview.occurred_on.desc(), CareerReview.id.desc())).all()

    def review_payload(self, row):
        """ORM 行不会被 FastAPI 自动带出 relationship，显式序列化嵌套题目。"""
        data = row.model_dump()
        data["questions"] = [question.model_dump() for question in row.questions]
        return data

    def review(self, review_id):
        row = self.session.exec(select(CareerReview).where(
            CareerReview.id == review_id, CareerReview.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("复盘不存在", 404)
        return row

    def review_source(self, application_id, schedule_id):
        schedule = self.schedule(schedule_id) if schedule_id is not None else None
        if schedule and application_id is not None and schedule.application_id != application_id:
            raise BusinessError("日程与投递不匹配", 400)
        app_id = application_id if application_id is not None else (
            schedule.application_id if schedule else None
        )
        app = self.application(app_id) if app_id is not None else None
        label = " · ".join(part for part in (
            f"{app.company_name} {app.position}" if app else "", schedule.title if schedule else "",
        ) if part)
        return app_id, label[:256]

    def question_items(self, questions):
        items = [
            {"question": item.question.strip(), "answer": item.answer.strip(),
             "notes": item.notes.strip()}
            for item in (questions or [])
        ]
        if len(items) > MAX_QUESTIONS_PER_REVIEW:
            raise BusinessError("题目数量已达上限", 400)
        for item in items:
            if not item["question"]:
                raise BusinessError("问题不能为空", 400)
        return items

    def create_review(self, body):
        if len(self.reviews()) >= MAX_REVIEWS:
            raise BusinessError("复盘数量已达上限", 400)
        app_id, label = self.review_source(body.application_id, body.schedule_id)
        items = self.question_items(body.questions)
        data = body.model_dump(exclude={"questions"})
        data.update(application_id=app_id)
        with transaction(self.session):
            row = CareerReview(**data, user_id=self.user_id, source_label=label)
            row.questions = [
                InterviewQuestion(**item, user_id=self.user_id, application_id=app_id)
                for item in items
            ]
            self.session.add(row)
        self.session.refresh(row)
        return row

    def update_review(self, review_id, body):
        row = self.review(review_id)
        app_id, label = self.review_source(body.application_id, body.schedule_id)
        items = self.question_items(body.questions) if body.questions is not None else None
        with transaction(self.session):
            for key, value in body.model_dump(exclude={"questions"}).items():
                setattr(row, key, value.strip() if isinstance(value, str) else value)
            row.application_id = app_id
            row.source_label = label
            if items is not None:
                row.questions = [
                    InterviewQuestion(**item, user_id=self.user_id, application_id=app_id)
                    for item in items
                ]
            else:
                for child in row.questions:
                    child.application_id = app_id
            row.updated_at = datetime.now()
            self.session.add(row)
        self.session.refresh(row)
        return row

    def delete_review(self, review_id):
        with transaction(self.session):
            self.session.delete(self.review(review_id))

    def briefing(self, day):
        applications = self.session.exec(select(Application).where(
            Application.user_id == self.user_id,
        )).all()
        schedules = self.session.exec(select(Schedule).where(
            Schedule.user_id == self.user_id, Schedule.done.is_(False),
            Schedule.sched_date <= day + timedelta(days=7),
        ).order_by(Schedule.sched_date, Schedule.id)).all()
        tasks = [row for row in self.tasks() if not row.done and row.due_date is not None
                 and row.due_date <= day + timedelta(days=7)]
        stale = [row for row in applications if row.current_stage in ACTIVE_STAGES
                 and row.updated_at.date() <= day - timedelta(days=14)]
        return {
            "as_of": day.isoformat(), "window_end": (day + timedelta(days=7)).isoformat(),
            "application_count": len(applications),
            "recent_applications": [{"id": row.id, "company_name": row.company_name,
                                     "position": row.position, "apply_date": row.apply_date.isoformat()}
                                    for row in applications if day - timedelta(days=6) <= row.apply_date <= day],
            "stale_applications": [{"id": row.id, "company_name": row.company_name,
                                    "position": row.position, "stage": row.current_stage,
                                    "updated_at": row.updated_at.isoformat()}
                                   for row in sorted(stale, key=lambda item: item.updated_at)[:20]],
            "schedules": [{"id": row.id, "application_id": row.application_id,
                           "title": row.title, "date": row.sched_date.isoformat(),
                           "time": row.sched_time, "overdue": row.sched_date < day}
                          for row in schedules[:30]],
            "tasks": [{"id": row.id, "title": row.title, "due_date": row.due_date.isoformat(),
                       "application_id": row.application_id, "overdue": row.due_date < day}
                      for row in tasks[:30]],
        }

    def weekly(self, start):
        end = start + timedelta(days=6)
        applications = self.session.exec(select(Application).where(
            Application.user_id == self.user_id, Application.apply_date.between(start, end),
        ).order_by(Application.apply_date, Application.id)).all()
        stages = self.session.exec(select(ApplicationStage).where(
            ApplicationStage.user_id == self.user_id,
            ApplicationStage.changed_at >= datetime.combine(start, datetime.min.time()),
            ApplicationStage.changed_at < datetime.combine(end + timedelta(days=1), datetime.min.time()),
        ).order_by(ApplicationStage.changed_at)).all()
        schedules = self.session.exec(select(Schedule).where(
            Schedule.user_id == self.user_id, Schedule.sched_date.between(start, end),
        ).order_by(Schedule.sched_date)).all()
        reviews = [row for row in self.reviews() if start <= row.occurred_on <= end][:20]
        completed = [row for row in self.tasks() if row.completed_at
                     and start <= row.completed_at.date() <= end][:30]
        return {
            "start": start.isoformat(), "end": end.isoformat(),
            "applications": [{"id": row.id, "company_name": row.company_name,
                              "position": row.position, "apply_date": row.apply_date.isoformat()}
                             for row in applications[:30]],
            "stage_changes": [{"id": row.id, "application_id": row.application_id,
                               "stage": row.stage, "changed_at": row.changed_at.isoformat()}
                              for row in stages[:50]],
            "schedules": [{"id": row.id, "title": row.title, "date": row.sched_date.isoformat(),
                           "done": row.done} for row in schedules[:30]],
            "reviews": [{"id": row.id, "occurred_on": row.occurred_on.isoformat(),
                         "source_label": row.source_label,
                         "question_count": len(row.questions)} for row in reviews],
            "completed_tasks": [{"id": row.id, "title": row.title} for row in completed],
        }

    def followup_context(self, application_id):
        app = self.application(application_id)
        stages = self.session.exec(select(ApplicationStage).where(
            ApplicationStage.user_id == self.user_id,
            ApplicationStage.application_id == app.id,
        ).order_by(ApplicationStage.changed_at.desc()).limit(12)).all()
        schedules = self.session.exec(select(Schedule).where(
            Schedule.user_id == self.user_id, Schedule.application_id == app.id,
        ).order_by(Schedule.sched_date.desc()).limit(12)).all()
        return {
            "application": {"id": app.id, "company_name": app.company_name,
                            "position": app.position, "stage": app.current_stage,
                            "apply_date": app.apply_date.isoformat(),
                            "updated_at": app.updated_at.isoformat(), "notes": app.notes[:500]},
            "stage_history": [{"stage": row.stage, "date": row.changed_at.isoformat()}
                              for row in stages],
            "schedules": [{"id": row.id, "title": row.title,
                           "date": row.sched_date.isoformat(), "done": row.done}
                          for row in schedules],
        }

    def interview_context(self, schedule_id):
        schedule = self.schedule(schedule_id)
        app = self.application(schedule.application_id) if schedule.application_id else None
        query = f"{app.company_name} {app.position}" if app else schedule.title
        documents = ProfileService(self.session, self.actor).search(query, "jd", 3) if tokens(query) else []
        reviews = [row for row in self.reviews()
                   if app and row.application_id == app.id][:5]
        return {
            "schedule": {"id": schedule.id, "title": schedule.title,
                         "type": schedule.type, "date": schedule.sched_date.isoformat(),
                         "time": schedule.sched_time, "location": schedule.location,
                         "application_id": schedule.application_id},
            "application": ({"id": app.id, "company_name": app.company_name,
                             "position": app.position, "stage": app.current_stage,
                             "notes": app.notes[:500]} if app else None),
            "jd_evidence": documents,
            "prior_reviews": [{
                "id": row.id,
                "occurred_on": row.occurred_on.isoformat(),
                "questions": [{"question": question.question,
                               "answer": question.answer[:500],
                               "notes": question.notes[:500]}
                              for question in row.questions[:20]],
            } for row in reviews],
        }
