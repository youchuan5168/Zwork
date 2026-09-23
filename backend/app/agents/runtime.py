"""受控单 Agent Loop。所有模型等待均在数据库事务之外。"""

import asyncio
import time
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import uuid4
from sqlalchemy import update
from sqlmodel import Session, select
from app.agents import prompts, tools
from app.agents.contracts import ProviderError
from app.agents.store import RunStore, TERMINAL, now
from app.core.errors import BusinessError
from app.models import AgentRun
from app.models import User
from app.services.applications import ApplicationService

RECOVERABLE_SKILLS = {
    "job_match", "career_manager", "daily_briefing", "interview_preparation",
    "application_follow_up", "weekly_review",
}


def digest(value):
    return sha256(tools.encode(value).encode()).hexdigest()


def binding_keys(_tool):
    return sorted(["tool", "arguments", "target", "approval_id", "expires_at", "call_id"])


class AgentRuntime:
    def __init__(self, engine, actor, config, provider):
        self.store = RunStore(engine, actor, config)
        self.engine, self.actor, self.config, self.provider = engine, actor, config, provider

    def settle(self, row):
        if row.status in TERMINAL:
            return row
        if row.status == "running" and row.lease_until and row.lease_until <= now():
            if row.skill in RECOVERABLE_SKILLS and not row.pending:
                recoveries = sum(event.kind == "run_requeued"
                                 for event in self.store.events(row.id))
                if recoveries < 2:
                    state = list(row.state)
                    dropped_call = bool(state and state[-1].get("type") == "function_call")
                    if dropped_call:
                        state.pop()  # 未完成的只读工具调用重新交由模型决定。
                    return self.store.save(row, {
                        "status": "queued", "lease_until": None, "state": state,
                        "tool_calls": row.tool_calls - int(dropped_call),
                    }, "run_requeued", {"reason": "lease_expired"}, execution=False)
            return self.store.save(row, {"status": "expired", "error_code": "run_expired"},
                                   "run_expired", execution=False)
        expired = (
            row.pending and datetime.fromisoformat(row.pending["expires_at"].rstrip("Z")) <= now()
        ) or (
            row.status == "queued" and not row.pending
            and row.updated_at + timedelta(seconds=self.config.agent_approval_ttl_seconds) <= now()
        )
        if expired:
            return self.store.save(row, {"status": "expired", "error_code": "run_expired"},
                                   "run_expired", execution=False)
        return row

    def cancel(self, run_id):
        row = self.store.get(run_id)
        if row.status in TERMINAL:
            return row
        return self.store.save(row, {"status": "cancelled"}, "run_cancelled", execution=False)

    def decide(self, run_id, decision):
        row = self.settle(self.store.get(run_id, execution=True))
        pending = row.pending
        if not pending or pending["approval_id"] != decision.approval_id:
            raise BusinessError("审批不存在或已失效", 409)
        if pending["decision"] is not None:
            if pending["decision"] != decision.decision:
                raise BusinessError("审批决策不能更改", 409)
            return row
        if row.status != "waiting_approval":
            raise BusinessError("运行不在审批状态", 409)
        pending = {**pending, "decision": decision.decision}
        return self.store.save(row, {"status": "queued", "pending": pending},
                               "approval_decided", {"decision": decision.decision})

    def _claim(self, session, row):
        """原子占用运行行并消费审批；返回决策是否为批准。"""
        pending = row.pending
        conditions = [
            AgentRun.id == row.id, AgentRun.user_id == self.actor.user_id,
            AgentRun.status == "running", AgentRun.revision == row.revision,
        ]
        result = session.execute(update(AgentRun).where(*conditions).values(
            revision=row.revision + 1,
        ).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise BusinessError("运行状态已变化", 409)
        return pending.get("decision") == "approve"

    def _finalize(self, session, row, pending, result, arguments):
        state = [*row.state, {"type": "function_call_output", "call_id": pending["call_id"],
                              "output": tools.encode(result)}]
        session.execute(update(AgentRun).where(AgentRun.id == row.id).values(
            state=state, pending=None, updated_at=now(),
        ).execution_options(synchronize_session=False))
        fresh = self.store.owned(session, row.id, execution=True)
        session.refresh(fresh)
        self.store.event(session, fresh, "tool_executed", {
            "tool": pending["tool"], "approval_id": pending["approval_id"],
            "changed": result.get("changed", result.get("created", False)),
            "arguments_hash": digest(arguments),
            "edited": result.get("edited", False),
        })
        return fresh

    def apply_approval(self, row):
        """消费批准动作、业务修改、工具结果和审计同事务；条件更新阻止双执行。"""
        pending = row.pending
        if pending["binding"] != digest({key: pending[key] for key in binding_keys(pending["tool"])}):
            raise BusinessError("审批绑定无效", 409)
        body = tools.validate(pending["tool"], tools.encode(pending["arguments"]), row.skill)
        with Session(self.engine) as session:
            # 与撤销会话的 User UPDATE 在支持行锁的数据库中串行化。
            session.exec(select(User).where(
                User.id == self.actor.user_id,
            ).with_for_update()).first()
            self.store.owned(session, row.id, execution=True)
            if datetime.fromisoformat(pending["expires_at"].rstrip("Z")) <= now():
                raise BusinessError("审批已过期", 409)
            # 先占用运行行，取消和重复 execute 无法跨越此原子写边界。
            approved = self._claim(session, row)
            if approved:
                target = pending["target"]
                result = ApplicationService(session, self.actor).change_stage_in_transaction(
                    body.application_id, body.stage, target["stage"],
                    datetime.fromisoformat(target["updated_at"]),
                )
            else:
                result = {"error": "user_rejected", "changed": False}
            fresh = self._finalize(session, row, pending, result, pending["arguments"])
            session.commit()
            session.refresh(fresh)
            session.expunge(fresh)
            return fresh

    async def execute(self, run_id):
        row = self.settle(self.store.get(run_id, execution=True))
        if row.status in TERMINAL or row.status == "waiting_approval":
            return row
        if row.status != "queued":
            raise BusinessError("运行正在执行", 409)
        if not self.config.agent_enabled:
            raise BusinessError("Agent 尚未启用", 503)
        row = self.store.save(row, {
            "status": "running", "lease_until": now() + timedelta(seconds=self.config.agent_timeout_seconds),
        }, "run_started")
        started = time.monotonic()
        prior_ms = row.execution_ms
        try:
            if (row.prompt_version, row.prompt_hash, row.tool_version) != (
                *prompts.VERSIONS[row.skill], tools.SKILL_VERSIONS[row.skill],
            ):
                raise ProviderError("runtime_version_changed")
            if row.pending:
                if row.execution_ms >= self.config.agent_timeout_seconds * 1000:
                    raise ProviderError("time_budget")
                row = self.apply_approval(row)
            while True:
                row = self.store.get(run_id, execution=True)
                if row.status != "running":
                    return row
                elapsed_ms = prior_ms + int((time.monotonic() - started) * 1000)
                remaining = self.config.agent_timeout_seconds - elapsed_ms / 1000
                if remaining <= 0:
                    raise ProviderError("time_budget")
                if row.steps >= self.config.agent_max_steps:
                    raise ProviderError("step_budget")
                instructions = prompts.build(row.timezone, row.skill)
                schema = tools.schemas(row.skill)
                # UTF-8 字节数作为保守 Token 上界，再预留协议开销；不依赖模型的自报预算。
                context_bytes = len(tools.encode([instructions, row.state, schema]).encode())
                if context_bytes > self.config.agent_max_context_bytes:
                    raise ProviderError("context_budget")
                reserve = context_bytes + 1024 + self.config.agent_max_output_tokens
                if row.input_tokens + row.output_tokens + reserve > self.config.agent_max_total_tokens:
                    raise ProviderError("token_budget")
                pricing = row.pricing
                forecast = ((row.input_tokens + context_bytes + 1024) * pricing["input_rate"]
                            + (row.output_tokens + self.config.agent_max_output_tokens) * pricing["output_rate"]) / 1_000_000
                if pricing["max_usd"] and forecast > pricing["max_usd"]:
                    raise ProviderError("cost_budget")
                row = self.store.save(row, {"steps": row.steps + 1, "execution_ms": elapsed_ms},
                                      "model_started", {"step": row.steps + 1})
                turn = await asyncio.wait_for(self.provider.complete(
                    model=row.model, instructions=instructions, items=row.state, tools=schema,
                    max_output_tokens=self.config.agent_max_output_tokens, timeout=remaining,
                ), timeout=remaining)
                # 取消/撤销在返回后再次核对；丢弃取消后的结果，不开始新工具。
                fresh = self.store.get(run_id, execution=True)
                if fresh.status != "running":
                    return fresh
                if fresh.revision != row.revision:
                    raise BusinessError("运行状态已变化", 409)
                if min(turn.input_tokens, turn.output_tokens) < 0:
                    raise ProviderError("provider_invalid_usage")
                elapsed_ms = prior_ms + int((time.monotonic() - started) * 1000)
                row = self.store.save(row, {
                    "input_tokens": row.input_tokens + turn.input_tokens,
                    "output_tokens": row.output_tokens + turn.output_tokens,
                    "execution_ms": elapsed_ms,
                }, "model_completed", {"input_tokens": turn.input_tokens,
                                       "output_tokens": turn.output_tokens})
                if row.input_tokens + row.output_tokens > self.config.agent_max_total_tokens:
                    raise ProviderError("token_budget")
                cost = (row.input_tokens * pricing["input_rate"] + row.output_tokens * pricing["output_rate"]) / 1_000_000
                if pricing["max_usd"] and cost > pricing["max_usd"]:
                    raise ProviderError("cost_budget")
                if elapsed_ms >= self.config.agent_timeout_seconds * 1000:
                    raise ProviderError("time_budget")
                if not turn.calls:
                    if not turn.text.strip() or len(turn.text.encode()) > 20000:
                        raise ProviderError("provider_invalid_output")
                    return self.store.save(row, {"status": "completed", "output_text": turn.text},
                                           "run_completed")
                specs = tools.SKILL_SPECS[row.skill]
                if len(turn.calls) > 1 and any(
                    specs.get(call.name, (None, None, False))[2] for call in turn.calls
                ):
                    # 多调用批次中绝不混入审批或写入工具，避免部分执行后等待审批。
                    raise ProviderError("multiple_tool_calls")
                if row.tool_calls + len(turn.calls) > self.config.agent_max_tool_calls:
                    raise ProviderError("tool_budget")
                seen_ids = {item.get("call_id") for item in row.state}
                for call in turn.calls:
                    if (not call.call_id or len(call.call_id) > 128
                            or len(call.arguments.encode()) > 8192 or call.call_id in seen_ids):
                        raise ProviderError("provider_invalid_call")
                    seen_ids.add(call.call_id)
                for call in turn.calls:
                    fresh = self.store.get(run_id, execution=True)
                    if fresh.status != "running":
                        return fresh
                    if fresh.revision != row.revision:
                        raise BusinessError("运行状态已变化", 409)
                    if prior_ms + int((time.monotonic() - started) * 1000) >= \
                            self.config.agent_timeout_seconds * 1000:
                        raise ProviderError("time_budget")
                    state = [*row.state, {"type": "function_call", "call_id": call.call_id,
                                          "name": call.name, "arguments": call.arguments}]
                    row = self.store.save(row, {"state": state, "tool_calls": row.tool_calls + 1},
                                          "tool_requested", {"tool": call.name[:128]})
                    try:
                        body = tools.validate(call.name, call.arguments, row.skill)
                        self.store.get(run_id, execution=True)
                        if specs[call.name][2]:
                            pending = {
                                "approval_id": uuid4().hex, "tool": call.name, "call_id": call.call_id,
                                "arguments": body.model_dump(mode="json"),
                                "target": tools.snapshot(self.engine, self.actor, body, row.token_version),
                                "expires_at": (now() + timedelta(
                                    seconds=self.config.agent_approval_ttl_seconds)).isoformat() + "Z",
                                "decision": None,
                            }
                            pending["binding"] = digest({key: pending[key] for key in
                                                         binding_keys(call.name)})
                            return self.store.save(row, {
                                "status": "waiting_approval", "pending": pending,
                                "lease_until": None,
                                "execution_ms": prior_ms + int((time.monotonic() - started) * 1000),
                            }, "approval_required", {"approval_id": pending["approval_id"],
                                                    "tool": call.name})
                        result = tools.read(self.engine, self.actor, call.name, body,
                                            row.token_version)
                    except BusinessError as error:
                        if error.status_code == 401:
                            raise
                        result = {"error": "tool_validation_failed" if error.status_code == 400
                                  else "tool_target_unavailable"}
                    output = tools.encode(result)
                    if len(output.encode()) > 16000:
                        output = tools.encode({"error": "tool_output_too_large", "hint": "缩小查询范围"})
                    row = self.store.save(row, {"state": [*row.state, {
                        "type": "function_call_output", "call_id": call.call_id, "output": output,
                    }], "execution_ms": prior_ms + int((time.monotonic() - started) * 1000)},
                        "tool_completed", {"tool": call.name[:128], "ok": "error" not in result})
        except asyncio.CancelledError:
            self.cancel(run_id)
            raise
        except (ProviderError, asyncio.TimeoutError, BusinessError) as error:
            if isinstance(error, BusinessError) and error.status_code == 409 \
                    and error.detail == "运行状态已变化":
                return self.store.get(run_id)
            if isinstance(error, BusinessError):
                code = "identity_revoked" if error.status_code == 401 else "target_or_state_changed"
            else:
                code = str(error) if isinstance(error, ProviderError) else "time_budget"
                if code not in {
                    "provider_incomplete", "provider_refused", "provider_timeout",
                    "provider_unavailable", "provider_output_too_large", "runtime_version_changed",
                    "provider_auth_failed", "provider_rate_limited",
                    "provider_invalid_usage", "provider_invalid_output", "provider_invalid_call",
                    "multiple_tool_calls", "time_budget", "step_budget", "tool_budget",
                    "token_budget", "context_budget", "cost_budget",
                }:
                    code = "provider_unavailable"
            return self.fail(run_id, code, prior_ms + int((time.monotonic() - started) * 1000))
        except Exception:
            # 不把 SDK/数据库异常文本送往客户端或 Trace。
            return self.fail(run_id, "internal_error", prior_ms + int((time.monotonic() - started) * 1000))

    def fail(self, run_id, code, elapsed_ms):
        row = self.store.get(run_id)
        if row.status != "running":
            return row
        status = "budget_exhausted" if code.endswith("_budget") else "failed"
        try:
            return self.store.save(row, {"status": status, "error_code": code,
                                        "execution_ms": elapsed_ms}, "run_failed", {"code": code},
                                   execution=False)
        except BusinessError as error:
            if error.status_code == 409:
                return self.store.get(run_id)
            raise
