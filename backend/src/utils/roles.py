from fastapi import HTTPException

from model.user import User

# 学校管理员：排课、实验室维护、学生预约审批、看板
SCHOOL_ADMIN = "admin"


def require_school_admin(user: User) -> None:
    if user.role != SCHOOL_ADMIN:
        raise HTTPException(status_code=403, detail="需要学校管理员权限")


# 兼容旧名：现仅 admin（老师不再算管理端）
def require_admin(user: User) -> None:
    require_school_admin(user)


def reservation_status_for_role(role: str, need_approve: int | bool = 1) -> str:
    """老师/管理员直通；学生仅当实验室 need_approve=0 时免审直通，否则 pending。"""
    if role != "student":
        return "approved"
    if not int(need_approve or 0):
        return "approved"
    return "pending"
