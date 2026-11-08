# 智能实验室预约通行系统 · Agent 主入口版

> **本目录是副本工程**（位于 `D:\全栈`）：从 `D:\edu\智能实验室预约通行系统` 备份而来，用于毕设「助手为主入口、页面可降级」实验，不覆盖原项目。  
> 登录默认进入助手；预约/签须知/领码尽量在对话内确认后办理；助手不可用时仍走表单菜单。  
> 技术栈：**Vue3 + FastAPI + MySQL + Redis + LangChain Tool + LangGraph**（硬件：ESP32-S3 + 串口二维码扫码模块 + 蜂鸣器）

## 为什么用这套栈

与本人 `D:\全栈\全部知识点`、`等保实验agent注册登录模块备份` 同一路线，便于开发与答辩讲解；Agent/LangGraph 在 Python 侧原生集成。

## 目录

见 `docs/00-目录说明.md`。知识点对照见 `D:\全栈\全部知识点\06-项目对照-智能实验室预约通行\`。

## 快速启动（登录注册已就位）

### 1) 数据库

MySQL 执行 `backend/sql/01_init.sql`（库名 `lab_access`）。

### 2) 后端

```bash
cd backend
copy .env.example .env
# 按需改 DATABASE_URL
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
set PYTHONPATH=src
uvicorn main:app --reload --port 8000
```

### 3) 前端

```bash
cd front
pnpm install
pnpm run dev
```

浏览器打开 Vite 地址 → 注册学生账号 → 登录进入 Layout。

## 阶段

| 阶段 | 内容 | 状态 |
|------|------|------|
| A0 | 工程骨架 + 登录注册 | ✅ 已完成（本机可登录） |
| A1 | 实验室 + 预约冲突 + 审批 | ✅ 已完成（本机有数据） |
| A2 | 须知 + 凭证 + 核验 + 模拟门 | ✅ 已完成（冒烟全流程通过） |
| A3 | 管理看板 + 消息/信用/报修闭环 | ✅ 已完成 |
| A4 | Agent + LangGraph | ✅ 已完成（助手对话正常） |
| A4b | 制度 RAG（FAISS：须知/开放/管理员） | ✅ 已接入 `search_lab_docs` |
| A4c | 管理员 AI 辅助审批（低风险可自动过） | ✅ `ai_review` / `auto_process_pending` |
| M1 | 学生端小程序态 H5（`/m`） | ✅ 页面已铺，待真机验收 |
| B1 | ESP32-S3 + 串口二维码扫码模块 | 硬件待做；verify 接口已就绪 |

### 制度文档 RAG（FAISS）

语料在 `backend/kb_source/`（安全须知、开放规则、管理员联系、实验室专篇）。  
预约空闲仍走业务 Tool；问规则/安全/找谁时助手调 `search_lab_docs`。

```bash
# 推荐：单独用 Python 3.12 隔离环境装 faiss-cpu（不要用 3.13 的旧 .venv）
# WSL / Linux 示例：
uv venv ~/venvs/lab-faiss-py312 --python 3.12
source ~/venvs/lab-faiss-py312/bin/activate
cd backend
uv pip install -r requirements.txt --index-url https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com
export PYTHONPATH=src
python scripts/build_faiss_kb.py
# 看到 backend.json 里 "backend": "faiss" 即真·FAISS
```

索引目录：`backend/data/faiss_lab/`（含 `index.faiss`；可本地生成）。  
若坚持用 Python 3.13 且装不上 faiss-cpu，代码会降级 numpy 内积；隔离换成 3.12 后即可走真 FAISS。  
自测：登录助手问「安全须知有哪些禁止事项」「管理员联系谁」「周末开吗」。改完工具后请重启后端以清图缓存。  
日常跑 uvicorn 也可：`PYTHONPATH=src ~/venvs/lab-faiss-py312/bin/uvicorn main:app --reload --port 8000`（在 backend 目录）。

### 管理员 AI 辅助审批

管理员登录助手可用：`list_pending_reservations`、`ai_review_reservation`（规则+AI建议，默认不改库）、`auto_process_pending`（仅自动通过低风险高置信；存疑进 need_human，不自动驳回）、`apply_reservation_decision`（明确通过/驳回）。  
硬条件：时长≤4h、信用≥60、非深夜。  
资格路径（满足其一）：用途合格；或历史成功预约≥2（可调 `LAB_AUTO_APPROVE_MIN_HISTORY`）；或工号在白名单 `data/trusted_employee_nos.txt`（助手可 `add_trusted_employee_no`）。  
再叠加 AI 建议 approve 且置信度≥0.75 才自动通过。页面原审批按钮仍可用。  
测法：录入工号 → 该学生提单 → 管理员 dry_run / 自动过；或同一学生多次通过后再提一笔看「历史路径」。

进度详表：`docs/09-任务推进计划书.md`（会随你反馈实时更新）

## 参考

- 登录注册完整步骤：等保备份里的 `登录注册可复用完整笔记.md`  
- LangGraph：`全部知识点/03-Agent/LangGraph/01-LangGraph详解.md`
