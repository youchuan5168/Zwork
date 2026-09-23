"""用户级偏好设置接口（当前：大模型 API 配置）。"""

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session

from app.core.actor import Actor
from app.db.session import get_session
from app.deps import get_actor
from app.schemas import LlmConfigIn, LlmConfigOut
from app.services.llm_settings import LlmSettingsService

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/llm", response_model=LlmConfigOut)
def get_llm(request: Request, actor: Actor = Depends(get_actor),
            session: Session = Depends(get_session)):
    return LlmSettingsService(session, actor, request.app.state.settings).get()


@router.put("/llm", response_model=LlmConfigOut)
def save_llm(body: LlmConfigIn, request: Request, actor: Actor = Depends(get_actor),
             session: Session = Depends(get_session)):
    return LlmSettingsService(session, actor, request.app.state.settings).save(body)


@router.delete("/llm")
def delete_llm(request: Request, actor: Actor = Depends(get_actor),
               session: Session = Depends(get_session)):
    return LlmSettingsService(session, actor, request.app.state.settings).delete()

