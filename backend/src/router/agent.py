"""智能助手路由（A4：LangGraph；SSE 流式 + 可降级）。"""
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agent.graphs.lab_assistant import (
    experts_for_role,
    graph_name_for_role,
    llm_configured,
    run_assistant,
    stream_assistant,
    warmup_assistant,
)
from agent.tools.lab_tools import ADMIN_TOOL_NAMES, tool_names_for_role
from config.request import get_db
from crud import agent_chat as chat_crud
from model.user import User
from utils.auth import get_current_user
from utils.response import success_response

router = APIRouter(prefix="/api/agent", tags=["agent"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = Field(default=None, max_length=64)


@router.post("/chat")
async def chat(body: ChatIn, user: User = Depends(get_current_user)):
    """非流式兜底：整段返回。演示/兼容用。"""
    data = run_assistant(
        user_id=user.id,
        message=body.message,
        thread_id=body.thread_id,
        role=user.role,
    )
    degraded = bool(data.get("degraded"))
    return success_response(
        message="助手降级中" if degraded else "ok",
        data=data,
    )


@router.post("/chat/stream")
async def chat_stream(body: ChatIn, user: User = Depends(get_current_user)):
    """
    SSE：LangGraph stream_mode=messages 的 token 碎片。
    前端用 fetch + ReadableStream 消费，不要用 EventSource（仅 GET）。
    """
    user_id = user.id
    role = user.role
    message = body.message
    thread_id = body.thread_id

    async def event_stream():
        async for item in stream_assistant(
            user_id=user_id,
            message=message,
            role=role,
            thread_id=thread_id,
        ):
            if item.get("done"):
                yield "event: done\ndata: {}\n\n"
                continue
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.get("/history")
async def agent_history(
    limit: int = Query(default=100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按用户取最近聊天（默认 100 条），重新登录也能在助手页回看。"""
    rows = await chat_crud.list_recent_for_user(db, user_id=user.id, limit=limit)
    return success_response(
        message="ok",
        data={
            "user_id": user.id,
            "limit": limit,
            "items": [
                {
                    "id": r.id,
                    "role": r.role,
                    "content": r.content,
                    "thread_id": r.thread_id,
                    "create_at": r.create_at.isoformat(sep=" ") if r.create_at else None,
                }
                for r in rows
            ],
        },
    )


@router.post("/warmup")
async def agent_warmup(user: User = Depends(get_current_user)):
    """进入助手页时预热图和模型连接，缩短第一次提问的等待。"""
    data = await warmup_assistant(user_id=user.id, role=user.role)
    return success_response(message="ok" if data.get("warm") else "未预热", data=data)


@router.get("/status")
async def agent_status(user: User = Depends(get_current_user)):
    ready = llm_configured()
    tools = tool_names_for_role(user.role)
    return success_response(
        message="ok",
        data={
            "llm_configured": ready,
            "graph_ready": ready,
            "degraded": not ready,
            "stream": True,
            "architecture": "single_agent",
            "graph": graph_name_for_role(user.role),
            "experts": list(experts_for_role(user.role)),
            "role": user.role,
            "short_term_memory": True,
            "memory_backend": "langgraph.MemorySaver",
            "core_tools": tools,
            "admin_tools": list(ADMIN_TOOL_NAMES),
            "graphs": ["student_graph", "teacher_graph", "admin_graph"],
            "hitl_confirm_gate": True,
            "p1_tools": ["cancel_reservation", "access_help", "ack_safety", "issue_passcode"],
        },
    )
