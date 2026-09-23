"""User-owned career documents, memory and evidence-backed matching."""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import Session

from app.core.actor import Actor
from app.db.session import get_session
from app.deps import get_actor
from app.services.document_import import MAX_UPLOAD_BYTES, extract
from app.services.profile import ProfileService

router = APIRouter(prefix="/api/profile", tags=["profile"])


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocumentInput(StrictInput):
    kind: Literal["resume", "jd", "project"]
    title: str = Field(min_length=1, max_length=128)
    content: str = Field(min_length=1)
    source_name: str = Field(default="", max_length=128)

    @field_validator("title", "content")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("内容不能为空")
        return value


class MemoryInput(StrictInput):
    category: Literal["goal", "skill", "preference", "experience"]
    content: str = Field(min_length=1, max_length=1000)
    source_version_id: int | None = Field(default=None, gt=0)
    valid_until: date | None = None

    @field_validator("content")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("内容不能为空")
        return value


class MatchInput(StrictInput):
    resume_document_id: int = Field(gt=0)
    jd_document_id: int = Field(gt=0)


class DuplicateResumeInput(StrictInput):
    title: str = Field(min_length=1, max_length=128)
    version: int | None = Field(default=None, gt=0)

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("标题不能为空")
        return value


def service(actor, session):
    return ProfileService(session, actor)


def version_view(row, *, content=False):
    result = {
        "id": row.id, "document_id": row.document_id, "version": row.version,
        "source_name": row.source_name, "content_sha256": row.content_sha256,
        "created_at": row.created_at,
    }
    if content:
        result["content"] = row.content
    return result


@router.get("/documents")
def list_documents(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return service(actor, session).list_documents()


@router.post("/documents", status_code=201)
def create_document(body: DocumentInput, actor: Actor = Depends(get_actor),
                    session: Session = Depends(get_session)):
    return service(actor, session).create_document(body)


@router.post("/documents/import", status_code=201)
async def import_document(
    kind: Literal["resume", "jd", "project"] = Form(), title: str = Form(),
    file: UploadFile = File(), actor: Actor = Depends(get_actor),
    session: Session = Depends(get_session),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    name, content = extract(file.filename or "", data)
    return service(actor, session).create_document(DocumentInput(
        kind=kind, title=title, content=content, source_name=name,
    ))


@router.get("/documents/search")
def search_documents(
    q: str = Query(min_length=2, max_length=200),
    kind: Literal["resume", "jd", "project"] | None = None,
    limit: int = Query(default=8, ge=1, le=20),
    actor: Actor = Depends(get_actor), session: Session = Depends(get_session),
):
    return {"items": service(actor, session).search(q, kind, limit)}


@router.get("/documents/{document_id}")
def get_document(document_id: int, actor: Actor = Depends(get_actor),
                 session: Session = Depends(get_session)):
    svc = service(actor, session)
    document = svc.document(document_id)
    return {"document": document, "version": version_view(svc.version(document_id), content=True)}


@router.patch("/documents/{document_id}/default")
def set_default_resume(document_id: int, actor: Actor = Depends(get_actor),
                       session: Session = Depends(get_session)):
    return service(actor, session).set_default_resume(document_id)


@router.post("/documents/{document_id}/duplicate", status_code=201)
def duplicate_resume(document_id: int, body: DuplicateResumeInput,
                     actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return service(actor, session).duplicate_resume(document_id, body.title.strip(), body.version)


@router.get("/documents/{document_id}/profile-suggestions")
def profile_suggestions(document_id: int, actor: Actor = Depends(get_actor),
                        session: Session = Depends(get_session)):
    return service(actor, session).profile_suggestions(document_id)


@router.get("/documents/{document_id}/versions")
def list_versions(document_id: int, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    return [version_view(row) for row in service(actor, session).list_versions(document_id)]


@router.get("/documents/{document_id}/versions/{number}")
def get_version(document_id: int, number: int, actor: Actor = Depends(get_actor),
                session: Session = Depends(get_session)):
    return version_view(service(actor, session).version(document_id, number), content=True)


@router.post("/documents/{document_id}/versions", status_code=201)
def revise_document(document_id: int, body: DocumentInput,
                    actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    return service(actor, session).revise_document(document_id, body)


@router.post("/documents/{document_id}/import", status_code=201)
async def import_version(
    document_id: int, kind: Literal["resume", "jd", "project"] = Form(),
    title: str = Form(), file: UploadFile = File(),
    actor: Actor = Depends(get_actor), session: Session = Depends(get_session),
):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    name, content = extract(file.filename or "", data)
    return service(actor, session).revise_document(document_id, DocumentInput(
        kind=kind, title=title, content=content, source_name=name,
    ))


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, actor: Actor = Depends(get_actor),
                    session: Session = Depends(get_session)):
    service(actor, session).delete_document(document_id)
    return {"ok": True}


@router.get("/memories")
def list_memories(actor: Actor = Depends(get_actor), session: Session = Depends(get_session)):
    svc = service(actor, session)
    active = {row.id for row in svc.active_memories()}
    return [{**row.model_dump(), "active": row.id in active} for row in svc.list_memories()]


@router.post("/memories", status_code=201)
def create_memory(body: MemoryInput, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    return service(actor, session).create_memory(body)


@router.put("/memories/{memory_id}")
def update_memory(memory_id: int, body: MemoryInput, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    return service(actor, session).update_memory(memory_id, body)


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: int, actor: Actor = Depends(get_actor),
                  session: Session = Depends(get_session)):
    service(actor, session).delete_memory(memory_id)
    return {"ok": True}


@router.post("/match")
def match_documents(body: MatchInput, actor: Actor = Depends(get_actor),
                    session: Session = Depends(get_session)):
    return service(actor, session).match(body.resume_document_id, body.jd_document_id)
