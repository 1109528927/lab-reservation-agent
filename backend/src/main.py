"""智能实验室预约通行系统 — FastAPI 入口。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from router.loginuser import router as user_router
from router import lab as lab_router
from router import reservation as reservation_router
from router import access as access_router
from router import agent as agent_router
from router import stats as stats_router
from router import schedule as schedule_router
from router import ops as ops_router
from utils.exception import register_exception_handlers

app = FastAPI(title="智能实验室预约通行系统", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(user_router)
app.include_router(lab_router.router)
app.include_router(reservation_router.router)
app.include_router(access_router.router)
app.include_router(agent_router.router)
app.include_router(stats_router.router)
app.include_router(schedule_router.router)
app.include_router(ops_router.router)


@app.get("/api/health")
async def health():
    return {"code": 200, "message": "ok", "data": {"service": "lab-access"}}
