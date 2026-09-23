from app.core.actor import Actor
from app.db.session import transaction
from app.models import Schedule
from app.repositories.catalog import ApplicationRepository, ScheduleRepository
from app.services.common import apply_fields, require
from app.core.errors import BusinessError


class ScheduleService:
    def __init__(self, session, actor: Actor):
        self.session = session
        self.actor = actor
        self.repository = ScheduleRepository(session, actor)

    def list(self):
        return self.repository.list()

    def upcoming(self, start, end, limit=20):
        if not 0 <= (end - start).days <= 90 or not 1 <= limit <= 50:
            raise BusinessError("查询范围无效")
        return self.repository.upcoming(start, end, limit)

    def save(self, body, schedule_id=None):
        entity = (
            require(self.repository.get(schedule_id), "安排不存在")
            if schedule_id is not None
            else Schedule(user_id=self.actor.user_id)
        )
        if body.application_id is not None:
            require(
                ApplicationRepository(self.session, self.actor).get(body.application_id),
                "投递记录不存在",
            )
        with transaction(self.session):
            apply_fields(entity, body.model_dump())
            self.repository.add(entity)
        self.session.refresh(entity)
        return entity

    def delete(self, schedule_id):
        with transaction(self.session):
            self.repository.delete(require(self.repository.get(schedule_id), "安排不存在"))
