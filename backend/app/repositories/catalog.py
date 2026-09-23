from sqlalchemy import func
from sqlmodel import select
from app.core.actor import Actor
from app.core.errors import BusinessError
from app.models import Application, ApplicationStage, Company, Schedule, User


class Repository:
    def __init__(self, session, model):
        self.session, self.model = session, model

    def get(self, entity_id):
        return self.session.get(self.model, entity_id)

    def add(self, entity):
        self.session.add(entity)
        self.session.flush()
        return entity

    def delete(self, entity):
        self.session.delete(entity)


class OwnedRepository(Repository):
    def __init__(self, session, model, actor: Actor):
        if not isinstance(actor, Actor):
            raise TypeError("必须显式传递已认证 Actor")
        user = session.exec(select(User).where(User.id == actor.user_id)).first()
        if user is None or not user.is_active:
            raise BusinessError("账号不可用", 401)
        super().__init__(session, model)
        self.actor = actor

    def query(self):
        return select(self.model).where(self.model.user_id == self.actor.user_id)

    def get(self, entity_id):
        return self.session.exec(self.query().where(self.model.id == entity_id)).first()

    def add(self, entity):
        if entity.user_id != self.actor.user_id:
            raise ValueError("不能持久化其他用户的数据")
        return super().add(entity)

    def delete(self, entity):
        if entity.user_id != self.actor.user_id:
            raise ValueError("不能删除其他用户的数据")
        super().delete(entity)


class ApplicationRepository(OwnedRepository):
    def __init__(self, session, actor: Actor):
        super().__init__(session, Application, actor)

    def list(self):
        return self.session.exec(
            self.query().order_by(Application.apply_date.desc(), Application.id.desc())
        ).all()

    def history(self, application_id):
        return self.session.exec(
            select(ApplicationStage)
            .where(
                ApplicationStage.user_id == self.actor.user_id,
                ApplicationStage.application_id == application_id,
            )
            .order_by(ApplicationStage.changed_at, ApplicationStage.id)
        ).all()

    def search(self, keyword, stage, limit):
        query = self.query()
        if keyword:
            query = query.where(
                func.lower(Application.company_name + " " + Application.position)
                .contains(keyword.lower(), autoescape=True)
            )
        if stage:
            query = query.where(Application.current_stage == stage)
        total = self.session.exec(select(func.count()).select_from(query.subquery())).one()
        rows = self.session.exec(query.order_by(Application.apply_date.desc(), Application.id.desc())
                                 .limit(limit)).all()
        return total, rows


class CompanyRepository(OwnedRepository):
    def __init__(self, session, actor: Actor):
        super().__init__(session, Company, actor)

    def list(self):
        return self.session.exec(self.query().order_by(Company.name)).all()

    def by_name(self, name):
        return self.session.exec(self.query().where(Company.name == name)).first()


class ScheduleRepository(OwnedRepository):
    def __init__(self, session, actor: Actor):
        super().__init__(session, Schedule, actor)

    def list(self):
        return self.session.exec(
            self.query().order_by(Schedule.sched_date, Schedule.sched_time)
        ).all()

    def upcoming(self, start, end, limit):
        query = self.query().where(Schedule.done.is_(False), Schedule.sched_date >= start,
                                   Schedule.sched_date <= end)
        total = self.session.exec(select(func.count()).select_from(query.subquery())).one()
        return total, self.session.exec(query.order_by(Schedule.sched_date, Schedule.sched_time)
                                       .limit(limit)).all()


class UserRepository(Repository):
    def __init__(self, session):
        super().__init__(session, User)

    def first(self):
        return self.session.exec(select(User).order_by(User.id)).first()

    def by_name(self, name):
        return self.session.exec(
            select(User).where(func.lower(User.username) == name.lower())
        ).first()
