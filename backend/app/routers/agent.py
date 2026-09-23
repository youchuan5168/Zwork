"""Agent HTTP 适配器；鉴权立即释放 Session，流式连接不持有事务。"""

import asyncio
from fastapi import APIRouter, Depends, Request, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from app.agents.contracts import RunCreate, ApprovalDecision
from app.agents.providers import OpenAIResponsesProvider, DeepSeekChatProvider
from app.agents.runtime import AgentRuntime
from app.agents.store import RunStore, TERMINAL, view
from app.agents.tools import SKILL_SPECS, encode
from app.core.actor import Actor
from app.deps import get_current_user
from app.services.llm_settings import effective_config

router = APIRouter(prefix="/api/agent", tags=["agent"])


def actor_for_agent(request: Request):
    with Session(request.app.state.engine) as session:
        return Actor(get_current_user(request, session).id)


def resolved_config(request: Request, actor: Actor):
    """用户保存过大模型配置则覆盖服务器默认，预算等限制仍取全局设置。"""
    with Session(request.app.state.engine) as session:
        return effective_config(session, request.app.state.settings, actor.user_id)


def runtime(request, actor):
    config = resolved_config(request, actor)
    provider = request.app.state.agent_provider
    if provider is None and config.agent_enabled:
        provider_type = DeepSeekChatProvider if config.agent_provider == "deepseek_chat" else OpenAIResponsesProvider
        provider = provider_type(config.openai_api_key, api_url=config.agent_api_url)
    return AgentRuntime(request.app.state.engine, actor, config, provider)


@router.get("/capabilities")
def capabilities(request: Request, actor: Actor = Depends(actor_for_agent)):
    config = resolved_config(request, actor)
    return {"enabled": config.agent_enabled, "model": config.agent_model,
            "tools": list(SKILL_SPECS["assistant"]),
            "skills": {skill: list(specs) for skill, specs in SKILL_SPECS.items()},
            "streaming": "persisted_lifecycle_events"}


@router.post("/runs", status_code=201)
def create_run(body: RunCreate, request: Request, actor: Actor = Depends(actor_for_agent)):
    store = RunStore(request.app.state.engine, actor, resolved_config(request, actor))
    return view(store.create(body))


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request, actor: Actor = Depends(actor_for_agent)):
    service = runtime(request, actor)
    return view(service.settle(service.store.get(run_id)))


@router.get("/runs")
def list_runs(request: Request, actor: Actor = Depends(actor_for_agent)):
    service = runtime(request, actor)
    return [view(service.settle(row)) for row in service.store.recent()]


@router.delete("/runs/{run_id}")
def delete_run(run_id: str, request: Request, actor: Actor = Depends(actor_for_agent)):
    runtime(request, actor).store.delete(run_id)
    return {"message": "对话已删除"}


@router.post("/runs/{run_id}/execute")
async def execute_run(run_id: str, request: Request, actor: Actor = Depends(actor_for_agent)):
    return view(await runtime(request, actor).execute(run_id))


@router.post("/runs/{run_id}/approval")
def approve_run(
    run_id: str, body: ApprovalDecision, request: Request,
    actor: Actor = Depends(actor_for_agent),
):
    return view(runtime(request, actor).decide(run_id, body))


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, request: Request, actor: Actor = Depends(actor_for_agent)):
    return view(runtime(request, actor).cancel(run_id))


@router.get("/runs/{run_id}/events")
async def events(
    run_id: str, request: Request, after: int = Query(default=-1, ge=-1),
    actor: Actor = Depends(actor_for_agent),
):
    service = runtime(request, actor)
    service.store.get(run_id)  # 非所有者在开始流前返回 404。
    supplied = request.headers.get("last-event-id")
    if supplied:
        try:
            after = max(after, int(supplied))
        except ValueError:
            raise HTTPException(400, "无效的事件游标") from None

    async def stream():
        cursor = after
        while not await request.is_disconnected():
            try:
                # 每次轮询重新校验 Cookie/Bearer 的有效期与撤销状态。
                actor_for_agent(request)
            except HTTPException:
                yield "event: auth_expired\ndata: {}\n\n"
                return
            row = service.settle(service.store.get(run_id))
            for event in service.store.events(run_id, cursor):
                cursor = event.sequence
                yield f"id: {cursor}\nevent: {event.kind}\ndata: {encode(event.payload)}\n\n"
            if row.status in TERMINAL or row.status == "waiting_approval":
                return
            yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "X-Accel-Buffering": "no", "Cache-Control": "no-store",
    })
