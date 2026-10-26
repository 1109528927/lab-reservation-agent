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


def reservation_status_for_role(role: str) -> str:
    """学生预约一律待审；老师/管理员直接通过。"""
    if role == "student":
        return "pending"
    return "approved"
