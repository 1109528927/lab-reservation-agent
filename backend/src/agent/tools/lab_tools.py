"""实验室助手 Tool。

三张角色图各自只绑定本角色工具集：
- student / teacher：核心业务 Tool（写库仍走 CRUD，按账号角色分流待审/直通）
- admin：核心 + 排课/待审/规则审批等管理 Tool

模型没有裸 SQL 通道；越权靠「图不挂工具 + CRUD 再鉴权」。
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from langchain_core.tools import StructuredTool

from config.request import SyncSessionLocal
from crud import access as access_crud
from crud import schedule as schedule_crud


CORE_TOOL_NAMES = (
    "search_labs",
    "pick_free_slot",
    "create_reservation",
    "cancel_draft",
    "list_my_reservations",
    "get_passcode",
    "search_lab_docs",
    "cancel_reservation",
    "ack_safety",
    "issue_passcode",
    "access_help",
)

# 老师与学生工具面相同；业务层按角色写 pending/approved，图级物理隔离便于答辩
TEACHER_TOOL_NAMES = CORE_TOOL_NAMES

# 用户确认前的草稿（按 user_id）；落盘避免 uvicorn reload / 多进程丢草稿导致「口头成功、库里没有」
_PENDING_WRITE: dict[int, dict] = {}
_PENDING_FILE = (
    Path(__file__).resolve().parents[3] / "data" / "agent_pending_write.json"
)
# 最近一次成功写库事实（供「刚才取消了什么」等追问，避免模型不查库却说「只是预检」）
_LAST_WRITE_FACT: dict[int, dict] = {}
_LAST_FACT_FILE = (
    Path(__file__).resolve().parents[3] / "data" / "agent_last_write_fact.json"
)


def _load_pending_store() -> dict[str, dict]:
    try:
        if _PENDING_FILE.is_file():
            raw = json.loads(_PENDING_FILE.read_text(encoding="utf-8") or "{}")
            return raw if isinstance(raw, dict) else {}
    except Exception:
        pass
    return {}


def _save_pending_store(store: dict[str, dict]) -> None:
    try:
        _PENDING_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PENDING_FILE.write_text(
            json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _get_pending(user_id: int) -> dict | None:
    mem = _PENDING_WRITE.get(user_id)
    if mem:
        return mem
    store = _load_pending_store()
    row = store.get(str(user_id))
    if isinstance(row, dict):
        _PENDING_WRITE[user_id] = row
        return row
    return None


def _set_pending(user_id: int, payload: dict | None) -> None:
    store = _load_pending_store()
    key = str(user_id)
    if payload is None:
        _PENDING_WRITE.pop(user_id, None)
        store.pop(key, None)
    else:
        _PENDING_WRITE[user_id] = payload
        store[key] = payload
    _save_pending_store(store)


def _load_last_fact_store() -> dict:
    try:
        if _LAST_FACT_FILE.is_file():
            raw = json.loads(_LAST_FACT_FILE.read_text(encoding="utf-8") or "{}")
            return raw if isinstance(raw, dict) else {}
    except Exception:
        pass
    return {}


def _save_last_fact_store(store: dict) -> None:
    try:
        _LAST_FACT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_FACT_FILE.write_text(
            json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


def _set_last_write_fact(user_id: int, fact: dict | None) -> None:
    store = _load_last_fact_store()
    key = str(user_id)
    if fact is None:
        _LAST_WRITE_FACT.pop(user_id, None)
        store.pop(key, None)
    else:
        from time import time as _time

        row = {**fact, "at": float(fact.get("at") or _time())}
        _LAST_WRITE_FACT[user_id] = row
        store[key] = row
    _save_last_fact_store(store)


def _get_last_write_fact(user_id: int) -> dict | None:
    mem = _LAST_WRITE_FACT.get(user_id)
    if mem:
        return mem
    store = _load_last_fact_store()
    row = store.get(str(user_id))
    if isinstance(row, dict):
        _LAST_WRITE_FACT[user_id] = row
        return row
    return None


def format_last_cancel_fact(user_id: int, *, max_age_sec: float = 7200) -> str | None:
    """若有未过期的成功取消事实，生成对用户说明（已落库，不是预检）。"""
    from time import time as _time

    fact = _get_last_write_fact(int(user_id))
    if not fact or fact.get("action") != "cancel":
        return None
    try:
        age = _time() - float(fact.get("at") or 0)
    except Exception:
        return None
    if age < 0 or age > max_age_sec:
        return None
    items = fact.get("items") if isinstance(fact.get("items"), list) else []
    if not items:
        return None
    lines = []
    for it in items[:8]:
        if not isinstance(it, dict):
            continue
        lines.append(
            f"· {it.get('lab_name') or '实验室'}，"
            f"{it.get('start_time') or ''} 至 {it.get('end_time') or ''}"
        )
    if not lines:
        return None
    return (
        "刚才已确认并取消成功（已写入数据库，不是预检）：\n"
        + "\n".join(lines)
    )


def _pending_exists_payload(draft: dict) -> dict:
    """有待确认草稿时的软拦截：给 Agent 的结构化错误，勿直接当最终对用户文案早停。"""
    return {
        "ok": False,
        "error_code": "PENDING_EXISTS",
        "error": "PENDING_EXISTS",
        "message": "当前有未完成的草稿，若要新建或换选请先调用 cancel_draft。",
        "agent_hint": (
            "用户要换档/换时间/换实验室/不要这笔待确认：先 cancel_draft，"
            "再 search_labs / pick_free_slot / create_reservation(confirm=false)。"
            "换一间时 pick_free_slot 请带 exclude_lab_name=旧实验室名。"
            "用户要确认当前草稿：create_reservation(confirm=true) 或对应写库工具 confirm=true。"
            "禁止把本错误原样复读给用户后停住；应继续编排工具。"
        ),
        "pending": {
            "action": draft.get("action"),
            "lab_id": draft.get("lab_id"),
            "lab_name": draft.get("lab_name"),
            "start_time": draft.get("start_time"),
            "end_time": draft.get("end_time"),
            "reservation_ids": draft.get("reservation_ids"),
        },
    }

ADMIN_TOOL_NAMES = (
    "list_schedule_blocks",
    "add_schedule_block",
    "list_pending_reservations",
    "rule_review_reservation",
    "apply_reservation_decision",
    "auto_process_pending",
    "add_trusted_employee_no",
    "list_trusted_employee_nos",
)


def _parse_dt(s: str) -> datetime:
    s = s.strip().replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(s)


def _parse_hm(s: str) -> tuple[int, int]:
    m = re.search(r"(\d{1,2}):(\d{2})", (s or "").strip())
    if not m:
        raise ValueError(f"无法解析时刻: {s}")
    return int(m.group(1)), int(m.group(2))


def _normalize_booking_range(
    st: datetime, et: datetime
) -> tuple[datetime, datetime, str | None]:
    """纠正模型臆造的过期年/已过去时段：保留钟点，落到服务器的「明天」。"""
    now = datetime.now()
    if et <= st:
        raise ValueError("结束时间必须晚于开始时间")
    duration = et - st
    wrong_year = st.year != now.year
    is_past = st < now
    if not wrong_year and not is_past:
        return st, et, None
    # 常见误判：把「明天」写成 2024 年 → 一律改到服务器明天同钟点
    day = (now + timedelta(days=1)).date()
    st2 = datetime(day.year, day.month, day.day, st.hour, st.minute, st.second)
    et2 = st2 + duration
    note = (
        f"已按服务器时间纠正为 {st2.strftime('%Y-%m-%d %H:%M')}~"
        f"{et2.strftime('%Y-%m-%d %H:%M')}（原解析疑似错误年份或已过去）"
    )
    return st2, et2, note


def tool_names_for_role(role: str) -> list[str]:
    r = (role or "student").strip().lower()
    if r == "admin":
        return list(CORE_TOOL_NAMES) + list(ADMIN_TOOL_NAMES)
    if r == "teacher":
        return list(TEACHER_TOOL_NAMES)
    return list(CORE_TOOL_NAMES)


def _pick_tools(tools: list, names: tuple[str, ...] | list[str]) -> list:
    by_name = {t.name: t for t in tools}
    return [by_name[n] for n in names if n in by_name]


def build_advisor_tools(user_id: int) -> list:
    """顾问专家：制度/安全/联系人检索 + 实验室名录 + 进不去诊断；不写预约库。"""
    return _pick_tools(
        _build_core_tools(user_id),
        ("search_labs", "search_lab_docs", "access_help"),
    )


def build_booking_tools(user_id: int) -> list:
    """办理专家：查空闲、确认门预约、须知/领码、取消；不改排课、不批单。"""
    return _pick_tools(
        _build_core_tools(user_id),
        (
            "search_labs",
            "pick_free_slot",
            "create_reservation",
            "cancel_draft",
            "list_my_reservations",
            "get_passcode",
            "cancel_reservation",
            "ack_safety",
            "issue_passcode",
            "access_help",
        ),
    )


def build_approval_tools(user_id: int) -> list:
    """审批专家（仅管理图）：待审、规则闸门、通过/驳回、白名单。"""
    return _pick_tools(
        _build_admin_only_tools(user_id),
        (
            "list_pending_reservations",
            "rule_review_reservation",
            "apply_reservation_decision",
            "auto_process_pending",
            "add_trusted_employee_no",
            "list_trusted_employee_nos",
        ),
    )


def build_schedule_tools(user_id: int) -> list:
    """教务专家（仅管理图）：排课占档查询/临时添加。"""
    return _pick_tools(
        _build_admin_only_tools(user_id),
        ("list_schedule_blocks", "add_schedule_block"),
    )


def build_student_tools(user_id: int) -> list:
    """学生可触达工具并集（顾问+办理），无改课与审批。"""
    return _build_core_tools(user_id)


def build_teacher_tools(user_id: int) -> list:
    """老师可触达工具并集（顾问+办理）；直通在 CRUD。"""
    return _build_core_tools(user_id)


def build_admin_tools(user_id: int) -> list:
    """管理可触达工具并集（四专家）。"""
    tools = _build_core_tools(user_id)
    tools.extend(_build_admin_only_tools(user_id))
    return tools


def build_tools_for_user(user_id: int, role: str = "student") -> list:
    """按角色分发到三套工具工厂（兼容旧调用）。"""
    r = (role or "student").strip().lower()
    if r == "admin":
        return build_admin_tools(user_id)
    if r == "teacher":
        return build_teacher_tools(user_id)
    return build_student_tools(user_id)


def _build_core_tools(user_id: int) -> list:
    def search_labs(query: str = "", min_capacity: int = 0) -> str:
        """搜索开放中的实验室。
        query：名称/位置关键词；min_capacity：最少容纳人数（如用户说「能坐30人」传 30）。
        返回 id/name/location/capacity；对用户介绍名称、位置、容量，勿提设备号或是否审批。
        """
        with SyncSessionLocal() as session:
            items = access_crud.sync_list_labs(
                session,
                query=query or "",
                min_capacity=int(min_capacity) if min_capacity else None,
            )
            return json.dumps(
                {
                    "items": items,
                    "min_capacity": int(min_capacity) if min_capacity else None,
                    "count": len(items),
                },
                ensure_ascii=False,
            )

    def pick_free_slot(
        prefer_lab_name: str = "",
        day_offset: int = 1,
        prefer: str = "pm",
        purpose: str = "",
        exclude_lab_name: str = "",
        exclude_lab_id: int = 0,
    ) -> str:
        """自动挑选空闲实验室与时段，并直接完成预检写入待确认草稿。
        day_offset：0=今天，1=明天，2=后天。prefer：am/pm/eve/any。
        用户说换一间：传 exclude_lab_name/exclude_lab_id 避开刚取消的旧实验室。
        成功后请复述给用户确认；用户确认后只调 create_reservation(confirm=true)。
        若已有待确认草稿，返回 PENDING_EXISTS（给 Agent）；请先 cancel_draft 再挑档。
        """
        draft = _get_pending(user_id)
        if draft:
            return json.dumps(_pending_exists_payload(draft), ensure_ascii=False)
        with SyncSessionLocal() as session:
            picked = access_crud.sync_pick_free_slot(
                session,
                prefer_lab_name=prefer_lab_name or "",
                day_offset=int(day_offset or 1),
                prefer=prefer or "pm",
                exclude_lab_name=exclude_lab_name or "",
                exclude_lab_id=int(exclude_lab_id or 0),
            )
            if not picked.get("ok"):
                picked["must_tell_user"] = True
                return json.dumps(picked, ensure_ascii=False)
            st = _parse_dt(picked["start_time"])
            et = _parse_dt(picked["end_time"])
            preview = access_crud.sync_preview_reservation(
                session,
                user_id=user_id,
                lab_id=int(picked["lab_id"]),
                start_time=st,
                end_time=et,
                purpose=purpose or None,
            )
            if not preview.get("ok"):
                preview["must_tell_user"] = True
                preview["picked"] = picked
                preview["hint"] = "把冲突原因告诉用户，不要静默换实验室。"
                return json.dumps(preview, ensure_ascii=False)
            _set_pending(user_id, {
                "action": "create_reservation",
                "lab_id": int(picked["lab_id"]),
                "start_time": picked["start_time"],
                "end_time": picked["end_time"],
                "purpose": purpose or "",
                "lab_name": picked.get("lab_name") or preview.get("lab_name"),
            })
            out = {
                **preview,
                "ok": True,
                "needs_confirm": True,
                "lab_id": picked["lab_id"],
                "lab_name": picked.get("lab_name") or preview.get("lab_name"),
                "start_time": picked["start_time"],
                "end_time": picked["end_time"],
                "next_step": "请复述实验室与时段请用户确认；确认后只调 create_reservation(confirm=true)。",
            }
            return json.dumps(out, ensure_ascii=False)

    def create_reservation(
        lab_id: int = 0,
        start_time: str = "",
        end_time: str = "",
        purpose: str = "",
        confirm: bool = False,
        day_offset: int | None = None,
        start_hm: str = "",
        end_hm: str = "",
        replace_pending: bool = False,
    ) -> str:
        """预约确认门。confirm=false 预检；用户说确认后必须 confirm=true 落库（可只传 confirm=true）。
        已有待确认草稿时：再预检换选会返回 PENDING_EXISTS，请先 cancel_draft；
        兼容：replace_pending=true 等同于先清草稿再预检。相对日期优先 day_offset+start_hm/end_hm。
        """
        draft = _get_pending(user_id)

        if confirm:
            if not draft or draft.get("action") != "create_reservation":
                return json.dumps(
                    {
                        "ok": False,
                        "written": False,
                        "error": "没有待确认的预约草稿，无法落库。请先重新预检（pick_free_slot 或 create_reservation confirm=false）。",
                        "must_tell_user": True,
                        "tell_user": "刚才没有可确认的预约草稿，还没写进预约表。请再说一次要约哪天/哪个时段，我重新预检后再请你确认。",
                    },
                    ensure_ascii=False,
                )
            lab_id = int(draft["lab_id"])
            start_time = draft["start_time"]
            end_time = draft["end_time"]
            purpose = draft.get("purpose") or purpose
            try:
                st = _parse_dt(start_time)
                et = _parse_dt(end_time)
            except Exception as e:
                return json.dumps(
                    {
                        "ok": False,
                        "written": False,
                        "error": f"草稿时间损坏: {e}",
                        "must_tell_user": True,
                    },
                    ensure_ascii=False,
                )
            with SyncSessionLocal() as session:
                try:
                    result = access_crud.sync_create_reservation(
                        session,
                        user_id=user_id,
                        lab_id=lab_id,
                        start_time=st,
                        end_time=et,
                        purpose=purpose or None,
                    )
                    if result.get("ok") and result.get("written"):
                        _set_pending(user_id, None)
                        session.commit()
                        result["must_tell_user"] = True
                        result["tell_user"] = (
                            f"已写入预约表：{result.get('lab_name') or ''} "
                            f"{start_time} 至 {end_time}，状态 {result.get('status')}。"
                        )
                    else:
                        session.rollback()
                        # 落库失败保留草稿，并要求把 error 原样告诉用户
                        result["ok"] = False
                        result["written"] = False
                        result["pending_kept"] = True
                        result["must_tell_user"] = True
                        result["tell_user"] = (
                            f"预约没有写入数据库：{result.get('error') or '未知原因'}。"
                            f"{result.get('suggest') or ''}禁止声称预约成功。"
                        )
                    return json.dumps(result, ensure_ascii=False)
                except Exception as e:
                    session.rollback()
                    return json.dumps(
                        {
                            "ok": False,
                            "written": False,
                            "error": str(e),
                            "must_tell_user": True,
                            "tell_user": f"预约写库异常：{e}。禁止声称预约成功。",
                        },
                        ensure_ascii=False,
                    )

        # ----- 预检 confirm=false -----
        fix_note = None
        try:
            if day_offset is not None and start_hm and end_hm:
                h0, m0 = _parse_hm(start_hm)
                h1, m1 = _parse_hm(end_hm)
                day = (datetime.now() + timedelta(days=int(day_offset))).date()
                st = datetime(day.year, day.month, day.day, h0, m0, 0)
                et = datetime(day.year, day.month, day.day, h1, m1, 0)
                start_time = st.strftime("%Y-%m-%d %H:%M:%S")
                end_time = et.strftime("%Y-%m-%d %H:%M:%S")
            else:
                if not lab_id or not start_time or not end_time:
                    return json.dumps(
                        {
                            "ok": False,
                            "error": "缺少 lab_id 与时间；请用 day_offset+start_hm/end_hm 或先 pick_free_slot",
                        },
                        ensure_ascii=False,
                    )
                st = _parse_dt(start_time)
                et = _parse_dt(end_time)
                st, et, fix_note = _normalize_booking_range(st, et)
                start_time = st.strftime("%Y-%m-%d %H:%M:%S")
                end_time = et.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"时间格式错误: {e}"}, ensure_ascii=False
            )

        if not lab_id:
            return json.dumps(
                {"ok": False, "error": "缺少 lab_id，请先 search_labs 或 pick_free_slot"},
                ensure_ascii=False,
            )

        if draft and not replace_pending:
            if draft.get("action") == "create_reservation":
                same = (
                    int(lab_id) == int(draft["lab_id"])
                    and start_time == draft["start_time"]
                    and end_time == draft["end_time"]
                )
                if not same:
                    return json.dumps(_pending_exists_payload(draft), ensure_ascii=False)
            else:
                # 取消/签须知等其它草稿：禁止静默覆盖
                return json.dumps(_pending_exists_payload(draft), ensure_ascii=False)
        if replace_pending and draft:
            _set_pending(user_id, None)
            draft = None

        with SyncSessionLocal() as session:
            try:
                result = access_crud.sync_preview_reservation(
                    session,
                    user_id=user_id,
                    lab_id=int(lab_id),
                    start_time=st,
                    end_time=et,
                    purpose=purpose or None,
                )
                if result.get("ok"):
                    _set_pending(user_id, {
                        "action": "create_reservation",
                        "lab_id": int(lab_id),
                        "start_time": start_time,
                        "end_time": end_time,
                        "purpose": purpose or "",
                        "lab_name": result.get("lab_name"),
                    })
                    result["start_time"] = start_time
                    result["end_time"] = end_time
                    result["needs_confirm"] = True
                    result["next_step"] = (
                        "请向用户复述实验室与时段，等用户确认后调用 "
                        "create_reservation(confirm=true)。禁止此时再换实验室。"
                    )
                    if fix_note:
                        result["time_fix"] = fix_note
                        result["summary"] = (
                            f"{fix_note}。" + str(result.get("summary") or "")
                        )
                else:
                    result["must_tell_user"] = True
                    result["hint"] = "把 error/suggest 原话告诉用户，不要静默换选。"
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                session.rollback()
                return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    def cancel_draft() -> str:
        """清空当前用户的待确认草稿（预约预检/取消预检/签须知/领码）。
        用户说换一间、换时间、不约这个、换成第二个等变更意图时先调用本工具，再查空闲或新建预检。
        不删除已落库的正式预约；正式取消请用 cancel_reservation。
        """
        draft = _get_pending(user_id)
        if not draft:
            return json.dumps(
                {
                    "ok": True,
                    "cleared": False,
                    "message": "当前没有待确认草稿，可直接挑档或预检。",
                },
                ensure_ascii=False,
            )
        snapshot = {
            "action": draft.get("action"),
            "lab_id": draft.get("lab_id"),
            "lab_name": draft.get("lab_name"),
            "start_time": draft.get("start_time"),
            "end_time": draft.get("end_time"),
            "reservation_ids": draft.get("reservation_ids"),
        }
        _set_pending(user_id, None)
        return json.dumps(
            {
                "ok": True,
                "cleared": True,
                "cleared_action": snapshot.get("action"),
                "cleared_pending": snapshot,
                "message": "已清空待确认草稿，可以重新挑档或预检。",
                "agent_hint": (
                    "草稿已清；若用户要换一间，请立刻 pick_free_slot("
                    f"exclude_lab_name={snapshot.get('lab_name')!r}, "
                    f"exclude_lab_id={snapshot.get('lab_id') or 0})；"
                    "若只换时间，用原 lab_id + 新 day_offset/start_hm/end_hm 做 create_reservation(confirm=false)。"
                ),
            },
            ensure_ascii=False,
        )

    def list_my_reservations() -> str:
        """查询当前用户预约。返回 active（可取消）与 history；取消必须用 active_ids 里的真实 id，禁止用 1,2,3 这种序号。"""
        with SyncSessionLocal() as session:
            items = access_crud.sync_my_reservations(session, user_id)
            active = [
                x
                for x in items
                if x.get("status") in ("pending", "approved", "in_use")
            ]
            # 补全可能不在最近 20 条里的活跃单
            active_all = access_crud.sync_my_active_reservations(session, user_id)
            by_id = {int(x["id"]): x for x in active}
            for x in active_all:
                by_id[int(x["id"])] = x
            active = sorted(by_id.values(), key=lambda x: int(x["id"]), reverse=True)
            history = [
                x
                for x in items
                if x.get("status") not in ("pending", "approved", "in_use")
            ]
            active_ids = [int(x["id"]) for x in active]
            return json.dumps(
                {
                    "active_count": len(active),
                    "active_ids": active_ids,
                    "active": active,
                    "history": history[:10],
                    "recent_cancelled": [
                        x for x in history if x.get("status") == "cancelled"
                    ][:5],
                    "hint": (
                        "对用户只说实验室名与时段，不要报内部 id；"
                        "取消时必须传 active_ids 原值，或 cancel_all_active=true；"
                        "禁止把列表序号 1,2,3 当成预约 id。"
                        "用户问「刚才取消了什么」：看 recent_cancelled / history 里 status=cancelled；"
                        "若刚成功取消过，以库内已取消记录为准，禁止说「只是预检还没取消」。"
                    ),
                },
                ensure_ascii=False,
            )

    def get_passcode() -> str:
        """查询当前用户有效通行码（需已审批并签署须知后领取）。"""
        with SyncSessionLocal() as session:
            result = access_crud.sync_get_passcode(session, user_id)
            return json.dumps(result, ensure_ascii=False)

    def cancel_reservation(
        reservation_id: int = 0,
        reservation_ids: str = "",
        cancel_all_active: bool = False,
        confirm: bool = False,
    ) -> str:
        """取消本人预约（支持批量 / 全部有效单）。

        用户说「全部取消」→ 必须 cancel_all_active=true（由库查出真实 id），禁止手填 1,2,3。
        指定取消：reservation_ids 必须来自 list_my_reservations 的 active_ids。
        第1轮 confirm=false 复述清单；第2轮用户确认后 confirm=true（可只传 confirm=true）。
        """
        def _parse_ids() -> list[int]:
            ids: list[int] = []
            if reservation_ids and str(reservation_ids).strip():
                for part in re.split(r"[,，\s]+", str(reservation_ids).strip()):
                    if not part:
                        continue
                    try:
                        ids.append(int(part))
                    except ValueError:
                        continue
            if reservation_id and int(reservation_id) > 0:
                ids.append(int(reservation_id))
            seen: set[int] = set()
            out: list[int] = []
            for i in ids:
                if i not in seen:
                    seen.add(i)
                    out.append(i)
            return out

        with SyncSessionLocal() as session:
            draft = _get_pending(user_id) or {}
            ids = _parse_ids()
            use_all = bool(cancel_all_active) or (
                draft.get("action") == "cancel_reservation"
                and bool(draft.get("cancel_all_active"))
            )

            if confirm and not ids and draft.get("action") == "cancel_reservation":
                ids = [int(x) for x in (draft.get("reservation_ids") or [])]

            def _empty_list_payload(*, missing_ids: list[int] | None = None, found=None):
                return {
                    "ok": True,
                    "written": False,
                    "empty": True,
                    "active_count": 0,
                    "cancelled_count": 0,
                    "missing_ids": missing_ids or [],
                    "found": found or [],
                    "message": "当前没有有效预约，预约列表为空",
                    "tell_user": "当前预约列表为空，没有可取消的预约。禁止再说「已成功取消」。",
                }

            if use_all:
                targets = access_crud.sync_my_active_reservations(session, user_id)
                ids = [int(x["id"]) for x in targets]
                missing: list[int] = []
            elif not ids:
                return json.dumps(
                    {
                        "ok": False,
                        "error": (
                            "缺少预约 id。用户要全部取消请传 cancel_all_active=true；"
                            "指定取消请传 list_my_reservations 返回的 active_ids，禁止用序号 1,2,3。"
                        ),
                    },
                    ensure_ascii=False,
                )
            else:
                targets = []
                missing = []
                for rid in ids:
                    row = access_crud.sync_get_my_reservation(
                        session, user_id=user_id, reservation_id=rid
                    )
                    if not row:
                        missing.append(rid)
                    else:
                        targets.append(row)

            if not confirm:
                cancellable = [
                    t
                    for t in targets
                    if t.get("status") in ("pending", "approved", "in_use")
                ]
                if not cancellable:
                    if use_all or not missing:
                        return json.dumps(
                            _empty_list_payload(missing_ids=missing, found=targets),
                            ensure_ascii=False,
                        )
                    hint = ""
                    if missing and set(missing) <= {1, 2, 3, 4, 5}:
                        hint = (
                            "你传入的像是列表序号而非数据库 id。"
                            "请改用 cancel_all_active=true，或先 list_my_reservations 取 active_ids。"
                        )
                    return json.dumps(
                        {
                            "ok": False,
                            "error": "没有可取消的有效预约"
                            + (f"；{hint}" if hint else "（可能已取消或已过期）"),
                            "missing_ids": missing,
                            "found": targets,
                            "retry": "cancel_reservation(cancel_all_active=true, confirm=false)",
                            "tell_user": "若确无有效单，告知预约列表为空，不要谎称取消成功。",
                        },
                        ensure_ascii=False,
                    )
                _set_pending(user_id, {
                    "action": "cancel_reservation",
                    "reservation_ids": [int(t["id"]) for t in cancellable],
                    "cancel_all_active": bool(use_all),
                })
                lines = []
                for t in cancellable:
                    lines.append(
                        f"· {t.get('lab_name') or '实验室'}，"
                        f"{t.get('start_time')} 至 {t.get('end_time')}"
                    )
                body = "\n".join(lines) if lines else ""
                tell_user = (
                    f"将取消 {len(cancellable)} 个预约并作废相关通行码。"
                    + (f"\n{body}\n" if body else "")
                    + "请回复「确认」以取消。"
                )
                return json.dumps(
                    {
                        "ok": True,
                        "needs_confirm": True,
                        "count": len(cancellable),
                        "active_ids": [int(t["id"]) for t in cancellable],
                        "reservations": cancellable,
                        "missing_ids": missing,
                        "tell_user": tell_user,
                        "summary": (
                            f"将取消 {len(cancellable)} 个预约。"
                            "对用户只复述实验室与时段，勿报内部 id；"
                            "用户确认后 cancel_reservation(confirm=true)。"
                        ),
                        "agent_hint": (
                            "下一轮用户说确认后立刻 cancel_reservation(confirm=true)；"
                            "若带全部取消意图须同时 cancel_all_active=true。"
                        ),
                    },
                    ensure_ascii=False,
                )

            # confirm=true：无草稿时若带了 cancel_all_active 仍可直接按库取消；
            # 若既无草稿又未声明全部取消，禁止假装成功。
            if use_all:
                ids = [
                    int(x["id"])
                    for x in access_crud.sync_my_active_reservations(session, user_id)
                ]
            elif draft.get("action") == "cancel_reservation":
                ids = [int(x) for x in (draft.get("reservation_ids") or ids)]
            elif not ids:
                return json.dumps(
                    {
                        "ok": False,
                        "written": False,
                        "error": "没有待确认的取消草稿。用户要全部取消时请传 cancel_all_active=true, confirm=true。",
                        "must_tell_user": True,
                        "tell_user": "取消没有执行成功（缺少取消清单）。请再说一次「全部取消」，我重新预检后再请你确认。禁止声称已取消成功或列表为空。",
                    },
                    ensure_ascii=False,
                )

            if not ids:
                _set_pending(user_id, None)
                return json.dumps(_empty_list_payload(), ensure_ascii=False)

            results = []
            try:
                for rid in ids:
                    result = access_crud.sync_cancel_reservation(
                        session, user_id=user_id, reservation_id=int(rid)
                    )
                    results.append(result)
                _set_pending(user_id, None)
                session.commit()
                newly = [r for r in results if r.get("written")]
                already = [
                    r for r in results if r.get("ok") and not r.get("written")
                ]
                failed = [r for r in results if not r.get("ok")]
                # 写库后再查一遍：以剩余有效单为准，防止口头“列表为空”
                remaining = access_crud.sync_my_active_reservations(session, user_id)
                remaining_ids = [int(x["id"]) for x in remaining]
                if not newly:
                    payload = _empty_list_payload()
                    payload.update(
                        {
                            "already_cancelled": already,
                            "failed": failed,
                            "remaining_active_count": len(remaining),
                            "remaining_active_ids": remaining_ids,
                            "message": (
                                "当前没有新取消的预约"
                                + (
                                    f"，仍有 {len(remaining)} 条有效预约"
                                    if remaining
                                    else "，预约列表为空"
                                )
                            ),
                            "tell_user": (
                                f"取消未产生新变更；仍有 {len(remaining)} 条有效预约，列表并未清空。"
                                if remaining
                                else "当前预约列表为空，没有可取消的预约。禁止再说「已成功取消」。"
                            ),
                            "empty": not remaining,
                            "ok": not remaining and not failed,
                            "written": False,
                        }
                    )
                    return json.dumps(payload, ensure_ascii=False)

                all_cleared = use_all and not remaining
                detail_lines = []
                fact_items = []
                for r in newly:
                    lab_n = r.get("lab_name") or "实验室"
                    st = r.get("start_time") or ""
                    et = r.get("end_time") or ""
                    detail_lines.append(f"· {lab_n}，{st} 至 {et}")
                    fact_items.append(
                        {
                            "lab_name": lab_n,
                            "start_time": st,
                            "end_time": et,
                            "id": r.get("id"),
                        }
                    )
                detail_block = ("\n" + "\n".join(detail_lines)) if detail_lines else ""
                if all_cleared or not remaining:
                    tell_user = (
                        f"已成功取消 {len(newly)} 个预约{detail_block}\n"
                        "当前有效预约列表已空。"
                    )
                else:
                    tell_user = (
                        f"已取消 {len(newly)} 个预约{detail_block}\n"
                        f"但列表并未清空，仍剩 {len(remaining)} 条有效预约。禁止说列表为空。"
                    )
                _set_last_write_fact(
                    user_id,
                    {
                        "action": "cancel",
                        "items": fact_items,
                        "cancelled_count": len(newly),
                        "remaining_active_count": len(remaining),
                    },
                )
                return json.dumps(
                    {
                        "ok": not failed and (not use_all or all_cleared),
                        "written": True,
                        "empty": not remaining,
                        "cancelled_count": len(newly),
                        "cancelled": newly,
                        "already_cancelled": already,
                        "failed": failed,
                        "remaining_active_count": len(remaining),
                        "remaining_active_ids": remaining_ids,
                        "remaining_active": remaining,
                        "must_tell_user": True,
                        "message": (
                            f"已新取消 {len(newly)} 个"
                            + (f"，另有 {len(already)} 个本来就是已取消" if already else "")
                            + (f"，{len(failed)} 个失败" if failed else "")
                            + (
                                f"；仍剩 {len(remaining)} 条有效预约"
                                if remaining
                                else "；有效预约列表已空"
                            )
                        ),
                        "tell_user": tell_user,
                    },
                    ensure_ascii=False,
                )
            except Exception as e:
                session.rollback()
                return json.dumps(
                    {
                        "ok": False,
                        "written": False,
                        "error": str(e),
                        "must_tell_user": True,
                        "tell_user": f"取消写库异常：{e}。禁止声称已取消成功。",
                    },
                    ensure_ascii=False,
                )

    def ack_safety(reservation_id: int, confirm: bool = False) -> str:
        """签署安全须知。confirm=false 先展示须知全文；用户确认后再 confirm=true 落库。"""
        if not confirm:
            _set_pending(user_id, {
                "action": "ack_safety",
                "reservation_id": int(reservation_id),
            })
            return json.dumps(
                {
                    "ok": True,
                    "needs_confirm": True,
                    "reservation_id": int(reservation_id),
                    "safety_text": access_crud.SAFETY_TEXT_V1,
                    "summary": "请向用户展示须知要点，待其确认后再签署。",
                },
                ensure_ascii=False,
            )
        with SyncSessionLocal() as session:
            try:
                rid = int(reservation_id)
                if (_get_pending(user_id) or {}).get("action") == "ack_safety":
                    rid = int((_get_pending(user_id) or {}).get("reservation_id", rid))
                result = access_crud.sync_ack_safety(
                    session, user_id=user_id, reservation_id=rid
                )
                if result.get("ok"):
                    _set_pending(user_id, None)
                    session.commit()
                else:
                    session.rollback()
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                session.rollback()
                return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    def issue_passcode(reservation_id: int, confirm: bool = False) -> str:
        """领取通行码。confirm=false 先说明将发码；确认后再 confirm=true 发码。"""
        if not confirm:
            _set_pending(user_id, {
                "action": "issue_passcode",
                "reservation_id": int(reservation_id),
            })
            return json.dumps(
                {
                    "ok": True,
                    "needs_confirm": True,
                    "reservation_id": int(reservation_id),
                    "summary": f"将为预约#{reservation_id}发放通行码（须已审批并签须知）。请用户确认。",
                },
                ensure_ascii=False,
            )
        with SyncSessionLocal() as session:
            try:
                rid = int(reservation_id)
                if (_get_pending(user_id) or {}).get("action") == "issue_passcode":
                    rid = int((_get_pending(user_id) or {}).get("reservation_id", rid))
                result = access_crud.sync_issue_passcode(
                    session, user_id=user_id, reservation_id=rid
                )
                if result.get("ok"):
                    _set_pending(user_id, None)
                    session.commit()
                else:
                    session.rollback()
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                session.rollback()
                return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    def access_help(lab_hint: str = "") -> str:
        """用户说进不去/刷不开时调用：查本人最近核验流水、有效预约与门口绑定，给可执行建议。
        必须依据返回的 bookings[].doors / door_hint 告知正确 device_id，禁止猜测门口。不写库。
        """
        with SyncSessionLocal() as session:
            result = access_crud.sync_access_help(
                session, user_id=user_id, lab_hint=lab_hint or ""
            )
            return json.dumps(result, ensure_ascii=False)

    def search_lab_docs(q: str, lab: str = "") -> str:
        """检索实验室制度语料（安全须知、开放规则、管理员联系方式等）。
        问规则/安全/找谁审批时先调用；空闲与预约仍用 search_labs / create_reservation。
        lab 可填实验室名称关键词以优先匹配专篇；可空。
        """
        from utils.faiss_kb import format_hits, search_lab_docs as _search

        hits = _search(q, lab=lab or None)
        return format_hits(hits)

    return [
        StructuredTool.from_function(search_labs, name="search_labs"),
        StructuredTool.from_function(pick_free_slot, name="pick_free_slot"),
        StructuredTool.from_function(create_reservation, name="create_reservation"),
        StructuredTool.from_function(cancel_draft, name="cancel_draft"),
        StructuredTool.from_function(list_my_reservations, name="list_my_reservations"),
        StructuredTool.from_function(get_passcode, name="get_passcode"),
        StructuredTool.from_function(cancel_reservation, name="cancel_reservation"),
        StructuredTool.from_function(ack_safety, name="ack_safety"),
        StructuredTool.from_function(issue_passcode, name="issue_passcode"),
        StructuredTool.from_function(access_help, name="access_help"),
        StructuredTool.from_function(search_lab_docs, name="search_lab_docs"),
    ]


def _build_admin_only_tools(user_id: int) -> list:
    def list_schedule_blocks(
        lab_name: str = "",
        from_time: str = "",
        to_time: str = "",
    ) -> str:
        """查询教务排课占档。可选实验室名称与时间范围。"""
        st = _parse_dt(from_time) if from_time.strip() else None
        et = _parse_dt(to_time) if to_time.strip() else None
        with SyncSessionLocal() as session:
            items = schedule_crud.sync_list_blocks(
                session,
                lab_name=lab_name or None,
                start=st,
                end=et,
            )
            return json.dumps({"items": items}, ensure_ascii=False)

    def add_schedule_block(
        lab_name: str,
        title: str,
        start_time: str,
        end_time: str,
        note: str = "",
    ) -> str:
        """学校管理员添加一条临时排课占档（挡学生/老师预约）。大批量请用 Excel 导入页。"""
        try:
            st = _parse_dt(start_time)
            et = _parse_dt(end_time)
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"时间格式错误: {e}"}, ensure_ascii=False
            )
        with SyncSessionLocal() as session:
            try:
                result = schedule_crud.sync_add_block(
                    session,
                    user_id=user_id,
                    lab_name=lab_name,
                    title=title,
                    start_time=st,
                    end_time=et,
                    note=note or None,
                )
                session.commit()
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                session.rollback()
                return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    def list_pending_reservations(limit: int = 20) -> str:
        """列出待审核预约（pending），供管理员批处理。"""
        from agent.approval import list_pending

        items = list_pending(limit=max(1, min(int(limit or 20), 50)))
        return json.dumps({"items": items, "count": len(items)}, ensure_ascii=False)

    def rule_review_reservation(reservation_id: int) -> str:
        """对单条待审预约只跑规则闸门，不出大模型建议，默认不改状态。
        返回 can_auto_approve 表示是否满足自动通过条件。
        """
        from agent.approval import review_one

        return json.dumps(review_one(int(reservation_id)), ensure_ascii=False)

    def apply_reservation_decision(
        reservation_id: int,
        action: str,
        reason: str = "",
    ) -> str:
        """管理员明确执行通过或驳回。action=approve|reject；驳回请填 reason。
        规则未过或需人工时用本工具，不要口头说「已通过」。
        """
        from agent.approval import apply_decision

        return json.dumps(
            apply_decision(
                int(reservation_id),
                action=action,
                reason=reason,
                actor_note="管理员经助手确认",
            ),
            ensure_ascii=False,
        )

    def auto_process_pending(limit: int = 5, dry_run: bool = False) -> str:
        """批量处理待审：仅自动通过「规则闸门通过」的单；其余列入 need_human，不自动驳回。
        dry_run=True 只演练不改库。不调用大模型。
        资格路径：用途合格，或历史成功预约够次数，或工号在可信白名单。
        """
        from agent.approval import auto_process_pending as _auto

        return json.dumps(
            _auto(limit=max(1, min(int(limit or 5), 20)), dry_run=bool(dry_run)),
            ensure_ascii=False,
        )

    def add_trusted_employee_no(employee_no: str) -> str:
        """录入可信工号到白名单。之后该工号用户待审可走「工号」资格路径（仍受时长等硬条件约束）。"""
        from agent.approval import add_trusted_employee_no as _add

        return json.dumps(_add(employee_no), ensure_ascii=False)

    def list_trusted_employee_nos() -> str:
        """查看已录入的可信工号白名单。"""
        from agent.approval import load_trusted_employee_nos

        nos = sorted(load_trusted_employee_nos())
        return json.dumps({"items": nos, "count": len(nos)}, ensure_ascii=False)

    return [
        StructuredTool.from_function(list_schedule_blocks, name="list_schedule_blocks"),
        StructuredTool.from_function(add_schedule_block, name="add_schedule_block"),
        StructuredTool.from_function(
            list_pending_reservations, name="list_pending_reservations"
        ),
        StructuredTool.from_function(
            rule_review_reservation, name="rule_review_reservation"
        ),
        StructuredTool.from_function(
            apply_reservation_decision, name="apply_reservation_decision"
        ),
        StructuredTool.from_function(auto_process_pending, name="auto_process_pending"),
        StructuredTool.from_function(
            add_trusted_employee_no, name="add_trusted_employee_no"
        ),
        StructuredTool.from_function(
            list_trusted_employee_nos, name="list_trusted_employee_nos"
        ),
    ]
