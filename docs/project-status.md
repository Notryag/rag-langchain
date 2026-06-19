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
- 多租户问答、聊天记录、chat run 生命周期、token 级 SSE、热点缓存、限流、操作日志、usage 统计
- pgvector retrieval / answer eval、hybrid、rerank、prompt 上下文压缩

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

- 当前仍存在旧 `/api + Chroma + Agent` 和新 `/api/v1 + pgvector + 多租户` 两条问答链路，需要继续保持主次边界。
- pgvector 多租户链路已成为产品主线，统一 retrieval DTO、chat run、token 级 SSE 和评测入口已经完成。
- 新 pgvector 产品主链路已有 retrieval / answer evaluation，但还需要在真实 PostgreSQL 数据上沉淀可对比 baseline。
- 旧链路仍有演示和 legacy eval 价值，但不应继续承载新的企业知识库能力。

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

接下来最值得投入的方向是质量基线和产品化运维闭环，而不是继续堆大功能:

1. 在真实 PostgreSQL + pgvector 数据上跑 retrieval / answer eval，沉淀 baseline manifest 和 bad cases。
2. 基于评测结果决定是否默认开启 hybrid / rerank。
3. 继续保持 `/api/v1 + pgvector` 为产品主链路，旧 `/api + Chroma + Agent` 只作为 legacy demo / eval 基线。
4. 补齐 run 查询、取消、运行耗时和更细的 usage 统计。
5. 再考虑组织、团队、RBAC、ACL 等更复杂权限模型。

详细计划见 [target-architecture.md](target-architecture.md)。
