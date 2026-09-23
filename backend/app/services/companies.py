from app.core.actor import Actor
from sqlalchemy.exc import IntegrityError
from app.core.errors import BusinessError
from app.db.session import transaction
from app.models import Company
from app.repositories.catalog import CompanyRepository
from app.services.common import apply_fields, require


class CompanyService:
    def __init__(self, session, actor: Actor):
        self.session = session
        self.actor = actor
        self.repository = CompanyRepository(session, actor)

    def list(self):
        return self.repository.list()

    def save(self, body, company_id=None):
        entity = (
            require(self.repository.get(company_id), "公司不存在")
            if company_id is not None
            else Company(user_id=self.actor.user_id)
        )
        existing = self.repository.by_name(body.name)
        if existing is not None and existing.id != entity.id:
            raise BusinessError("该公司已存在")
        try:
            with transaction(self.session):
                apply_fields(entity, body.model_dump())
                self.repository.add(entity)
        except IntegrityError as error:
            raise BusinessError("该公司已存在") from error
        self.session.refresh(entity)
        return entity

    def delete(self, company_id):
        with transaction(self.session):
            entity = require(self.repository.get(company_id), "公司不存在")
            for application in list(entity.applications):
                application.company = None
                application.company_id = None
                self.session.add(application)
            self.session.flush()
            self.repository.delete(entity)
