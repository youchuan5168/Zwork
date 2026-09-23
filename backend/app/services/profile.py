"""Versioned user documents, explicit memory, and source-linked lexical retrieval."""

import hashlib
import re
from datetime import date, datetime
from types import SimpleNamespace

from sqlalchemy import delete, update
from sqlmodel import select

from app.core.errors import BusinessError
from app.db.session import transaction
from app.models import (
    CareerDocument, CareerDocumentChunk, CareerDocumentVersion, CareerMemory,
)

MAX_DOCUMENT_BYTES = 200_000
MAX_DOCUMENTS = 100
MAX_VERSIONS = 20
MAX_MEMORIES = 200


def tokens(value):
    result = set()
    for word in re.findall(r"[a-z0-9][a-z0-9+#.]*|[\u4e00-\u9fff]+", value.casefold()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", word):
            result.update(word[index:index + 2] for index in range(len(word) - 1))
        elif len(word) >= 2:
            result.add(word)
    return result


def chunks(content):
    return [content[start:start + 700] for start in range(0, len(content), 600)]


def score(query_tokens, content):
    common = query_tokens & tokens(content)
    return len(common) / len(query_tokens) if query_tokens else 0.0


class ProfileService:
    def __init__(self, session, actor):
        self.session = session
        self.user_id = actor.user_id

    def document(self, document_id):
        row = self.session.exec(select(CareerDocument).where(
            CareerDocument.id == document_id, CareerDocument.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("文档不存在", 404)
        return row

    def version(self, document_id, number=None):
        document = self.document(document_id)
        number = number or document.current_version
        row = self.session.exec(select(CareerDocumentVersion).where(
            CareerDocumentVersion.document_id == document.id,
            CareerDocumentVersion.user_id == self.user_id,
            CareerDocumentVersion.version == number,
        )).first()
        if row is None:
            raise BusinessError("文档版本不存在", 404)
        return row

    def list_documents(self):
        return self.session.exec(select(CareerDocument).where(
            CareerDocument.user_id == self.user_id,
        ).order_by(CareerDocument.updated_at.desc(), CareerDocument.id.desc())).all()

    def list_versions(self, document_id):
        self.document(document_id)
        return self.session.exec(select(CareerDocumentVersion).where(
            CareerDocumentVersion.document_id == document_id,
            CareerDocumentVersion.user_id == self.user_id,
        ).order_by(CareerDocumentVersion.version.desc())).all()

    def _content(self, content):
        value = content.strip()
        if not value or len(value.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise BusinessError("文档内容需为 1～200000 字节的文本", 400)
        return value

    def _add_version(self, document, content, source_name):
        row = CareerDocumentVersion(
            document_id=document.id, user_id=self.user_id,
            version=document.current_version, content=content,
            source_name=source_name.strip(),
            content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            created_at=datetime.now(),
        )
        self.session.add(row)
        self.session.flush()
        self.session.add_all(CareerDocumentChunk(
            version_id=row.id, user_id=self.user_id, ordinal=index, content=part,
        ) for index, part in enumerate(chunks(content)))
        return row

    def create_document(self, body):
        content = self._content(body.content)
        if len(self.list_documents()) >= MAX_DOCUMENTS:
            raise BusinessError("文档数量已达上限", 400)
        with transaction(self.session):
            make_default = body.kind == "resume" and not self.session.exec(select(CareerDocument).where(
                CareerDocument.user_id == self.user_id,
                CareerDocument.kind == "resume",
            )).first()
            document = CareerDocument(
                user_id=self.user_id, kind=body.kind, title=body.title.strip(),
                current_version=1, is_default=make_default,
            )
            self.session.add(document)
            self.session.flush()
            self._add_version(document, content, body.source_name)
        self.session.refresh(document)
        return document

    def set_default_resume(self, document_id):
        document = self.document(document_id)
        if document.kind != "resume":
            raise BusinessError("只能将简历设为默认", 400)
        with transaction(self.session):
            self.session.execute(update(CareerDocument).where(
                CareerDocument.user_id == self.user_id,
                CareerDocument.kind == "resume",
            ).values(is_default=False).execution_options(synchronize_session=False))
            self.session.execute(update(CareerDocument).where(
                CareerDocument.id == document.id,
                CareerDocument.user_id == self.user_id,
            ).values(is_default=True).execution_options(synchronize_session=False))
        self.session.expire_all()
        return self.document(document_id)

    def duplicate_resume(self, document_id, title, version=None):
        source = self.document(document_id)
        if source.kind != "resume":
            raise BusinessError("只能从简历创建定制版本", 400)
        source_version = self.version(document_id, version)
        return self.create_document(SimpleNamespace(
            kind="resume", title=title, content=source_version.content,
            source_name=f"基于《{source.title}》第 {source_version.version} 版",
        ))

    def profile_suggestions(self, document_id):
        document = self.document(document_id)
        if document.kind != "resume":
            raise BusinessError("请选择一份简历", 400)
        version = self.version(document_id)
        lines = [re.sub(r"\s+", " ", line).strip(" -•\t")
                 for line in version.content.splitlines()]
        lines = [line for line in lines if 4 <= len(line) <= 220]
        suggestions = []

        def add(category, content):
            content = content.strip()
            if content and not any(row["content"] == content for row in suggestions):
                suggestions.append({"category": category, "content": content,
                                    "source_version_id": version.id})

        for line in lines:
            lowered = line.casefold()
            if any(key in line for key in ("求职意向", "目标岗位", "期望岗位", "职业目标")):
                add("goal", line)
            elif any(key in line for key in ("期望城市", "期望薪资", "工作地点", "工作方式")):
                add("preference", line)
            elif any(key in lowered for key in (
                "技能", "python", "java", "javascript", "vue", "react", "sql", "产品", "数据分析",
            )):
                add("skill", line)
            elif any(key in line for key in ("项目", "负责", "主导", "实现", "优化", "提升", "降低")):
                add("experience", line)
            if len(suggestions) >= 12:
                break
        if not suggestions and lines:
            add("experience", lines[0])
        return {"document_id": document.id, "version": version.version,
                "suggestions": suggestions[:12]}

    def revise_document(self, document_id, body):
        document = self.document(document_id)
        if document.kind != body.kind:
            raise BusinessError("文档类型不能改变", 400)
        if document.current_version >= MAX_VERSIONS:
            raise BusinessError("文档版本已达上限", 400)
        content = self._content(body.content)
        if hashlib.sha256(content.encode("utf-8")).hexdigest() == self.version(document_id).content_sha256:
            raise BusinessError("文档内容未变化", 409)
        prior = document.current_version
        with transaction(self.session):
            result = self.session.execute(update(CareerDocument).where(
                CareerDocument.id == document_id,
                CareerDocument.user_id == self.user_id,
                CareerDocument.current_version == prior,
            ).values(current_version=prior + 1, title=body.title.strip(), updated_at=datetime.now())
            .execution_options(synchronize_session=False))
            if result.rowcount != 1:
                raise BusinessError("文档已被修改，请刷新后重试", 409)
            self.session.expire(document)
            self._add_version(document, content, body.source_name)
        self.session.refresh(document)
        return document

    def delete_document(self, document_id):
        document = self.document(document_id)
        version_ids = [row.id for row in self.list_versions(document_id)]
        with transaction(self.session):
            self.session.execute(delete(CareerMemory).where(
                CareerMemory.user_id == self.user_id,
                CareerMemory.source_version_id.in_(version_ids),
            ))
            self.session.execute(delete(CareerDocumentChunk).where(
                CareerDocumentChunk.user_id == self.user_id,
                CareerDocumentChunk.version_id.in_(version_ids),
            ))
            self.session.execute(delete(CareerDocumentVersion).where(
                CareerDocumentVersion.user_id == self.user_id,
                CareerDocumentVersion.document_id == document_id,
            ))
            self.session.delete(document)

    def list_memories(self):
        return self.session.exec(select(CareerMemory).where(
            CareerMemory.user_id == self.user_id,
        ).order_by(CareerMemory.updated_at.desc(), CareerMemory.id.desc())).all()

    def memory(self, memory_id):
        row = self.session.exec(select(CareerMemory).where(
            CareerMemory.id == memory_id, CareerMemory.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("记忆不存在", 404)
        return row

    def _memory_source(self, source_version_id):
        if source_version_id is None:
            return
        row = self.session.exec(select(CareerDocumentVersion).where(
            CareerDocumentVersion.id == source_version_id,
            CareerDocumentVersion.user_id == self.user_id,
        )).first()
        if row is None:
            raise BusinessError("来源文档版本不存在", 404)

    def create_memory(self, body):
        if len(self.list_memories()) >= MAX_MEMORIES:
            raise BusinessError("记忆数量已达上限", 400)
        self._memory_source(body.source_version_id)
        with transaction(self.session):
            row = CareerMemory(**body.model_dump(), user_id=self.user_id)
            row.content = row.content.strip()
            self.session.add(row)
        self.session.refresh(row)
        return row

    def update_memory(self, memory_id, body):
        row = self.memory(memory_id)
        self._memory_source(body.source_version_id)
        with transaction(self.session):
            row.category = body.category
            row.content = body.content.strip()
            row.source_version_id = body.source_version_id
            row.valid_until = body.valid_until
            row.updated_at = datetime.now()
            self.session.add(row)
        self.session.refresh(row)
        return row

    def delete_memory(self, memory_id):
        with transaction(self.session):
            self.session.delete(self.memory(memory_id))

    def search(self, query, kind=None, limit=8):
        query_tokens = tokens(query)
        if not query_tokens:
            raise BusinessError("请输入可检索的关键词", 400)
        statement = select(CareerDocumentChunk, CareerDocumentVersion, CareerDocument).join(
            CareerDocumentVersion,
            (CareerDocumentChunk.version_id == CareerDocumentVersion.id)
            & (CareerDocumentChunk.user_id == CareerDocumentVersion.user_id),
        ).join(
            CareerDocument,
            (CareerDocumentVersion.document_id == CareerDocument.id)
            & (CareerDocumentVersion.user_id == CareerDocument.user_id),
        ).where(
            CareerDocument.user_id == self.user_id,
            CareerDocumentVersion.user_id == self.user_id,
            CareerDocumentChunk.user_id == self.user_id,
            CareerDocumentVersion.version == CareerDocument.current_version,
        )
        if kind is not None:
            statement = statement.where(CareerDocument.kind == kind)
        ranked = []
        for chunk, version, document in self.session.exec(statement):
            relevance = score(query_tokens, chunk.content)
            if relevance:
                ranked.append({
                    "document_id": document.id, "title": document.title, "kind": document.kind,
                    "version": version.version, "version_id": version.id,
                    "chunk": chunk.ordinal, "excerpt": chunk.content[:700],
                    "score": round(relevance, 3),
                })
        ranked.sort(key=lambda item: (-item["score"], item["document_id"], item["chunk"]))
        return ranked[:limit]

    def match(self, resume_id, jd_id):
        resume = self.document(resume_id)
        jd = self.document(jd_id)
        if resume.kind != "resume" or jd.kind != "jd":
            raise BusinessError("请选择一份简历和一份 JD", 400)
        resume_version = self.version(resume_id)
        jd_version = self.version(jd_id)
        resume_chunks = self.session.exec(select(CareerDocumentChunk).where(
            CareerDocumentChunk.version_id == resume_version.id,
            CareerDocumentChunk.user_id == self.user_id,
        ).order_by(CareerDocumentChunk.ordinal)).all()
        requirements = [part.strip() for part in re.split(r"[\n。；;]+", jd_version.content)
                        if len(part.strip()) >= 6]
        if not requirements:
            requirements = [jd_version.content[:200]]
        matched, gaps = [], []
        for requirement in requirements[:30]:
            needle = tokens(requirement)
            scored = sorted(
                ((score(needle, chunk.content), chunk) for chunk in resume_chunks),
                key=lambda pair: pair[0], reverse=True,
            )
            best_score, best_chunk = scored[0]
            item = {"requirement": requirement[:240], "jd_version_id": jd_version.id,
                    "jd_version": jd_version.version, "score": round(best_score, 3)}
            if best_score >= 0.35 and len(needle & tokens(best_chunk.content)) >= 2:
                item.update({"resume_version_id": resume_version.id,
                             "resume_version": resume_version.version,
                             "resume_chunk": best_chunk.ordinal,
                             "evidence": best_chunk.content[:350]})
                matched.append(item)
            else:
                gaps.append(item)
        return {
            "resume_document_id": resume.id, "jd_document_id": jd.id,
            "resume_version": resume_version.version, "jd_version": jd_version.version,
            "method": "lexical-v1", "matched": matched, "gaps": gaps,
            "evaluated_requirements": len(matched) + len(gaps),
            "truncated": len(requirements) > 30,
        }

    def active_memories(self):
        today = date.today()
        current_sources = set(self.session.exec(select(CareerDocumentVersion.id).join(
            CareerDocument,
            (CareerDocumentVersion.document_id == CareerDocument.id)
            & (CareerDocumentVersion.user_id == CareerDocument.user_id),
        ).where(
            CareerDocument.user_id == self.user_id,
            CareerDocumentVersion.version == CareerDocument.current_version,
        )).all())
        return [row for row in self.list_memories()
                if (row.valid_until is None or row.valid_until >= today)
                and (row.source_version_id is None or row.source_version_id in current_sources)]
