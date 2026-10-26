"""通行：须知、发码、核验、流水（A2）。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from crud import access as access_crud
from crud import lab as lab_crud
from crud import ops as ops_crud
from crud import reservation as res_crud
from model.access import Passcode
from model.reservation import Reservation
from model.user import User
from schema.access import (
    AccessLogOut,
    PasscodeIssueIn,
    PasscodeOut,
    SafetyAckIn,
    VerifyIn,
)
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_admin

router = APIRouter(prefix="/api/access", tags=["access"])

SAFETY_TEXT = (
    "进入实验室须遵守安全规定：禁止违规用电、食品饮料远离设备、"
    "离开前断电关窗。本人已阅读并同意上述须知。"
)


async def _passcode_payload(
    db: AsyncSession,
    pc: Passcode,
    res: Reservation | None = None,
) -> dict:
    """通行码 + 实验室名称/位置 + 刷码统计，供领码弹窗与列表展示。"""
    if res is None:
        res = await res_crud.get_reservation(db, pc.reservation_id)
    data = PasscodeOut.model_validate(pc).model_dump()
    stats = await access_crud.passcode_allow_stats(db, pc.code)
    data["scan_ok_count"] = stats["scan_ok_count"]
    data["last_allowed_at"] = stats["last_allowed_at"]
    if res:
        data["lab_id"] = res.lab_id
        data["start_time"] = res.start_time
        data["end_time"] = res.end_time
        lab = await lab_crud.get_lab(db, res.lab_id)
        if lab:
            data["lab_name"] = lab.name
            data["lab_location"] = lab.location
    return data


@router.get("/safety-text")
async def safety_text(user: User = Depends(get_current_user)):
    _ = user
    return success_response(
        message="ok",
        data={"version": "v1", "text": SAFETY_TEXT},
    )


@router.post("/safety/ack")
async def ack_safety(
    body: SafetyAckIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await res_crud.get_reservation(db, body.reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="预约不存在")
    if res.user_id != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="只能签署自己的预约须知")

    if res.status not in ("approved", "in_use"):
        raise HTTPException(status_code=400, detail="仅已通过的预约可签署须知")

    existed = await access_crud.get_ack(db, user.id, body.reservation_id)
    if existed:
        return success_response(message="已签署过", data={"acked": True})

    await access_crud.create_ack(db, user.id, body.reservation_id)
    return success_response(message="签署成功", data={"acked": True})


@router.post("/passcode/issue")
async def issue_passcode(
    body: PasscodeIssueIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    res = await res_crud.get_reservation(db, body.reservation_id)
    if not res:
        raise HTTPException(status_code=404, detail="预约不存在")
    if res.user_id != user.id:
        raise HTTPException(status_code=403, detail="只能领取自己的通行码")
    if res.status not in ("approved", "in_use"):
        raise HTTPException(status_code=400, detail="预约未通过，无法发码")

    ack = await access_crud.get_ack(db, user.id, body.reservation_id)
    if not ack:
        raise HTTPException(status_code=400, detail="请先签署安全须知")

    existed = await access_crud.get_active_passcode_for_res(db, body.reservation_id)
    if existed:
        return success_response(
            message="已有有效通行码",
            data=await _passcode_payload(db, existed, res),
        )

    row = await access_crud.create_passcode(db, reservation=res, user_id=user.id)
    return success_response(
        message="发码成功",
        data=await _passcode_payload(db, row, res),
    )


@router.get("/passcode/mine")
async def my_passcodes(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = await access_crud.list_my_passcodes(db, user.id)
    items = [await _passcode_payload(db, x) for x in rows]
    return success_response(message="ok", data={"items": items})


@router.post("/verify")
async def verify(
    body: VerifyIn,
    db: AsyncSession = Depends(get_db),
):
    """硬件 / 模拟门调用；不强制用户 Bearer。"""
    code = body.code.strip().upper()
    now = datetime.now()
    pc = await access_crud.get_passcode_by_code(db, code)

    if not pc:
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=None,
            reservation_id=None,
            allowed=False,
            reason="无效凭证",
        )
        return success_response(
            message="拒绝通行",
            data={"allowed": False, "reason": "无效凭证", "buzz": "long"},
        )

    if pc.status != "active":
        reason = f"凭证状态不可用:{pc.status}"
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=pc.user_id,
            reservation_id=pc.reservation_id,
            allowed=False,
            reason=reason,
        )
        return success_response(
            message="拒绝通行",
            data={"allowed": False, "reason": reason, "buzz": "long"},
        )

    if now < pc.valid_from or now > pc.valid_to:
        reason = "不在有效时段内"
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=pc.user_id,
            reservation_id=pc.reservation_id,
            allowed=False,
            reason=reason,
        )
        return success_response(
            message="拒绝通行",
            data={"allowed": False, "reason": reason, "buzz": "long"},
        )

    res = await res_crud.get_reservation(db, pc.reservation_id)
    if not res:
        reason = "预约不存在"
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=pc.user_id,
            reservation_id=pc.reservation_id,
            allowed=False,
            reason=reason,
        )
        return success_response(
            message="拒绝通行",
            data={"allowed": False, "reason": reason, "buzz": "long"},
        )

    if res.status not in ("approved", "in_use"):
        reason = f"预约状态不可通行:{res.status}"
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=pc.user_id,
            reservation_id=pc.reservation_id,
            allowed=False,
            reason=reason,
        )
        return success_response(
            message="拒绝通行",
            data={"allowed": False, "reason": reason, "buzz": "long"},
        )

    # 一块硬件只绑一间实验室：device_id → lab_id 必须与预约实验室一致
    device = await access_crud.get_device_by_device_id(db, body.device_id)
    if not device or device.status != "active":
        reason = "未知门禁设备"
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=pc.user_id,
            reservation_id=pc.reservation_id,
            allowed=False,
            reason=reason,
        )
        return success_response(
            message="拒绝通行",
            data={"allowed": False, "reason": reason, "buzz": "long"},
        )

    if device.lab_id != res.lab_id:
        reason = "非本实验室凭证（请到预约对应实验室门口刷码）"
        await access_crud.add_access_log(
            db,
            code=code,
            device_id=body.device_id,
            user_id=pc.user_id,
            reservation_id=pc.reservation_id,
            allowed=False,
            reason=reason,
        )
        return success_response(
            message="拒绝通行",
            data={
                "allowed": False,
                "reason": reason,
                "buzz": "long",
                "reservation_lab_id": res.lab_id,
                "device_lab_id": device.lab_id,
            },
        )

    # 首次刷入：预约改为使用中；通行码保持 active，有效期内可再次刷码
    first_entry = res.status == "approved"
    if first_entry:
        res.status = "in_use"
        await db.flush()
        await db.commit()

    # 站内消息只提示一次（同一预约），不废码
    tipped = False
    if not await ops_crud.message_exists(
        db,
        user_id=pc.user_id,
        msg_type="access_scanned",
        related_id=pc.reservation_id,
    ):
        await ops_crud.create_message(
            db,
            user_id=pc.user_id,
            msg_type="access_scanned",
            title="已扫码完成",
            content=(
                f"您已在门禁刷码进入（预约#{pc.reservation_id}）。"
                f"有效期内通行码仍可使用，无需重新领码。"
            ),
            related_id=pc.reservation_id,
        )
        tipped = True

    await access_crud.add_access_log(
        db,
        code=code,
        device_id=body.device_id,
        user_id=pc.user_id,
        reservation_id=pc.reservation_id,
        allowed=True,
        reason="核验通过" if first_entry else "核验通过（再次刷码）",
    )
    return success_response(
        message="允许通行",
        data={
            "allowed": True,
            "reason": "核验通过",
            "buzz": "short",
            "user_id": pc.user_id,
            "reservation_id": pc.reservation_id,
            "lab_id": res.lab_id,
            "device_id": device.device_id,
            "first_entry": first_entry,
            "notified": tipped,
            "passcode_reusable": True,
        },
    )


@router.get("/devices")
async def list_devices(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出门禁设备及其绑定实验室（测试选门口用）。"""
    _ = user
    from crud import lab as lab_crud

    rows = await access_crud.list_devices(db)
    items = []
    for d in rows:
        lab = await lab_crud.get_lab(db, d.lab_id)
        items.append(
            {
                "device_id": d.device_id,
                "lab_id": d.lab_id,
                "name": d.name,
                "status": d.status,
                "lab_name": lab.name if lab else None,
            }
        )
    return success_response(message="ok", data={"items": items})


@router.get("/logs")
async def logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    rows = await access_crud.list_logs(db, limit=limit)
    return success_response(
        message="ok",
        data={"items": [AccessLogOut.model_validate(x).model_dump() for x in rows]},
    )
