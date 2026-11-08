"""
实验室预约助手 — 三角色图隔离 + 单 Agent。

student_graph / teacher_graph / admin_graph：
- 拓扑相同：START → agent → END（单节点内跑模型↔工具环）
- 工具集按角色物理分开编译；学生/老师无审批、改课工具
- JWT 角色决定进哪张图；对错以业务库为准

相对原「主管多专家」：去掉主管路由那一次云端调用，降低延时。
确认/纯随便仍可入口直办；查实验室等在工具环内早停。

百炼 OpenAI 兼容：LLM_BASE_URL + LLM_API_KEY + LLM_MODEL
"""
from __future__ import annotations

import os
import re
import traceback
from datetime import datetime, timedelta
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from langchain_core.messages import AIMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.graphs.supervisor import (
    EXPERT_PROMPTS,
    _last_human_text,
    _run_expert_tool_loop,
    resolve_thread_id,
    thread_config,
)
from agent.grounding import (
    try_auto_confirm_pending,
    try_auto_vague_book,
    try_answer_recent_cancel,
)
from agent.tools.lab_tools import (
    build_admin_tools,
    build_student_tools,
    build_teacher_tools,
    tool_names_for_role,
)

GRAPH_STUDENT = "student_graph"
GRAPH_TEACHER = "teacher_graph"
GRAPH_ADMIN = "admin_graph"
ARCH = "single_agent"

_CHECKPOINTER = MemorySaver()


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int


def llm_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY", "").strip())


def _make_llm(*, streaming: bool = False):
    model = os.getenv("LLM_MODEL", "deepseek-v3")
    # Qwen3 思考链偶发只出 reasoning、正文为空；对话办理关闭思考更稳
    extra = {}
    if "qwen3" in model.lower() or "qwen-3" in model.lower():
        extra["extra_body"] = {"enable_thinking": False}
    return ChatOpenAI(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=model,
        temperature=0.2,
        streaming=streaming,
        request_timeout=float(os.getenv("LLM_TIMEOUT_SEC", "35")),
        max_retries=1,
        **extra,
    )


def text_of(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                parts.append(str(block.get("text") or ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def normalize_role(role: str | None) -> str:
    r = (role or "student").strip().lower()
    if r in ("admin", "teacher", "student"):
        return r
    return "student"


def graph_name_for_role(role: str | None) -> str:
    r = normalize_role(role)
    if r == "admin":
        return GRAPH_ADMIN
    if r == "teacher":
        return GRAPH_TEACHER
    return GRAPH_STUDENT


def experts_for_role(role: str | None) -> tuple[str, ...]:
    """对外状态字段：单 Agent 图统一报 agent；便于前端/答辩说明。"""
    return ("agent",)


def _role_system_prompt(role: str) -> str:
    r = normalize_role(role)
    base = (
        "你是校内实验室预约与通行助手。根据用户意图调用工具办理或解答；"
        "对用户只说自然语言，禁止 Markdown 星号堆砌；禁止报设备号/door_id。"
        "写库/预检结果以工具 JSON 为准，禁止空口说预约成功或列表为空。"
    )
    parts = [base, EXPERT_PROMPTS["advisor"], EXPERT_PROMPTS["booking"]]
    if r == "admin":
        parts.append(EXPERT_PROMPTS["approval"])
        parts.append(EXPERT_PROMPTS["schedule"])
    return "\n".join(parts)


def _tools_for_role(user_id: int, role: str) -> list:
    r = normalize_role(role)
    if r == "admin":
        return build_admin_tools(user_id)
    if r == "teacher":
        return build_teacher_tools(user_id)
    return build_student_tools(user_id)


def build_role_agent_graph(user_id: int, role: str = "student") -> Any:
    """按角色编译单 Agent 图（工具集隔离）。"""
    r = normalize_role(role)
    tools = _tools_for_role(user_id, r)
    system = _role_system_prompt(r)

    def agent_node(state: AgentState):
        now = datetime.now()
        clock = (
            f"\n【系统当前时间】{now.strftime('%Y-%m-%d %H:%M:%S')}；"
            f"今天={now.strftime('%Y-%m-%d')}；"
            f"明天={(now + timedelta(days=1)).strftime('%Y-%m-%d')}；"
            f"后天={(now + timedelta(days=2)).strftime('%Y-%m-%d')}。"
            "相对日期必须按此推算，预约时间写成 YYYY-MM-DD HH:MM:SS。"
        )
        msgs = list(state.get("messages") or [])
        uid = int(state.get("user_id") or user_id)
        human = _last_human_text(msgs)
        auto = try_auto_confirm_pending(uid, human)
        if auto:
            return {"messages": [AIMessage(content=auto)]}
        ai = _run_expert_tool_loop(
            llm_factory=_make_llm,
            tools=tools,
            system=system + clock,
            messages=msgs,
        )
        content = text_of(ai)
        # 历史过脏时模型可能空回：只用本轮用户话再试一次
        if not (content or "").strip() and human.strip():
            ai = _run_expert_tool_loop(
                llm_factory=_make_llm,
                tools=tools,
                system=system + clock,
                messages=[HumanMessage(content=human)],
            )
            content = text_of(ai)
        if not (content or "").strip():
            if re.search(r"课表|排课|占档", human or ""):
                content = (
                    "这次没能办完排课。请补上实验室名称，例如："
                    "「在网络实验室，明天 10:00-12:00 加一节数学课」。"
                )
            else:
                content = (
                    "我这边没有生成有效回复。请再说一次实验室与时间，"
                    "或说「随便约一间」／「换成第二个」。"
                )
            ai = AIMessage(content=content)
        return {"messages": [ai]}

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_edge(START, "agent")
    g.add_edge("agent", END)
    return g.compile(checkpointer=_CHECKPOINTER)


def build_student_graph(user_id: int) -> Any:
    """学生图：单 Agent + 学生工具集（无审批/改课）。"""
    return build_role_agent_graph(user_id, "student")


def build_teacher_graph(user_id: int) -> Any:
    """老师图：单 Agent + 老师工具集。"""
    return build_role_agent_graph(user_id, "teacher")


def build_admin_graph(user_id: int) -> Any:
    """管理图：单 Agent + 全量管理工具。"""
    return build_role_agent_graph(user_id, "admin")


def build_lab_assistant_graph(user_id: int, role: str = "student") -> Any:
    r = normalize_role(role)
    if r == "admin":
        return build_admin_graph(user_id)
    if r == "teacher":
        return build_teacher_graph(user_id)
    return build_student_graph(user_id)


_GRAPH_CACHE: dict[tuple[int, str], Any] = {}


def get_lab_assistant_graph(user_id: int, role: str = "student") -> Any:
    r = normalize_role(role)
    key = (user_id, r)
    graph = _GRAPH_CACHE.get(key)
    if graph is None:
        graph = build_lab_assistant_graph(user_id, role=r)
        _GRAPH_CACHE[key] = graph
    return graph


def initial_agent_state(user_id: int, message: str) -> dict:
    return {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
    }


# 兼容旧导入名
def initial_supervisor_state(user_id: int, message: str) -> dict:
    return initial_agent_state(user_id, message)


async def warmup_assistant(user_id: int, role: str = "student") -> dict:
    """打开助手页：编译对应角色单 Agent 图，并预热模型连接。"""
    if not llm_configured():
        return {
            "warm": False,
            "reason": "no_key",
            "graph": graph_name_for_role(role),
            "architecture": ARCH,
            "experts": list(experts_for_role(role)),
        }
    try:
        get_lab_assistant_graph(user_id, role=role)
        llm = _make_llm().bind(max_tokens=1)
        await llm.ainvoke([HumanMessage(content="只回复一个字：好")])
        return {
            "warm": True,
            "graph": graph_name_for_role(role),
            "architecture": ARCH,
            "experts": list(experts_for_role(role)),
        }
    except Exception as e:
        return {
            "warm": False,
            "reason": str(e),
            "graph": graph_name_for_role(role),
            "architecture": ARCH,
            "experts": list(experts_for_role(role)),
        }


def _persist_chat_pair(
    *, user_id: int, thread_id: str, user_text: str, assistant_text: str
) -> None:
    try:
        from config.request import SyncSessionLocal
        from crud import agent_chat as chat_crud

        with SyncSessionLocal() as session:
            chat_crud.sync_append_pair(
                session,
                user_id=user_id,
                thread_id=thread_id,
                user_text=user_text,
                assistant_text=assistant_text,
            )
    except Exception:
        pass


def _try_fast_booking_reply(user_id: int, message: str) -> str | None:
    """确认直办落库；追问刚才取消了什么；纯「随便约」可直办挑档。"""
    return (
        try_auto_confirm_pending(user_id, message)
        or try_answer_recent_cancel(user_id, message)
        or try_auto_vague_book(user_id, message)
    )


def _meta(role: str, tid: str, tool_names: list) -> dict:
    return {
        "core_tools": tool_names,
        "graph": graph_name_for_role(role),
        "architecture": ARCH,
        "experts": list(experts_for_role(role)),
        "thread_id": tid,
        "short_term_memory": True,
    }


async def stream_assistant(
    user_id: int,
    message: str,
    role: str = "student",
    thread_id: str | None = None,
):
    """确认/随便直办；其余单 Agent ainvoke，整段下发。"""
    import asyncio

    from utils.text_clean import scrub_assistant_text

    r = normalize_role(role)
    tool_names = tool_names_for_role(r)
    tid = resolve_thread_id(user_id, thread_id)
    if not llm_configured():
        yield {
            "degraded": True,
            "t": "助手暂不可用（未配置大模型密钥）。请使用「预约管理 / 模拟门禁」完成演示。",
            **_meta(r, tid, tool_names),
        }
        yield {"done": True}
        return

    # 短提示，避免长等待空白气泡
    yield {"t": "正在办理…", "pending": True, "thread_id": tid}

    try:
        fast = await asyncio.to_thread(_try_fast_booking_reply, user_id, message)
        if fast:
            reply = scrub_assistant_text(fast)
            await asyncio.to_thread(
                _persist_chat_pair,
                user_id=user_id,
                thread_id=tid,
                user_text=message,
                assistant_text=reply,
            )
            yield {
                "t": reply,
                "degraded": False,
                "expert": "agent",
                "fast_path": True,
                **_meta(r, tid, tool_names),
            }
            yield {"done": True, **_meta(r, tid, tool_names)}
            return

        app = get_lab_assistant_graph(user_id, role=r)
        result = await asyncio.wait_for(
            app.ainvoke(
                initial_agent_state(user_id, message),
                config=thread_config(user_id, thread_id),
            ),
            timeout=60,
        )
        messages = result.get("messages") or []
        reply = ""
        for m in reversed(messages):
            if not isinstance(m, AIMessage):
                continue
            chunk = text_of(m)
            if not (chunk or "").strip():
                continue
            # 优先无工具调用的最终话术；否则也接受带正文的 AIMessage
            if not (m.tool_calls or []):
                reply = chunk
                break
            if not reply:
                reply = chunk
        if not reply:
            reply = "已处理，请补充实验室或时间后再试。"

        reply = scrub_assistant_text(reply)
        await asyncio.to_thread(
            _persist_chat_pair,
            user_id=user_id,
            thread_id=tid,
            user_text=message,
            assistant_text=reply,
        )
        yield {
            "t": reply,
            "degraded": False,
            "expert": "agent",
            **_meta(r, tid, tool_names),
        }
        yield {"done": True, **_meta(r, tid, tool_names)}
    except asyncio.TimeoutError:
        yield {
            "degraded": True,
            "t": "处理超时。请重试，或改用「预约」页办理。",
            **_meta(r, tid, tool_names),
        }
        yield {"done": True}
    except Exception as e:
        yield {
            "degraded": True,
            "t": scrub_assistant_text(
                f"助手调用失败，已降级。请改用预约/门禁菜单。原因：{e}"
            ),
            **_meta(r, tid, tool_names),
        }
        yield {"done": True}


def run_assistant(
    user_id: int,
    message: str,
    thread_id: str | None = None,
    role: str = "student",
) -> dict:
    r = normalize_role(role)
    tool_names = tool_names_for_role(r)
    tid = resolve_thread_id(user_id, thread_id)
    if not llm_configured():
        return {
            "degraded": True,
            "reply": "助手暂不可用（未配置大模型密钥）。请使用「预约管理 / 模拟门禁」完成演示。",
            "user_id": user_id,
            **_meta(r, tid, tool_names),
        }

    try:
        from utils.text_clean import scrub_assistant_text as _scrub

        fast = _try_fast_booking_reply(user_id, message)
        if fast:
            reply = _scrub(fast)
            _persist_chat_pair(
                user_id=user_id,
                thread_id=tid,
                user_text=message,
                assistant_text=reply,
            )
            return {
                "degraded": False,
                "reply": reply,
                "user_id": user_id,
                "expert": "agent",
                "fast_path": True,
                "memory_backend": "langgraph.MemorySaver",
                **_meta(r, tid, tool_names),
            }

        app = get_lab_assistant_graph(user_id, role=r)
        result = app.invoke(
            initial_agent_state(user_id, message),
            config=thread_config(user_id, thread_id),
        )
        messages = result.get("messages") or []
        reply = ""
        for m in reversed(messages):
            if isinstance(m, AIMessage) and m.content and not m.tool_calls:
                reply = m.content if isinstance(m.content, str) else str(m.content)
                break
            if isinstance(m, AIMessage) and m.content:
                reply = m.content if isinstance(m.content, str) else str(m.content)
                break
        if not reply:
            reply = "已处理，请查看是否还需要补充信息。"
        return {
            "degraded": False,
            "reply": _scrub(reply),
            "user_id": user_id,
            "expert": "agent",
            "memory_backend": "langgraph.MemorySaver",
            **_meta(r, tid, tool_names),
        }
    except Exception as e:
        return {
            "degraded": True,
            "reply": f"助手调用失败，已降级。请改用预约/门禁菜单。原因：{e}",
            "user_id": user_id,
            **_meta(r, tid, tool_names),
            "error": traceback.format_exc() if os.getenv("AGENT_DEBUG") else str(e),
        }

