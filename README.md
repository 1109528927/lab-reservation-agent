# 智能实验室预约通行系统

Vue3 + FastAPI + MySQL + Redis + LangGraph Agent；门口可选 ESP32-S3 扫码通行。

登录后管理实验室、预约审核、通行码与信用/报修；智能助手用自然语言查实验室、下预约、查通行码（SSE 流式回复）。

| 层 | 技术 | 作用 |
|----|------|------|
| 前端 | Vue3、Vue Router、Element Plus、Vite | 管理端 + 学生端 H5（`/m`） |
| 后端 | FastAPI、SQLAlchemy、Pydantic | 业务 API、Token 鉴权 |
| 数据 | MySQL | 用户、实验室、预约、通行、排课 |
| 缓存 | Redis | 会话/业务缓存 |
| 智能 | LangGraph 手画状态图 + Tool | 查库、预约、通行码 |
| 硬件 | ESP32-S3 + 串口扫码模块 | 门口核验（可选） |

## 功能要点

1. **预约闭环：** 申请 → 审批（或自动通过）→ 领通行码 → 门口/模拟门核验。
2. **Agent：** `StateGraph` + Tool（查实验室、创建预约、我的预约、通行码；管理员另有排课工具）。未配置 `LLM_API_KEY` 时可降级。
3. **流式对话：** `POST /api/ai/chat/stream`（SSE），前端边打字边显示过程。

## 目录

```text
front/                 Vue3 前端
backend/
  src/                 FastAPI（工作目录需含 PYTHONPATH=src）
  sql/                 建表与演示种子
  scripts/             种子/冒烟脚本
firmware/              ESP32-S3 门口固件（可选）
docker-compose.yml     一键起 MySQL + Redis + 后端 + 前端
```

本仓库**不含**个人笔记、开题文档、本机 `.env` 与密钥。

---

## 方式一：Docker（推荐）

依赖：Docker / Docker Compose。

```bash
cp .env.example .env
# 可选：填 LLM_API_KEY（阿里云百炼 OpenAI 兼容）

docker compose up -d --build
```

| 服务 | 地址 |
|------|------|
| 前端 | http://127.0.0.1:5173 |
| 后端 API / 文档 | http://127.0.0.1:8000/docs |
| MySQL | `127.0.0.1:3306` 库 `lab_access`（默认 root / 123456） |
| Redis | `127.0.0.1:6379` |

首次启动会按 `backend/sql/` 初始化表结构与演示实验室。请在页面**注册**学生账号；管理员需在库里改 `user.role='admin'`，或用：

```bash
docker compose exec backend python scripts/seed_teacher.py
```

镜像名：

- `lab-reservation-agent-backend:latest`
- `lab-reservation-agent-front:latest`

单独构建：

```bash
docker compose build
# 或
docker build -t lab-reservation-agent-backend:latest ./backend
docker build -t lab-reservation-agent-front:latest ./front
```

---

## 方式二：本机开发

依赖：Python 3.12+、Node 22+、pnpm、MySQL、Redis。

### 1. 数据库

按顺序执行 `backend/sql/` 下脚本（`01` → `05`）。

### 2. 后端

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 DATABASE_URL / REDIS_URL / LLM_*

export PYTHONPATH=src   # Windows: set PYTHONPATH=src
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 前端

```bash
cd front
pnpm install
pnpm dev
```

Vite 将 `/api` 代理到 `127.0.0.1:8000`。浏览器打开终端打印的本地地址。

---

## 助手相关接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/user/login` | 登录，返回 token |
| POST | `/api/ai/chat` | 整包回复 |
| POST | `/api/ai/chat/stream` | SSE 流式 |

请求头：`Authorization: Bearer <token>`，`Content-Type: application/json`。  
请求体示例：`{"messages":[{"role":"user","content":"..."}]}`。

---

## 固件（可选）

见 [firmware/README.md](firmware/README.md)。烧录前务必改 `config.h` 里的 Wi-Fi 与 `VERIFY_URL`，**不要提交真实密码**。

---

## 说明

- 演示默认密码仅用于本地/实验环境，上线请修改 MySQL root 与业务账号密码。
- 聊天记录默认在浏览器内存中，刷新会丢；预约与通行结果在 MySQL。
- 仓库地址：https://github.com/1109528927/lab-reservation-agent
