"""运行状态和事件的乐观并发控制；每次访问使用短 Session。"""

from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from app.agents import prompts, tools
from app.core.errors import BusinessError
from app.models import AgentRun, AgentEvent, User
from app.core.throttle import consume

TERMINAL = {"completed", "failed", "cancelled", "budget_exhausted", "expired"}


def now():
    # 数据库存 UTC-naive，HTTP 展示明确加 Z；与旧业务本地时间分开。
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RunStore:
    def __init__(self, engine, actor, config):
        self.engine, self.actor, self.config = engine, actor, config

    def owned(self, session, run_id, *, execution=False):
        user = session.exec(select(User).where(User.id == self.actor.user_id)).first()
        if not user or not user.is_active:
            raise BusinessError("账号不可用", 401)
        row = session.exec(select(AgentRun).where(
            AgentRun.id == run_id, AgentRun.user_id == self.actor.user_id,
        )).first()
        if not row:
            raise BusinessError("Agent 运行不存在", 404)
        if execution and row.token_version != user.token_version:
            raise BusinessError("运行身份已撤销，请创建新运行", 401)
        return row

    def get(self, run_id, *, execution=False):
        with Session(self.engine) as session:
            row = self.owned(session, run_id, execution=execution)
            session.expunge(row)
            return row

    def event(self, session, row, kind, payload):
        session.add(AgentEvent(
            run_id=row.id, user_id=row.user_id, sequence=row.revision,
            kind=kind, payload=payload, created_at=now(),
        ))

    def create(self, body):
        if not self.config.agent_enabled:
            raise BusinessError("Agent 尚未启用，请在设置中配置大模型 API", 503)
        with Session(self.engine) as session:
            user = session.get(User, self.actor.user_id)
            if not user or not user.is_active:
                raise BusinessError("账号不可用", 401)
            existing = session.exec(select(AgentRun).where(
                AgentRun.user_id == self.actor.user_id, AgentRun.request_key == body.request_key,
            )).first()
            if existing:
                if (existing.input_text != body.message or existing.timezone != body.timezone
                        or existing.skill != body.skill):
                    raise BusinessError("幂等键已用于不同请求", 409)
                session.expunge(existing)
                return existing
            consume(session, self.config, f"agent-create-{body.skill}", str(self.actor.user_id),
                    self.config.agent_run_limit_per_window,
                    window_seconds=self.config.agent_rate_window_seconds)
            prompt_version, prompt_hash = prompts.VERSIONS[body.skill]
            row = AgentRun(
                id=uuid4().hex, user_id=user.id, token_version=user.token_version,
                request_key=body.request_key, active_slot=1, skill=body.skill,
                model=self.config.agent_model, prompt_version=prompt_version,
                prompt_hash=prompt_hash, tool_version=tools.SKILL_VERSIONS[body.skill],
                timezone=body.timezone, input_text=body.message,
                state=[{"role": "user", "content": body.message}],
                pricing={"input_rate": self.config.agent_input_usd_per_million,
                         "output_rate": self.config.agent_output_usd_per_million,
                         "max_usd": self.config.agent_max_estimated_cost_usd},
                created_at=now(), updated_at=now(),
            )
            session.add(row)
            try:
                session.flush()
                self.event(session, row, "run_created", {"prompt_version": prompt_version})
                session.commit()
            except IntegrityError:
                session.rollback()
                # 相同幂等键并发创建允许取回结果；其他活跃 Run 拒绝。
                existing = session.exec(select(AgentRun).where(
                    AgentRun.user_id == self.actor.user_id,
                    AgentRun.request_key == body.request_key,
                )).first()
                if (existing and existing.input_text == body.message
                        and existing.timezone == body.timezone and existing.skill == body.skill):
                    session.expunge(existing)
                    return existing
                raise BusinessError("已有活跃运行，请完成或取消后再创建", 409) from None
            session.refresh(row)
            session.expunge(row)
            return row

    def save(self, row, changes, kind, payload=None, *, execution=True):
        with Session(self.engine) as session:
            self.owned(session, row.id, execution=execution)
            values = {**changes, "revision": row.revision + 1, "updated_at": now()}
            if values.get("status") in TERMINAL:
                values.update(active_slot=None, lease_until=None, pending=None, state=[])
            result = session.execute(update(AgentRun).where(
                AgentRun.id == row.id, AgentRun.user_id == self.actor.user_id,
                AgentRun.revision == row.revision,
            ).values(**values).execution_options(synchronize_session=False))
            if result.rowcount != 1:
                raise BusinessError("运行状态已变化", 409)
            row = self.owned(session, row.id, execution=execution)
            session.refresh(row)
            self.event(session, row, kind, payload or {})
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def events(self, run_id, after=-1):
        with Session(self.engine) as session:
            self.owned(session, run_id)
            return session.exec(select(AgentEvent).where(
                AgentEvent.run_id == run_id, AgentEvent.user_id == self.actor.user_id,
                AgentEvent.sequence > after,
            ).order_by(AgentEvent.sequence).limit(100)).all()

    def recent(self):
        with Session(self.engine) as session:
            rows = session.exec(select(AgentRun).where(
                AgentRun.user_id == self.actor.user_id,
            ).order_by(AgentRun.created_at.desc()).limit(20)).all()
            for row in rows:
                session.expunge(row)
            return rows

    def delete(self, run_id):
        """Delete one finished conversation and its persisted lifecycle events."""
        with Session(self.engine) as session:
            row = self.owned(session, run_id)
            if row.status not in TERMINAL:
                raise BusinessError("进行中的对话不能删除，请先停止或完成", 409)
            session.delete(row)
            session.commit()


def view(row):
    pending = None
    if row.pending:
        pending = {key: row.pending[key] for key in (
            "approval_id", "tool", "arguments", "target", "expires_at", "decision",
        )}
    return {
        "id": row.id, "status": row.status, "message": row.input_text,
        "output": row.output_text, "model": row.model, "prompt_version": row.prompt_version,
        "skill": row.skill, "steps": row.steps, "tool_calls": row.tool_calls,
        "usage": {"input_tokens": row.input_tokens, "output_tokens": row.output_tokens},
        "estimated_cost_usd": (
            (row.input_tokens * row.pricing["input_rate"] + row.output_tokens * row.pricing["output_rate"]) / 1_000_000
            if row.pricing.get("input_rate") and row.pricing.get("output_rate") else None
        ),
        "execution_ms": row.execution_ms, "error_code": row.error_code,
        "approval": pending, "created_at": row.created_at.isoformat() + "Z",
        "updated_at": row.updated_at.isoformat() + "Z",
    }
