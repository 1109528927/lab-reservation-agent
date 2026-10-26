"""实验室助手 Tool。按请求绑定 user_id；admin 额外挂排课 Tool。"""
from __future__ import annotations

import json
from datetime import datetime

from langchain_core.tools import StructuredTool

from config.request import SyncSessionLocal
from crud import access as access_crud
from crud import schedule as schedule_crud


CORE_TOOL_NAMES = (
    "search_labs",
    "create_reservation",
    "list_my_reservations",
    "get_passcode",
)

ADMIN_TOOL_NAMES = (
    "list_schedule_blocks",
    "add_schedule_block",
)


def _parse_dt(s: str) -> datetime:
    s = s.strip().replace("Z", "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(s)


def build_tools_for_user(user_id: int, role: str = "student") -> list:
    def search_labs(query: str = "") -> str:
        """搜索开放中的实验室，可按名称或位置关键词过滤。"""
        with SyncSessionLocal() as session:
            items = access_crud.sync_list_labs(session, query=query or "")
            return json.dumps({"items": items}, ensure_ascii=False)

    def create_reservation(
        lab_id: int,
        start_time: str,
        end_time: str,
        purpose: str = "",
    ) -> str:
        """为当前登录用户创建预约。学生提交后待管理员审核；老师直接通过。时间如 2026-10-20 14:00:00。"""
        try:
            st = _parse_dt(start_time)
            et = _parse_dt(end_time)
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"时间格式错误: {e}"}, ensure_ascii=False
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
                session.commit()
                return json.dumps(result, ensure_ascii=False)
            except Exception as e:
                session.rollback()
                return json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False)

    def list_my_reservations() -> str:
        """查询当前用户的预约列表。"""
        with SyncSessionLocal() as session:
            items = access_crud.sync_my_reservations(session, user_id)
            return json.dumps({"items": items}, ensure_ascii=False)

    def get_passcode() -> str:
        """查询当前用户有效通行码（需已审批并签署须知后领取）。"""
        with SyncSessionLocal() as session:
            result = access_crud.sync_get_passcode(session, user_id)
            return json.dumps(result, ensure_ascii=False)

    tools = [
        StructuredTool.from_function(search_labs, name="search_labs"),
        StructuredTool.from_function(create_reservation, name="create_reservation"),
        StructuredTool.from_function(list_my_reservations, name="list_my_reservations"),
        StructuredTool.from_function(get_passcode, name="get_passcode"),
    ]

    if role == "admin":

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

        tools.extend(
            [
                StructuredTool.from_function(
                    list_schedule_blocks, name="list_schedule_blocks"
                ),
                StructuredTool.from_function(
                    add_schedule_block, name="add_schedule_block"
                ),
            ]
        )

    return tools
