from app.core.actor import Actor
from datetime import datetime
from sqlalchemy import update
from app.core.errors import BusinessError
from app.db.session import transaction
from app.models import Application, ApplicationStage, RecruitmentJob
from app.repositories.catalog import ApplicationRepository, CompanyRepository
from app.services.common import STAGES, apply_fields, require


class ApplicationService:
    def __init__(self, session, actor: Actor):
        self.session = session
        self.actor = actor
        self.repository = ApplicationRepository(session, actor)

    def list(self):
        return self.repository.list()

    def search(self, keyword=None, stage=None, limit=20):
        if stage is not None:
            self.validate_stage(stage)
        if not 1 <= limit <= 50:
            raise BusinessError("查询上限必须为1～50")
        return self.repository.search(keyword, stage, limit)

    def get(self, application_id):
        return require(self.repository.get(application_id), "投递记录不存在")

    def validate(self, body):
        if body.current_stage not in STAGES:
            raise BusinessError("无效的投递阶段")
        if body.company_id is not None:
            require(CompanyRepository(self.session, self.actor).get(body.company_id), "公司不存在")

    def create(self, body):
        self.validate(body)
        with transaction(self.session):
            entity = self.repository.add(
                Application(**body.model_dump(), user_id=self.actor.user_id)
            )
            self.session.add(
                ApplicationStage(
                    user_id=self.actor.user_id, application_id=entity.id, stage=entity.current_stage
                )
            )
        self.session.refresh(entity)
        return entity

    def update(self, application_id, body):
        entity = self.get(application_id)
        self.validate(body)
        if body.current_stage != entity.current_stage:
            raise BusinessError("请使用阶段流转接口修改阶段（会记录阶段历史）")
        with transaction(self.session):
            apply_fields(entity, body.model_dump())
            entity.updated_at = datetime.now()
            self.repository.add(entity)
        self.session.refresh(entity)
        return entity

    def change_stage(self, application_id, stage):
        entity = self.get(application_id)
        if stage not in STAGES:
            raise BusinessError("无效的投递阶段")
        if stage == entity.current_stage:
            return entity
        with transaction(self.session):
            entity.current_stage = stage
            entity.updated_at = datetime.now()
            self.repository.add(entity)
            self.session.add(
                ApplicationStage(user_id=self.actor.user_id, application_id=entity.id, stage=stage)
            )
        self.session.refresh(entity)
        return entity

    def history(self, application_id):
        self.get(application_id)
        return self.repository.history(application_id)

    def change_stage_in_transaction(self, application_id, stage, expected_stage, expected_updated_at):
        """Agent 复合用例专用：调用者拥有事务，将业务写入与审计原子提交。

        不调用既有会 commit 的 change_stage；用条件更新防止审批期间覆盖新数据。
        """
        self.validate_stage(stage)
        entity = self.get(application_id)
        if entity.current_stage != expected_stage or entity.updated_at != expected_updated_at:
            raise BusinessError("审批目标已变化，请重新发起", 409)
        if stage == entity.current_stage:
            return {"application_id": entity.id, "stage": stage, "changed": False}
        result = self.session.execute(
            update(Application).where(
                Application.id == application_id, Application.user_id == self.actor.user_id,
                Application.current_stage == expected_stage,
                Application.updated_at == expected_updated_at,
            ).values(current_stage=stage, updated_at=datetime.now())
            .execution_options(synchronize_session=False)
        )
        if result.rowcount != 1:
            raise BusinessError("审批目标已变化，请重新发起", 409)
        self.session.add(ApplicationStage(
            user_id=self.actor.user_id, application_id=application_id, stage=stage,
        ))
        self.session.flush()
        return {"application_id": application_id, "stage": stage, "changed": True}

    @staticmethod
    def validate_stage(stage):
        if stage not in STAGES:
            raise BusinessError("无效的投递阶段")

    def delete(self, application_id):
        with transaction(self.session):
            self.session.execute(update(RecruitmentJob).where(
                RecruitmentJob.user_id == self.actor.user_id,
                RecruitmentJob.application_id == application_id,
            ).values(application_id=None))
            self.repository.delete(self.get(application_id))
