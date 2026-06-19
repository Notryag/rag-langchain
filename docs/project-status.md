# 项目现状

## 项目阶段

当前项目不是从 0 到 1 的空壳，而是已经具备最小可用闭环的本地 RAG 工程，并已经完成多租户企业知识库 RAG 后端的第一、第二阶段主体能力。

已落地的链路包括:

- 文档加载、切分、去重、入库
- Embeddings 与 Chroma 向量库初始化
- 检索、格式化、引用提取
- Tool 化检索能力
- Agent 构建与流式对话
- CLI 交互
- Streamlit 演示界面
- FastAPI API 与 React Web 控制台
- SQLAlchemy / Alembic / PostgreSQL / pgvector 的多租户数据层地基
- JWT 认证、知识库 CRUD、文档上传与状态追踪
- Celery 异步文档处理
- pgvector 入库、权限过滤检索、结构化引用
- 多租户问答、聊天记录、SSE、热点缓存、限流、操作日志、usage 统计

这意味着项目当前的主要问题已经不是“能不能跑起来”，而是“怎么稳定变好、怎么长期维护”。

## 已有模块

核心模块现状:

- `app/retrieval/ingest.py`: 文档处理与入库主链路
- `app/retrieval/vectorstore.py`: Embeddings 与向量库初始化
- `app/retrieval/retriever.py`: 检索与引用格式化
- `app/tools/retrieve_context.py`: Agent 调用的检索工具
- `app/agent/create_agent.py`: Agent 构建入口
- `app/services/chat_client.py`: 聊天请求与流式事件编排
- `app/cli/main.py`: 命令行交互入口
- `app/streamlit_app.py`: Streamlit 演示界面
- `app/api/`: FastAPI API 与 React 构建产物托管
- `frontend/`: React + Vite + TypeScript Web 控制台
- `evaluation/`: 顶层离线评测与 trace 工具目录
- `app/db/`: 多租户业务数据模型与 session provider
- `migrations/`: Alembic migration 环境

## 当前优点

- 主链路完整，已经具备继续迭代的基础。
- retrieval、tool、agent、service 已经有初步分层，不完全是脚本堆叠。
- 已经支持引用展示和流式输出，这对调试和用户感知都很重要。
- 当前数据集和场景相对集中，适合走垂直知识助手路线。

## 当前不足

- 当前存在旧 `/api + Chroma + Agent` 和新 `/api/v1 + pgvector + 多租户` 两条问答链路。
- pgvector 多租户链路已成为产品主线，但检索接口还没有统一抽象。
- `/api/v1` SSE 仍是回答完成后的分块输出，还不是真正 token 级 streaming。
- 聊天记录有 session/message，但还缺少一次问答运行的 run 生命周期模型。
- 新 pgvector 产品主链路还缺独立 retrieval / answer evaluation。

## 当前目录判断

当前实际核心结构如下:

```text
app/
  agent/
  cli/
  config/
  db/
  middleware/
  retrieval/
  services/
  tools/
evaluation/
data/
  raw/
storage/
migrations/
```

这是合理的工程骨架。当前主要风险不是目录缺失，而是旧本地 RAG 链路和新多租户产品链路需要明确主次并逐步收口。

## 当前最重要的结论

接下来最值得投入的方向是架构收口，而不是继续堆产品功能:

1. 明确 `/api/v1 + pgvector` 是产品主链路。
2. 将旧 `/api + Chroma + Agent` 定位为 legacy demo / eval 基线。
3. 抽统一 retrieval interface，避免两套检索逻辑继续分叉。
4. 增加 chat run 生命周期，聚合 status、usage、cache_hit、error。
5. 将 SSE 从 API 层伪流式升级为 service 层 token 级 streaming。
6. 给 pgvector 多租户链路补 retrieval / answer evaluation。

详细计划见 [target-architecture.md](target-architecture.md)。
