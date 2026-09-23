from app.core.actor import Actor
from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.db.session import get_session
from app.deps import get_actor
from app.models import Company
from app.schemas import CompanyIn
from app.services.companies import CompanyService

router = APIRouter(
    prefix="/api/companies",
    tags=["companies"],
)


@router.get("", response_model=list[Company])
def list_companies(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return CompanyService(session, actor).list()


@router.post("", response_model=Company)
def create_company(
    body: CompanyIn, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    return CompanyService(session, actor).save(body)


@router.put("/{company_id}", response_model=Company)
def update_company(
    company_id: int,
    body: CompanyIn,
    actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
):
    return CompanyService(session, actor).save(body, company_id)


@router.delete("/{company_id}")
def delete_company(
    company_id: int, actor: Actor = Depends(get_actor), session: Session = Depends(get_session)
):
    CompanyService(session, actor).delete(company_id)
    return {"ok": True}
