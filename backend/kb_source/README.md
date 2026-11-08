# 实验室制度 / 须知语料（FAISS RAG）

本目录 markdown 供助手 `search_lab_docs` 检索。
结构化数据（空闲、预约、通行码）仍走业务 Tool；这里只放说明类文档。

## 约定

- `general/`：全校通用规则、安全须知、管理员总览
- `labs/`：单个实验室补充（文件名可含实验室关键词，检索时可按 lab 过滤）
- 改完语料后执行：`python scripts/build_faiss_kb.py`

## 与工单项目对比

语料少、单机演示用 **FAISS**；工单手册多、要独立服务与类别过滤用 **Milvus**。选型按场景，不是谁更高级。
