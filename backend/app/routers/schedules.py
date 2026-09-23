from app.core.actor import Actor
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.session import get_session
from app.deps import get_actor
from app.models import Schedule
from app.schemas import ScheduleIn
from app.services.schedules import ScheduleService

router = APIRouter(
    prefix="/api/schedules",
    tags=["schedules"],
)


@router.get("", response_model=list[Schedule])
def list_schedules(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return ScheduleService(session, actor).list()


@router.post("", response_model=Schedule)
def create_schedule(
    body: ScheduleIn, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    return ScheduleService(session, actor).save(body)


@router.put("/{schedule_id}", response_model=Schedule)
def update_schedule(
    schedule_id: int,
    body: ScheduleIn,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
):
    return ScheduleService(session, actor).save(body, schedule_id)


@router.delete("/{schedule_id}")
def delete_schedule(
    schedule_id: int, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    ScheduleService(session, actor).delete(schedule_id)
    return {"ok": True}
