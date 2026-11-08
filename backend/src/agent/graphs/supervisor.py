"""主管 + 多专家子环（LangGraph）。

主管只路由：advisor | booking | approval | schedule | FINISH
专家节点内部跑短工具环（agent↔tools），工具集裁短防串台。
审批/教务仅挂在管理图。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Annotated, Any, Callable, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.grounding import (
    GROUNDING_TOOLS,
    WRITE_TOOLS,
    ground_expert_reply,
    is_confirm_utterance,
    is_vague_book_utterance,
    parse_tool_payload,
    try_auto_confirm_pending,
)
from agent.tools.lab_tools import (
    _get_pending,
    build_advisor_tools,
    build_approval_tools,
    build_booking_tools,
    build_schedule_tools,
)

# 进程内短期记忆：同 thread_id 多轮 messages 可续；重启清空
_CHECKPOINTER = MemorySaver()

ExpertName = Literal["advisor", "booking", "approval", "schedule"]

# 防「同专家反复答 → 前端拼出重复话」：复合句最多再转一跳
MAX_HOPS = 3
# 换档需 cancel_draft → search/pick → 预检，留给 Agent 多一轮自纠
MAX_TOOL_ROUNDS = 5

STUDENT_TEACHER_EXPERTS: tuple[ExpertName, ...] = ("advisor", "booking")
ADMIN_EXPERTS: tuple[ExpertName, ...] = (
    "advisor",
    "booking",
    "approval",
    "schedule",
)

EXPERT_PROMPTS: dict[str, str] = {
    "advisor": (
        "你是顾问专家。回答制度、安全须知、开放规则、联系人、实验室名录、进不去诊断；"
        "问「有哪些实验室/搜索某实验室名称」先调 search_labs（库内名录），不要用 search_lab_docs 代替；"
        "问规章/安全条文先调 search_lab_docs，文末写「依据：[序号] source=…」；"
        "进不去/刷不开先调 access_help，用实验室名称解释对错门，禁止向用户报设备号/door_id。"
        "对用户只说自然语言，禁止 Markdown 星号加粗、列表符号堆砌；不要提「是否审批/need_approve」。"
        "不要创建预约、不要审批、不要改排课。"
    ),
    "booking": (
        "你是办理专家。负责查空闲、本人预约、签须知、领码、取消。"
        "【少问多办·确认门两轮】"
        "第1轮：选定方案并 create_reservation(confirm=false) 或 pick_free_slot 预检成功后，一句话复述请确认；"
        "第2轮：用户说确认/同意/好/就这样/对/是 → 立刻只调用 create_reservation(confirm=true)，禁止再挑档。"
        "【换档/换时间/换实验室·原子编排】"
        "用户说不约这个、换成第二个、换一间、换个时间、改约下午等变更意图时："
        "必须先 cancel_draft 清空旧待确认草稿，再立刻 pick_free_slot（换一间务必带 exclude_lab_name=旧名）"
        "或 create_reservation(confirm=false) 新预检；不要只 search_labs 就结束；"
        "禁止在未 cancel_draft 时强行挑档；工具若返回 error_code=PENDING_EXISTS，按 agent_hint 先 cancel_draft 再继续，禁止把该错误复读给用户后停住。"
        "【写库真相】只有工具返回 written=true 且带预约 id 才能说「预约成功」；"
        "若 written=false / 无草稿 / 时段冲突，必须把 error/tell_user 原样告诉用户，禁止凭记忆谎称成功。"
        "预检也必须先调工具；工具失败时禁止口头假装预检成功。"
        "用户说「再约一个」（已落库后再约）：先 pick_free_slot（避开已占用），预检成功后再请确认。"
        "【意图分层】"
        "1) 只要名录/容量/用途匹配：先 search_labs（人数用 min_capacity，如「容纳30人」→ min_capacity=30），"
        "列出符合条件的实验室（含容量），问用户选哪间或哪一时段；此时不要说「预检成功/待确认」。"
        "2) 已选定实验室+时段（或用户说随便挑档）：再 pick_free_slot 或 create_reservation(confirm=false) 做时段预检。"
        "3) 用户确认后：create_reservation(confirm=true) 落库。"
        "【上下文】短答「随便/都行/你定」=从上一轮已列实验室中任选并立刻挑档；若有旧草稿先 cancel_draft。"
        "用户说「第二个/第N个」：按上一轮 search_labs 列表序号取实验室名，cancel_draft（如有草稿）后用 prefer_lab_name 或 lab_id 预检。"
        "换时间且实验室不变：cancel_draft 后直接 create_reservation(confirm=false, day_offset+start_hm/end_hm, lab_id)，不要只 search_labs 就停。"
        "模糊预约且无容量/用途约束：优先只调 pick_free_slot 一次。"
        "用户说了用途：search_labs 按关键词匹配，再挑档预检。"
        "明确实验室+时段（如「嵌入式，明天下午2-4点」）：有 lab 名就 search_labs 取 id 后立刻 create_reservation 预检，不要只列名录就结束。"
        "明确「明天下午14-16」：day_offset=1,start_hm=14:00,end_hm=16:00 + lab_id 预检；若有旧草稿先 cancel_draft。"
        "【取消·同样两轮】用户说全部取消：必须先 cancel_reservation(cancel_all_active=true, confirm=false) 预检，"
        "只复述实验室+时段并问一次确认；禁止未调工具就说「正在取消/已取消」。"
        "禁止手填 1,2,3 等序号当预约 id。"
        "第2轮用户确认/对/是/好 → 立刻 cancel_reservation(cancel_all_active=true, confirm=true)"
        "（必须带 cancel_all_active=true，防止草稿丢失后空跑）。"
        "【取消真相】只有工具 written=true 且 remaining_active_count=0 才能说「列表为空」；"
        "若 remaining_active_count>0 必须照实说还剩几条，禁止谎称已全部取消。"
        "取消后应用 tell_user 原文回复；不要凭聊天记忆编造成功。"
        "用户问「刚才取消了什么/取消的是哪间」：必须先 list_my_reservations，"
        "用 history/recent_cancelled 回答；若上一轮助手已说「已成功取消」，禁止再说「只是预检还没取消」。"
        "【时长】单次预约最长 2 小时；用户要约更久时，说明可分段续约（下一段不冲突再约），不要一次开超 2 小时。"
        "对用户只说实验室名与时段；禁止设备号、是否审批、Markdown 星号。"
        "不要改排课、不要审批别人的单；不要声称能直接开门。"
    ),
    "approval": (
        "你是审批专家。只处理待审列表、规则闸门、通过/驳回、可信工号白名单。"
        "规则未过须用 apply_reservation_decision；禁止口头谎称已全部自动通过。"
        "不要给学生乱约、不要改排课占档。"
    ),
    "schedule": (
        "你是教务专家。只查询/添加临时排课占档；大批量引导去「排课管理」Excel 导入。"
        "添加占档前先向用户复述影响，用户确认后再调用写库工具。"
        "不要批预约、不要替用户领通行码。"
    ),
}


class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    user_id: int
    next: str
    hop_count: int
    last_expert: str


def _last_ai_text(messages: list) -> str:
    for m in reversed(messages or []):
        if isinstance(m, AIMessage) and m.content and not (m.tool_calls or []):
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def _last_human_text(messages: list) -> str:
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            return m.content if isinstance(m.content, str) else str(m.content or "")
    return ""


def _ai_text_before_last_human(messages: list) -> str:
    """上一轮助手可见正文（在本轮用户话之前），供短答承接上下文。"""
    seen_human = False
    for m in reversed(messages or []):
        if isinstance(m, HumanMessage):
            if not seen_human:
                seen_human = True
                continue
            break
        if not seen_human:
            continue
        if isinstance(m, AIMessage) and m.content and not (m.tool_calls or []):
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def _window_messages(messages: list, limit: int = 24) -> list:
    """截断历史：保住本轮 Human，并尽量带上上一轮 AI 正文。"""
    msgs = list(messages or [])
    if len(msgs) <= limit:
        return msgs
    tail = msgs[-limit:]
    if _ai_text_before_last_human(tail):
        return tail
    prior = _ai_text_before_last_human(msgs)
    if not prior:
        return tail
    out = list(tail)
    for i in range(len(out) - 1, -1, -1):
        if isinstance(out[i], HumanMessage):
            out.insert(i, AIMessage(content=prior))
            return out
    out.insert(0, AIMessage(content=prior))
    return out


def _parse_next(text: str, allowed: set[str]) -> str:
    raw = (text or "").strip()
    try:
        # 容忍模型外包 ```json
        m = re.search(r"\{[^{}]*\}", raw, re.S)
        obj = json.loads(m.group(0) if m else raw)
        nxt = str(obj.get("next", "")).strip().lower()
    except Exception:
        nxt = ""
        low = raw.lower()
        for name in list(allowed) + ["finish"]:
            if re.search(rf"\b{name}\b", low):
                nxt = name
                break
    if nxt == "finish":
        return "FINISH"
    if nxt in allowed:
        return nxt
    return "FINISH"


def _run_expert_tool_loop(
    *,
    llm_factory: Callable[[], Any],
    tools: list,
    system: str,
    messages: list,
) -> AIMessage:
    """专家内部短环：模型 ↔ Tool，最多 MAX_TOOL_ROUNDS 轮。

    结束后用工具 JSON 硬校验/覆盖对用户正文，防止「口头成功、库未写」。
    """
    anti_hallucination = (
        "\n【防幻觉硬约束】预约/取消/领码等写库结果以工具 JSON 为准；"
        "禁止在未收到 written=true 时说成功；禁止在 remaining_active_count>0 时说列表为空；"
        "有 tell_user 字段时优先复述该字段原文；"
        "若工具返回 error_code=PENDING_EXISTS，先 cancel_draft 再继续办理，禁止复读该错误后停住。"
    )
    llm = llm_factory().bind_tools(tools)
    tool_map = {t.name: t for t in tools}
    # 截断历史但保住「上一轮 AI + 本轮用户」，避免短答丢上下文
    hist = _window_messages(messages, 24)
    msgs: list = [SystemMessage(content=system + anti_hallucination)] + hist
    last: AIMessage | None = None
    tool_events: list[tuple[str, dict]] = []
    user_text = _last_human_text(messages)

    def _format_search_labs(payload: dict) -> str:
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        if not items:
            return "当前没有符合条件的开放实验室。可以换个关键词，或说明人数/用途再帮你找。"
        lines = []
        for i, it in enumerate(items[:12], 1):
            if not isinstance(it, dict):
                continue
            name_ = str(it.get("name") or "实验室")
            loc = str(it.get("location") or "")
            cap = it.get("capacity")
            extra = f"，可容纳{cap}人" if cap is not None else ""
            place = f"（{loc}）" if loc else ""
            lines.append(f"{i}. {name_}{place}{extra}")
        body = "\n".join(lines)
        return (
            f"当前开放中的实验室有：\n{body}\n"
            "请问预约哪一间？也可以说用途或人数，我帮你筛选。"
        )

    def _finish_from_tools() -> AIMessage | None:
        """预检/写库/名录查询：成功结果够用则早停；冲突/清草稿留给模型继续编排。"""
        if not tool_events:
            return None
        name, payload = tool_events[-1]
        err_code = str(payload.get("error_code") or payload.get("error") or "")
        # 草稿冲突 / 清草稿：禁止早停成对用户复读，让 Agent 自纠
        if name == "cancel_draft" or err_code == "PENDING_EXISTS":
            return None
        # 查名录早停：仅「纯查询」；换档/已带预约意图时留给模型继续预检
        if name == "search_labs" and isinstance(payload.get("items"), list):
            prior = [n for n, _ in tool_events]
            if "cancel_draft" in prior:
                return None
            if any(
                str(p.get("error_code") or "") == "PENDING_EXISTS" for _, p in tool_events
            ):
                return None
            ut = user_text or ""
            bookish = bool(
                re.search(r"预约|预检|订一|约一|换成|换一|改成|改约|换个时间|换时段", ut)
            ) and bool(
                re.search(
                    r"\d|明天|后天|今天|上午|下午|晚上|点|时|分|随便",
                    ut,
                )
            )
            if bookish:
                return None
            return AIMessage(content=_format_search_labs(payload))
        if name not in GROUNDING_TOOLS:
            return None
        # 仅成功预检 / 成功写库 / 明确失败写库（非 PENDING）才早停
        ok = payload.get("ok")
        done = bool(
            (payload.get("needs_confirm") and ok is not False)
            or payload.get("written") is True
            or (
                payload.get("must_tell_user")
                and err_code != "PENDING_EXISTS"
                and ok is False
            )
        )
        if not done:
            return None
        grounded = ground_expert_reply("", tool_events, user_text=user_text)
        if grounded:
            return AIMessage(content=grounded)
        # 勿回退到 summary（常含给模型的内部指令 / 工具名）
        tell = payload.get("tell_user") or payload.get("error")
        if isinstance(tell, str) and tell.strip():
            return AIMessage(content=tell.strip())
        return None

    import logging
    import time as _time

    _log = logging.getLogger("agent.booking")
    for round_i in range(MAX_TOOL_ROUNDS):
        t0 = _time.perf_counter()
        resp = llm.invoke(msgs)
        _log.info(
            "expert_llm_round=%s elapsed=%.2fs tools_so_far=%s",
            round_i + 1,
            _time.perf_counter() - t0,
            [n for n, _ in tool_events],
        )
        last = resp if isinstance(resp, AIMessage) else AIMessage(content=str(resp))
        msgs.append(last)
        calls = getattr(last, "tool_calls", None) or []
        if not calls:
            raw = last.content if isinstance(last.content, str) else str(last.content or "")
            grounded = ground_expert_reply(
                raw, tool_events, user_text=user_text
            )
            if grounded != raw:
                return AIMessage(content=grounded)
            # 模型偶发空正文：用工具事实兜底，避免「已处理，请补充」
            if not (raw or "").strip() and tool_events:
                early = _finish_from_tools()
                if early is not None:
                    return early
                fallback = ground_expert_reply("", tool_events, user_text=user_text)
                if fallback:
                    return AIMessage(content=fallback)
                name, payload = tool_events[-1]
                if name == "search_labs" and isinstance(payload.get("items"), list):
                    return AIMessage(content=_format_search_labs(payload))
            return last
        round_facts: list[str] = []
        # 同轮并行时：cancel_draft 必须先执行，否则会清掉刚写入的新预检草稿
        def _tool_call_priority(call: Any) -> int:
            n = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
            if n == "cancel_draft":
                return 0
            if n in ("search_labs", "list_my_reservations", "search_lab_docs", "access_help"):
                return 1
            return 2

        ordered_calls = sorted(list(calls), key=_tool_call_priority)
        for call in ordered_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", "")
            args = (
                call.get("args", {})
                if isinstance(call, dict)
                else getattr(call, "args", {}) or {}
            )
            call_id = (
                call.get("id", name)
                if isinstance(call, dict)
                else getattr(call, "id", name)
            )
            tool = tool_map.get(name)
            if tool is None:
                out = json.dumps(
                    {"ok": False, "error": f"本专家无工具 {name}"},
                    ensure_ascii=False,
                )
            else:
                try:
                    out = tool.invoke(args)
                except Exception as e:
                    out = json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)
            if not isinstance(out, str):
                out = json.dumps(out, ensure_ascii=False)
            payload = parse_tool_payload(out) or {"ok": False, "error": "工具返回非 JSON"}
            tool_events.append((str(name or ""), payload))
            if name in GROUNDING_TOOLS or name == "cancel_draft":
                fact = {
                    "tool": name,
                    "ok": payload.get("ok"),
                    "written": payload.get("written"),
                    "needs_confirm": payload.get("needs_confirm"),
                    "cleared": payload.get("cleared"),
                    "error_code": payload.get("error_code"),
                    "empty": payload.get("empty"),
                    "cancelled_count": payload.get("cancelled_count"),
                    "remaining_active_count": payload.get("remaining_active_count"),
                    "active_count": payload.get("active_count"),
                    "id": payload.get("id"),
                    "lab_name": payload.get("lab_name"),
                    "start_time": payload.get("start_time"),
                    "end_time": payload.get("end_time"),
                    # 事实卡只给模型：优先 tell_user，勿把含工具名的 summary 当对用户话术
                    "tell_user": payload.get("tell_user"),
                    "message": payload.get("message"),
                    "agent_hint": payload.get("agent_hint"),
                    "error": payload.get("error"),
                }
                round_facts.append(json.dumps(fact, ensure_ascii=False))
            msgs.append(ToolMessage(content=out, tool_call_id=call_id))
        if round_facts:
            msgs.append(
                SystemMessage(
                    content=(
                        "【本轮工具事实·对用户回复必须遵守】"
                        + " | ".join(round_facts)
                        + "。若含 tell_user，下一句请直接采用其含义，禁止相反表述。"
                    )
                )
            )
        early = _finish_from_tools()
        if early is not None:
            return early
    raw = ""
    if last is not None:
        raw = last.content if isinstance(last.content, str) else str(last.content or "")
    grounded = ground_expert_reply(
        raw, tool_events, user_text=_last_human_text(messages)
    )
    if grounded:
        return AIMessage(content=grounded)
    return last or AIMessage(content="专家处理超时，请简化问题重试。")


def build_supervisor_graph(
    user_id: int,
    *,
    experts: tuple[ExpertName, ...],
    llm_factory: Callable[[], Any],
    role_label: str,
) -> Any:
    """
    编译主管图。
    experts：学生/老师仅 advisor+booking；管理员四专家齐全。
    """
    allowed = set(experts)
    builders: dict[str, Callable[[int], list]] = {
        "advisor": build_advisor_tools,
        "booking": build_booking_tools,
        "approval": build_approval_tools,
        "schedule": build_schedule_tools,
    }
    toolsets = {name: builders[name](user_id) for name in experts}

    options = " | ".join(list(experts) + ["FINISH"])
    supervisor_system = f"""你是校园实验室助手的主管（{role_label}）。
根据对话决定下一步交给哪个专家，或结束。
只输出一行 JSON，不要解释，格式：{{"next":"专家名或FINISH"}}
可选 next：{options}

分工：
- advisor：制度/安全/找谁/SOP/进不去；也可搜实验室名录（search_labs），不写库
- booking：查空闲/搜实验室、本人预约、通行码、签须知领码取消
- approval：待审、规则审、通过驳回（仅管理）
- schedule：排课占档查询/临时添加（仅管理）

路由提示：
- 「搜索/有哪些/叫什么名的实验室」→ booking 或 advisor 均可，优先 booking
- 「安全须知/禁止事项/找谁审批」→ advisor
- 「预约/取消/领码/签须知」→ booking
- 「确认/好/行/是」等短确认 → booking（落库确认门）
- 「随便预约/帮我约一个实验室」→ booking

硬规则：
1. 单一意图只派一个专家，专家已给出可展示答复后必须 FINISH，禁止再派同一专家。
2. 仅复合句才两跳：例如先 advisor 再 booking；第二跳后立刻 FINISH。
3. 禁止循环派单；不要为了「再说一遍」继续路由。
"""

    def supervisor_node(state: SupervisorState):
        hops = int(state.get("hop_count") or 0)
        last_expert = (state.get("last_expert") or "").strip()
        uid = int(state.get("user_id") or 0)
        human = _last_human_text(list(state.get("messages") or []))
        # 有待确认草稿 + 用户短确认 → 必须进 booking，禁止 FINISH/顾问抢走
        if (
            "booking" in allowed
            and is_confirm_utterance(human)
            and _get_pending(uid)
        ):
            return {"next": "booking"}
        if "booking" in allowed and is_vague_book_utterance(human):
            return {"next": "booking"}
        # 专家已答过且有正文 → 默认收束，避免重复生成
        if hops >= 1 and _last_ai_text(list(state.get("messages") or [])):
            # 允许「顾问→办理」这一跳复合；已两跳或只需单专家则结束
            if hops >= 2 or last_expert == "booking" or last_expert == "approval":
                return {"next": "FINISH"}
        if hops >= MAX_HOPS:
            return {"next": "FINISH"}

        llm = llm_factory()
        resp = llm.invoke(
            [SystemMessage(content=supervisor_system)]
            + list(state["messages"])[-12:]
        )
        text = resp.content if isinstance(resp.content, str) else str(resp.content)
        nxt = _parse_next(text, allowed)
        if is_confirm_utterance(human) and "booking" in allowed:
            nxt = "booking"
        if is_vague_book_utterance(human) and "booking" in allowed:
            nxt = "booking"
        # 禁止连派同一专家（主因：回答重复拼接）
        if nxt != "FINISH" and nxt == last_expert:
            return {"next": "FINISH"}
        # 已有办理/审批答复时不要再开新专家兜圈子
        if hops >= 1 and nxt == last_expert:
            return {"next": "FINISH"}
        return {"next": nxt}

    def route_after_supervisor(state: SupervisorState):
        nxt = state.get("next") or "FINISH"
        if nxt == "FINISH" or nxt not in allowed:
            return END
        return nxt

    def make_expert_node(name: ExpertName):
        tools = toolsets[name]
        base_system = EXPERT_PROMPTS[name]

        def expert_node(state: SupervisorState):
            now = datetime.now()
            clock = (
                f"\n【系统当前时间】{now.strftime('%Y-%m-%d %H:%M:%S')}；"
                f"今天={now.strftime('%Y-%m-%d')}；"
                f"明天={(now + timedelta(days=1)).strftime('%Y-%m-%d')}；"
                f"后天={(now + timedelta(days=2)).strftime('%Y-%m-%d')}。"
                "相对日期必须按此推算，预约时间写成 YYYY-MM-DD HH:MM:SS。"
            )
            msgs = list(state["messages"])
            # 办理专家：确认 / 纯随便直办（与入口 fast_path 一致）；带用途仍走工具环
            if name == "booking":
                uid = int(state.get("user_id") or 0)
                human = _last_human_text(msgs)
                auto = try_auto_confirm_pending(uid, human)
                if auto:
                    return {
                        "messages": [AIMessage(content=auto)],
                        "hop_count": int(state.get("hop_count") or 0) + 1,
                        "last_expert": name,
                        "next": "",
                    }
            ai = _run_expert_tool_loop(
                llm_factory=llm_factory,
                tools=tools,
                system=base_system + clock,
                messages=msgs,
            )
            return {
                "messages": [ai],
                "hop_count": int(state.get("hop_count") or 0) + 1,
                "last_expert": name,
                "next": "",
            }

        return expert_node

    g = StateGraph(SupervisorState)
    g.add_node("supervisor", supervisor_node)
    for name in experts:
        g.add_node(name, make_expert_node(name))

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {name: name for name in experts} | {END: END},
    )
    for name in experts:
        g.add_edge(name, "supervisor")

    return g.compile(checkpointer=_CHECKPOINTER)


def initial_supervisor_state(user_id: int, message: str) -> dict:
    """每轮只追加本句用户消息；历史由 MemorySaver 按 thread_id 合并。"""
    return {
        "messages": [HumanMessage(content=message)],
        "user_id": user_id,
        "next": "",
        "hop_count": 0,
        "last_expert": "",
    }


def resolve_thread_id(user_id: int, thread_id: str | None) -> str:
    tid = (thread_id or "").strip() or "default"
    return f"u{user_id}:{tid}"


def thread_config(user_id: int, thread_id: str | None) -> dict:
    return {"configurable": {"thread_id": resolve_thread_id(user_id, thread_id)}}


# 流式时只推专家节点正文，不推主管 JSON
STREAMABLE_NODES = frozenset({"advisor", "booking", "approval", "schedule", "agent"})
