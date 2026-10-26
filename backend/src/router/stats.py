"""简单看板（A3 轻量）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config.request import get_db
from model.access import AccessLog
from model.lab import Lab
from model.reservation import Reservation
from model.user import User
from utils.auth import get_current_user
from utils.response import success_response
from utils.roles import require_admin

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def overview(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_admin(user)
    labs = (await db.execute(select(func.count()).select_from(Lab))).scalar_one()
    users = (await db.execute(select(func.count()).select_from(User))).scalar_one()
    pending = (
        await db.execute(
            select(func.count()).select_from(Reservation).where(
                Reservation.status == "pending"
            )
        )
    ).scalar_one()
    approved = (
        await db.execute(
            select(func.count()).select_from(Reservation).where(
                Reservation.status.in_(("approved", "in_use"))
            )
        )
    ).scalar_one()
    allow = (
        await db.execute(
            select(func.count()).select_from(AccessLog).where(AccessLog.allowed == 1)
        )
    ).scalar_one()
    deny = (
        await db.execute(
            select(func.count()).select_from(AccessLog).where(AccessLog.allowed == 0)
        )
    ).scalar_one()
    return success_response(
        message="ok",
        data={
            "labs": labs,
            "users": users,
            "reservations_pending": pending,
            "reservations_active": approved,
            "access_allow": allow,
            "access_deny": deny,
        },
    )
