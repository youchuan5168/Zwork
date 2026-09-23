"""HTTP 适配层：鉴权、请求解析和响应；业务逻辑位于 Service。"""

from app.core.actor import Actor
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.session import get_session
from app.deps import get_actor
from app.models import Application, ApplicationStage
from app.schemas import ApplicationIn, StageIn
from app.services.applications import ApplicationService

router = APIRouter(
    prefix="/api/applications",
    tags=["applications"],
)


@router.get("", response_model=list[Application])
def list_applications(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return ApplicationService(session, actor).list()


@router.post("", response_model=Application)
def create_application(
    body: ApplicationIn, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    return ApplicationService(session, actor).create(body)


@router.put("/{app_id}", response_model=Application)
def update_application(
    app_id: int,
    body: ApplicationIn,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
):
    return ApplicationService(session, actor).update(app_id, body)


@router.patch("/{app_id}/stage", response_model=Application)
def change_stage(
    app_id: int,
    body: StageIn,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
):
    return ApplicationService(session, actor).change_stage(app_id, body.stage)


@router.get("/{app_id}/stages", response_model=list[ApplicationStage])
def stage_history(
    app_id: int, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    return ApplicationService(session, actor).history(app_id)


@router.delete("/{app_id}")
def delete_application(
    app_id: int, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    ApplicationService(session, actor).delete(app_id)
    return {"ok": True}
