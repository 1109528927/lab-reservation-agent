"""
实验室预约助手 — LangGraph（4 核心 Tool + 可降级）。
百炼 OpenAI 兼容：LLM_BASE_URL + LLM_API_KEY + LLM_MODEL
"""
from __future__ import annotations

import os
import traceback
from typing import Annotated, Any, TypedDict

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.tools.lab_tools import ADMIN_TOOL_NAMES, CORE_TOOL_NAMES, build_tools_for_user


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int


def llm_configured() -> bool:
    return bool(os.getenv("LLM_API_KEY", "").strip())


def _make_llm():
    return ChatOpenAI(
        api_key=os.getenv("LLM_API_KEY", ""),
        base_url=os.getenv(
            "LLM_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        model=os.getenv("LLM_MODEL", "deepseek-v3"),
        temperature=0.2,
        streaming=True,
    )


def text_of(chunk: Any) -> str:
    """把 AIMessageChunk.content 归一成可渲染字符串。"""
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


SYSTEM_PROMPT = """你是校园实验室预约助手。
规则：
1. 帮助学生/老师查询实验室、创建本人预约、查看本人预约、查询本人通行码。
2. 学生预约提交后需管理员审核；老师预约可直接通过。
3. 缺 lab_id 或时间时先追问，不要瞎编。
4. 预约与排课冲突时根据工具返回说明，建议改期。
5. 不要声称能直接开门；通行需扫码核验。
6. 用简洁中文回答。
"""

ADMIN_SYSTEM_EXTRA = """
你当前对话对象是学校管理员。除预约助手能力外，还可查询/添加临时排课占档。
大批量排课请引导管理员使用「排课管理」页的 Excel 导入，不要逐条用工具铺整学期。
"""


_GRAPH_CACHE: dict[tuple[int, str], Any] = {}


def get_lab_assistant_graph(user_id: int, role: str = "student") -> Any:
    """同一用户、同一角色复用已编译的图，避免每次提问重新绑工具。"""
    key = (user_id, role or "student")
    graph = _GRAPH_CACHE.get(key)
    if graph is None:
        graph = build_lab_assistant_graph(user_id, role=role)
        _GRAPH_CACHE[key] = graph
    return graph


async def warmup_assistant(user_id: int, role: str = "student") -> dict:
    """
    打开助手页时调用：编译图，并向模型发一次极短请求，把连接和首包延迟提前消化掉。
    """
    if not llm_configured():
        return {"warm": False, "reason": "no_key"}
    try:
        get_lab_assistant_graph(user_id, role=role)
        llm = _make_llm().bind(max_tokens=1)
        await llm.ainvoke([HumanMessage(content="只回复一个字：好")])
        return {"warm": True}
    except Exception as e:
        return {"warm": False, "reason": str(e)}


def build_lab_assistant_graph(user_id: int, role: str = "student") -> Any:
    tools = build_tools_for_user(user_id, role=role)
    llm = _make_llm().bind_tools(tools)
    tool_node = ToolNode(tools)
    system = SYSTEM_PROMPT + (ADMIN_SYSTEM_EXTRA if role == "admin" else "")

    def agent_node(state: AgentState):
        msgs = list(state["messages"])
        if not msgs or not isinstance(msgs[0], SystemMessage):
            msgs = [SystemMessage(content=system)] + msgs
        resp = llm.invoke(msgs)
        return {"messages": [resp]}


    def should_continue(state: AgentState):
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    g = StateGraph(AgentState)
    g.add_node("agent", agent_node)
    g.add_node("tools", tool_node)
    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent", should_continue, {"tools": "tools", "end": END}
    )
    g.add_edge("tools", "agent")
    return g.compile()


async def stream_assistant(
    user_id: int,
    message: str,
    role: str = "student",
):
    """
    LangGraph astream + stream_mode=messages。
    产出 dict：{"t": 文本碎片} / {"degraded": True, "t": ...} / {"done": True}
    """
    tool_names = list(CORE_TOOL_NAMES) + (
        list(ADMIN_TOOL_NAMES) if role == "admin" else []
    )
    if not llm_configured():
        yield {
            "degraded": True,
            "t": "助手暂不可用（未配置大模型密钥）。请使用「预约管理 / 模拟门禁」完成演示。",
            "core_tools": tool_names,
        }
        yield {"done": True}
        return

    try:
        app = get_lab_assistant_graph(user_id, role=role)
        inputs = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
        }
        async for chunk, meta in app.astream(inputs, stream_mode="messages"):
            if meta.get("langgraph_node") != "agent":
                continue
            # 工具调用阶段常有空 content，只推真正的正文 token
            if getattr(chunk, "tool_call_chunks", None):
                piece = text_of(chunk)
                if not piece:
                    continue
            piece = text_of(chunk)
            if not piece:
                continue
            yield {"t": piece, "degraded": False}
        yield {"done": True, "core_tools": tool_names}
    except Exception as e:
        yield {
            "degraded": True,
            "t": f"助手调用失败，已降级。请改用预约/门禁菜单。原因：{e}",
            "core_tools": tool_names,
        }
        yield {"done": True}


def run_assistant(
    user_id: int,
    message: str,
    thread_id: str | None = None,
    role: str = "student",
) -> dict:
    tool_names = list(CORE_TOOL_NAMES) + (
        list(ADMIN_TOOL_NAMES) if role == "admin" else []
    )
    if not llm_configured():
        return {
            "degraded": True,
            "reply": "助手暂不可用（未配置大模型密钥）。请使用「预约管理 / 模拟门禁」完成演示。",
            "user_id": user_id,
            "thread_id": thread_id,
            "core_tools": tool_names,
        }

    try:
        app = get_lab_assistant_graph(user_id, role=role)
        result = app.invoke(
            {
                "messages": [HumanMessage(content=message)],
                "user_id": user_id,
            }
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
            "reply": reply,
            "user_id": user_id,
            "thread_id": thread_id,
            "core_tools": tool_names,
        }
    except Exception as e:
        return {
            "degraded": True,
            "reply": f"助手调用失败，已降级。请改用预约/门禁菜单。原因：{e}",
            "user_id": user_id,
            "thread_id": thread_id,
            "core_tools": tool_names,
            "error": traceback.format_exc() if os.getenv("AGENT_DEBUG") else str(e),
        }

