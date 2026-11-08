"""写库类回复防幻觉：以 Tool 返回为准，必要时覆盖模型正文。"""
from __future__ import annotations

import json
import re
from typing import Any

# 写库 / 确认门相关工具（含预检挑档）
WRITE_TOOLS = frozenset(
    {
        "create_reservation",
        "cancel_reservation",
        "ack_safety",
        "issue_passcode",
        "apply_reservation_decision",
        "auto_process_pending",
        "add_schedule_block",
    }
)
# 预检也会写待确认草稿，必须纳入 grounding，否则会误杀「随便预约」
PRECHECK_TOOLS = frozenset({"pick_free_slot", "create_reservation"})
GROUNDING_TOOLS = WRITE_TOOLS | PRECHECK_TOOLS | {"list_my_reservations"}

# 用户短确认（命中后应由系统直接 confirm=true，不依赖模型再调工具）
_CONFIRM_UTTERANCE = re.compile(
    r"^\s*(确认|同意|好的?|行|是的?|可以|没问题|就这样|办吧|预约吧|"
    r"取消吧|全部取消吧|ok|okay|yes|y|嗯|中)\s*[!！。.~～]*\s*$",
    re.I,
)
# 模糊预约意图（仅用于路由提示等；不再用于关键词直办 pick）
# 「预约第二个 随便时间」不得命中：须避开夹带序号/指定实验室的句子
_VAGUE_BOOK = re.compile(
    r"(随便|随机|任意).{0,8}预约|"
    r"^\s*(随便|任意|都行|都可以|随便一间|随便一个|哪个都行|哪间都行|你定|帮我挑)\s*[!！。.~～]*\s*$",
    re.I,
)
_ORDINAL_PICK = re.compile(r"第?\s*[一二三四五六七八九十\d]+\s*个|第\s*\d+", re.I)
# 「我要做滴管，帮我预约」等：有用途，必须进模型，不能当随便约
_PURPOSE_HINT = re.compile(
    r"(要做|想做|做一下|用途|用来|做.{0,8}实验|化学|生物|滴管)",
    re.I,
)

_SUCCESS_CLAIM = re.compile(
    r"(已成功取消|成功取消|已全部取消|已成功预约|预约成功|已写入预约|提交成功|"
    r"预约列表为空|当前没有有效预约|已取消全部|取消成功)",
    re.I,
)
_BOOK_SUCCESS = re.compile(r"(已成功预约|预约成功|已写入预约|提交成功)", re.I)
_CANCEL_SUCCESS = re.compile(r"(已成功取消|成功取消|已全部取消|取消成功|预约列表为空)", re.I)
_EMPTY_LIST = re.compile(r"(预约列表为空|当前没有有效预约|无任何有效预约)", re.I)
# 仅拦截「空口声称已预检/待确认」；普通「请确认选哪间」不要误杀
_PRECHECK_CLAIM = re.compile(
    r"(预检成功|预检通过|当前为待确认|待确认状态|已为您预检)",
    re.I,
)


def is_confirm_utterance(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 24:
        return False
    return bool(_CONFIRM_UTTERANCE.match(t))


def is_vague_book_utterance(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(t) > 40:
        return False
    # 带用途/场景或「第二个」等序号 → 必须靠 Agent 读上下文
    if _PURPOSE_HINT.search(t) or _ORDINAL_PICK.search(t):
        return False
    # 太具体的时段
    if re.search(r"\d{1,2}\s*[:：点]\s*\d{0,2}|\d{1,2}\s*-\s*\d{1,2}", t):
        return False
    return bool(_VAGUE_BOOK.search(t))


def parse_tool_payload(content: Any) -> dict[str, Any] | None:
    if content is None:
        return None
    if isinstance(content, dict):
        return content
    text = content if isinstance(content, str) else str(content)
    text = text.strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


# 工具 summary / agent_hint 常夹带给模型的内部指令，禁止原样给用户
_INTERNAL_HINT = re.compile(
    r"(请向用户|对用户只|不要报|不要提|等待明确|立刻\s*\w+\(|"
    r"confirm\s*=\s*true|cancel_reservation\(|create_reservation\(|"
    r"pick_free_slot\(|agent_hint|禁止)",
    re.I,
)


def _pick_tell(payload: dict[str, Any]) -> str:
    """优先 tell_user；summary 仅在不含内部指令时采用。"""
    for key in ("tell_user", "summary", "message", "error"):
        val = payload.get(key)
        if not isinstance(val, str) or not val.strip():
            continue
        text = val.strip()
        if key == "summary" and _INTERNAL_HINT.search(text):
            continue
        if key != "tell_user" and _INTERNAL_HINT.search(text):
            continue
        return text
    return ""


def _format_cancel_confirm(payload: dict[str, Any]) -> str:
    """取消预检：只复述实验室与时段，请确认取消（禁止套用「正式预约」话术）。"""
    tell = _pick_tell(payload)
    if tell and "正式预约" not in tell and "cancel_reservation" not in tell:
        base = tell
        if "请确认" not in base and "确认」" not in base:
            base = f"{base} 请回复「确认」以取消。"
        return base

    reservations = payload.get("reservations") or []
    lines: list[str] = []
    if isinstance(reservations, list):
        for item in reservations[:8]:
            if not isinstance(item, dict):
                continue
            lab = item.get("lab_name") or "实验室"
            st = item.get("start_time") or ""
            et = item.get("end_time") or ""
            lines.append(f"· {lab}，{st} 至 {et}")
    n = int(payload.get("count") or len(lines) or 0)
    head = f"将取消 {n} 个预约并作废相关通行码。"
    if lines:
        head = f"{head}\n" + "\n".join(lines)
    return f"{head}\n请回复「确认」以取消。"


def _format_needs_confirm(name: str, payload: dict[str, Any]) -> str:
    # 必须先按工具名分支：cancel 也带 needs_confirm，不能走预约话术
    if name == "cancel_reservation":
        return _format_cancel_confirm(payload)
    if name == "ack_safety":
        tell = _pick_tell(payload) or "请确认已阅读安全须知。"
        if "请确认" not in tell and "确认」" not in tell:
            tell = f"{tell} 请回复「确认」以签署。"
        return tell
    if name == "issue_passcode":
        tell = _pick_tell(payload) or "将为该预约发放通行码。"
        if "请确认" not in tell and "确认」" not in tell:
            tell = f"{tell} 请回复「确认」以领码。"
        return tell

    tell = _pick_tell(payload)
    lab = payload.get("lab_name") or ""
    loc = payload.get("location") or ""
    st = payload.get("start_time") or ""
    et = payload.get("end_time") or ""
    if name in ("create_reservation", "pick_free_slot") or payload.get("needs_confirm"):
        place = f"{lab}（{loc}）" if lab and loc else (lab or loc or "实验室")
        base = tell or f"已为您预检成功：{place}，{st} 至 {et}，当前为待确认状态。"
        # 去掉误掺的取消/工具指令尾巴
        if "正式预约" in base and "取消" in base:
            base = re.split(r"请回复「确认」", base, maxsplit=1)[0].strip()
            base = f"{base} 请回复「确认」以正式预约。"
        elif "请确认" not in base and "确认」" not in base:
            base = f"{base} 请回复「确认」以正式预约。"
        return base
    return tell or "请确认后我再继续办理。"


def _format_write_result(name: str, payload: dict[str, Any]) -> str:
    tell = _pick_tell(payload)
    if tell:
        return tell
    if payload.get("written") is True:
        if name == "create_reservation":
            return (
                f"已写入预约表：{payload.get('lab_name') or ''} "
                f"{payload.get('start_time') or ''} 至 {payload.get('end_time') or ''}，"
                f"状态 {payload.get('status') or ''}。"
            ).strip()
        if name == "cancel_reservation":
            n = int(payload.get("cancelled_count") or 0)
            rem = int(payload.get("remaining_active_count") or 0)
            if rem:
                return f"已取消 {n} 个，但仍剩 {rem} 条有效预约，列表并未清空。"
            return f"已成功取消 {n} 个预约，当前有效预约列表已空。"
        return "操作已完成。"
    err = payload.get("error") or payload.get("message") or "操作未成功"
    return f"{err}。请勿理解为已办理成功。"


def _is_pending_conflict(payload: dict[str, Any]) -> bool:
    code = str(payload.get("error_code") or payload.get("error") or "")
    return code == "PENDING_EXISTS"


def _last_precheck(
    tool_events: list[tuple[str, dict[str, Any]]],
) -> tuple[str, dict[str, Any]] | None:
    for name, payload in reversed(tool_events):
        if name not in PRECHECK_TOOLS:
            continue
        # 草稿冲突交给 Agent 自纠，不当成功预检话术
        if _is_pending_conflict(payload):
            continue
        if not payload.get("needs_confirm"):
            continue
        # 仅成功预检（ok 不为 false）才生成「请确认」话术
        if payload.get("ok") is False:
            continue
        if payload.get("ok") or payload.get("must_tell_user") or payload.get("tell_user"):
            return name, payload
    return None


def ground_expert_reply(
    ai_text: str,
    tool_events: list[tuple[str, dict[str, Any]]],
    *,
    user_text: str = "",
) -> str:
    """用最近一次写库/预检工具结果约束对用户可见正文。"""
    text = (ai_text or "").strip()
    writes = [(n, p) for n, p in tool_events if n in WRITE_TOOLS]
    lists = [(n, p) for n, p in tool_events if n == "list_my_reservations"]
    precheck = _last_precheck(tool_events)

    # 0) 真实预检（含 pick_free_slot）：以工具结果为准生成确认话术
    if precheck:
        name, payload = precheck
        grounded = _format_needs_confirm(name, payload)
        if _BOOK_SUCCESS.search(text) or _CANCEL_SUCCESS.search(text):
            return grounded
        # 模型胡写也可以，但必须带确认；优先用工具文案更稳
        return grounded

    # 1) 本轮有写库工具：以最后一次写库结果覆盖成功/失败话术
    if writes:
        name, payload = writes[-1]
        if payload.get("needs_confirm"):
            grounded = _format_needs_confirm(name, payload)
            if _SUCCESS_CLAIM.search(text) and not payload.get("written"):
                return grounded
            if _BOOK_SUCCESS.search(text) or _CANCEL_SUCCESS.search(text):
                return grounded
            return text or grounded
        grounded = _format_write_result(name, payload)
        if name == "cancel_reservation":
            if payload.get("written") and int(payload.get("remaining_active_count") or 0) > 0:
                return grounded
            if payload.get("empty") or int(payload.get("remaining_active_count") or 0) == 0:
                if payload.get("written") or payload.get("empty"):
                    return grounded
        if payload.get("must_tell_user") or payload.get("written") is not None or payload.get(
            "ok"
        ) is False:
            return grounded
        if _SUCCESS_CLAIM.search(text):
            return grounded
        return text or grounded

    # 2) 本轮只查了列表：用 active_count 约束「列表为空」类说法
    if lists:
        _, payload = lists[-1]
        active_count = payload.get("active_count")
        if active_count is None and isinstance(payload.get("active"), list):
            active_count = len(payload["active"])
        if active_count is None and isinstance(payload.get("active_ids"), list):
            active_count = len(payload["active_ids"])
        if isinstance(active_count, int):
            if active_count > 0 and _EMPTY_LIST.search(text):
                active = payload.get("active") or []
                lines = []
                for item in active[:8]:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"· {item.get('lab_name') or '实验室'}，"
                        f"{item.get('start_time')} 至 {item.get('end_time')}"
                        f"（{item.get('status')}）"
                    )
                body = "\n".join(lines) if lines else f"仍有 {active_count} 条有效预约。"
                return f"当前仍有 {active_count} 条有效预约，列表并未清空：\n{body}"
            if active_count == 0 and _CANCEL_SUCCESS.search(text) and "取消" in text:
                return "当前有效预约列表为空。若需要预约，请告诉我时间偏好。"

    # 3) 本轮没有预检/写库工具，却空口说「已预检成功」→ 打回（不装成功）
    if _PRECHECK_CLAIM.search(text):
        if is_vague_book_utterance(user_text):
            return (
                "我还没有查到空闲档。请再说一次「随便约一间」，"
                "或直接点名实验室与时段。"
            )
        # 保留模型其它有用说明时，只替换成功幻觉句，避免整段变成吓人闸门话
        return (
            "我还没有完成时段预检，不能说已经约好。"
            "请补充想要的日期/时段，或说「随便挑一档」，我先查空闲再请你确认。"
        )
    if _SUCCESS_CLAIM.search(text) or (is_confirm_utterance(user_text) and not text):
        return (
            "系统尚未完成写库，刚才的成功说法无效。"
            "若你在确认预约/取消，请再说一次「确认」；若草稿已丢失，请重新说要约哪天哪个实验室。"
        )
    return text


_ASK_WHAT_CANCELLED = re.compile(
    r"(刚才|刚刚).{0,8}(取消|撤销).{0,6}(什么|哪|啥)|"
    r"(取消|撤销).{0,6}(了什么|的是什么|哪一|哪次)|"
    r"我取消了什么",
    re.I,
)


def try_answer_recent_cancel(user_id: int, user_text: str) -> str | None:
    """用户追问「刚才取消了什么」：用最近成功取消事实作答，禁止模型说成「只是预检」。"""
    if not _ASK_WHAT_CANCELLED.search(user_text or ""):
        return None
    from agent.tools.lab_tools import format_last_cancel_fact

    return format_last_cancel_fact(int(user_id))


def try_auto_confirm_pending(user_id: int, user_text: str) -> str | None:
    """有待确认草稿且用户说确认/行/好 → 跳过模型，直接调用对应工具落库。"""
    if not is_confirm_utterance(user_text):
        return None
    from agent.tools.lab_tools import _get_pending, build_booking_tools

    draft = _get_pending(int(user_id))
    if not draft:
        return None
    action = str(draft.get("action") or "")
    tools = {t.name: t for t in build_booking_tools(int(user_id))}
    out = None
    tool_name = ""
    try:
        if action == "create_reservation":
            tool_name = "create_reservation"
            out = tools[tool_name].invoke({"confirm": True})
        elif action == "cancel_reservation":
            tool_name = "cancel_reservation"
            out = tools[tool_name].invoke(
                {
                    "confirm": True,
                    "cancel_all_active": bool(draft.get("cancel_all_active")),
                }
            )
        elif action == "ack_safety":
            tool_name = "ack_safety"
            out = tools[tool_name].invoke(
                {
                    "reservation_id": int(draft.get("reservation_id") or 0),
                    "confirm": True,
                }
            )
        elif action == "issue_passcode":
            tool_name = "issue_passcode"
            out = tools[tool_name].invoke(
                {
                    "reservation_id": int(draft.get("reservation_id") or 0),
                    "confirm": True,
                }
            )
        else:
            return None
    except Exception as e:
        return f"确认办理失败：{e}。请稍后重试或改用预约页操作。"

    payload = parse_tool_payload(out) or {
        "ok": False,
        "written": False,
        "error": "工具无返回",
    }
    return ground_expert_reply(
        "",
        [(tool_name, payload)],
        user_text=user_text,
    ) or _pick_tell(payload) or "已处理确认请求。"


def try_auto_vague_book(user_id: int, user_text: str) -> str | None:
    """「随便预约」类话术：直接 pick_free_slot 预检，避免模型空口预检被闸门误杀。"""
    if not is_vague_book_utterance(user_text):
        return None
    from agent.tools.lab_tools import _get_pending, _set_pending, build_booking_tools

    # 再次「随便 / 换一间」：先 cancel_draft 再挑（短答「随便」也视为换档重挑）
    draft = _get_pending(int(user_id))
    replace = bool(
        draft
        and re.search(
            r"换一间|换一个|重新|再(随便)?预约|随便预约|"
            r"^\s*(随便|任意|都行|都可以|随便一间|随便一个|哪个都行|哪间都行|你定|帮我挑)\s*$",
            user_text or "",
        )
    )
    tools = {t.name: t for t in build_booking_tools(int(user_id))}
    if draft and not replace:
        return (
            f"您还有一档待确认预约："
            f"{draft.get('lab_name') or ''} {draft.get('start_time')} 至 {draft.get('end_time')}。"
            "请回复「确认」完成；若要换档，再说一次「随便」或「换一间」。"
        )
    if replace and "cancel_draft" in tools:
        try:
            tools["cancel_draft"].invoke({})
        except Exception:
            _set_pending(int(user_id), None)
    elif replace:
        _set_pending(int(user_id), None)

    try:
        out = tools["pick_free_slot"].invoke(
            {"day_offset": 1, "prefer": "any", "prefer_lab_name": "", "purpose": ""}
        )
    except Exception as e:
        return f"自动挑选失败：{e}。请改用预约页，或说明实验室与时段。"
    payload = parse_tool_payload(out) or {"ok": False, "error": "挑档无返回"}
    if not payload.get("ok"):
        # 若仍因草稿拒绝，cancel_draft 后再试
        err = str(payload.get("error_code") or payload.get("error") or "")
        if err == "PENDING_EXISTS" or "待确认" in err or "换选" in err:
            if "cancel_draft" in tools:
                try:
                    tools["cancel_draft"].invoke({})
                except Exception:
                    _set_pending(int(user_id), None)
            else:
                _set_pending(int(user_id), None)
            try:
                out = tools["pick_free_slot"].invoke(
                    {
                        "day_offset": 1,
                        "prefer": "any",
                        "prefer_lab_name": "",
                        "purpose": "",
                    }
                )
                payload = parse_tool_payload(out) or payload
            except Exception:
                pass
        if not payload.get("ok"):
            return (
                _pick_tell(payload)
                or payload.get("message")
                or payload.get("error")
                or "暂无合适空闲档，请换一天或指定实验室。"
            )
    return ground_expert_reply(
        "",
        [("pick_free_slot", payload)],
        user_text=user_text,
    )
