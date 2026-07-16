# rag-langchain

多租户企业知识库 RAG 后端。当前主线是 FastAPI + SQLAlchemy 2.0 + PostgreSQL + pgvector + Redis + Celery + JWT。

旧 `/api + Chroma + CLI + Streamlit` 链路已经删除。当前问答主线是 `/api/v1 + Runtime + Agent + pgvector`: Runtime 管理 chat run 生命周期、SSE、取消和运行态查询，Agent 通过 `retrieve_context` tool 调用当前 PostgreSQL/pgvector 检索，并保留多租户权限过滤。

## 当前能力

- 用户注册、登录、JWT 鉴权
- 每个用户管理自己的知识库
- 文档上传、状态追踪、同步/异步解析
- 文档切片、embedding、pgvector 入库
- 问答时按 `user_id + kb_id` 在 SQL 层做权限过滤
- 回答返回结构化引用来源
- 聊天会话、消息、chat run、usage、操作日志
- 本地轻量 Agent run timeline，记录 tool/result/complete/error
- 外部 tracing 配置入口、token cost 估算、trace id/url 预留
- Prompt 版本列表、创建、启用和回滚 API
- `admin / user` 最小 RBAC，Prompt 管理仅管理员可用
- 文档上传大小、扩展名和 MIME 限制，分块落盘并清理失败文件
- Celery 文档任务并发抢占、有限重试、退避和执行超时
- MCP Server 示例，供外部 Agent/MCP client 复用知识库检索、文档查询和运行记录查询
- SSE 流式回答、热点问题缓存、接口限流
- pgvector retrieval / answer eval、baseline manifest、bad case 导出

## 快速开始

完整项目一键启动（PostgreSQL / Redis / FastAPI / Celery worker / React 前端静态资源）:

```powershell
docker compose up -d --build
```

打开: `http://127.0.0.1:8000`

如果容器内 API / worker 需要访问宿主机 Ollama 或兼容 OpenAI 服务，不要在 `.env` 中使用 `http://127.0.0.1:11434/v1`，应使用:

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

本机进程开发:

```powershell
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
uv run python -m app.main web
```

API 默认地址: `http://127.0.0.1:8000`

## 必要环境变量

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSION=1024
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-me-in-production
UPLOAD_DIR=./storage/uploads
MAX_UPLOAD_BYTES=20971520
```

当前主线默认使用 `bge-m3`，embedding 表结构按 `vector(1024)` 设计。如果切换到其他 embedding 模型，必须同步修改:

```env
EMBEDDING_DIMENSION=1024
```

已经建过旧维度表时，本项目不保留旧 embedding 数据兼容；请重建数据库或清空并重建 `document_chunks` 后重新处理文档，避免混用不同维度的向量。

容器访问宿主机 Ollama 时使用:

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

## 常用命令

```powershell
# 启动 FastAPI
uv run python -m app.main web

# 数据库迁移
uv run alembic upgrade head

# 单元测试
uv run python scripts/run_tests.py

# 创建 Prompt 管理员（先执行数据库迁移）
uv run python -m app.main create-admin --username admin --email admin@example.com --password "change-this-password"

# 多租户 smoke
uv run python scripts/smoke_multitenant.py --skip-chat

# pgvector 配置诊断
uv run python -m evaluation.check_pgvector_embedding_config

# pgvector baseline
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-dataset data/eval/current_kb_retrieval.jsonl --retrieval-limit 10 --skip-answer
```

## 前端

```powershell
cd frontend
npm install
npm test
npm run build
```

FastAPI 会托管 `frontend/dist/`。本地开发:

```powershell
cd frontend
npm run dev
```

前端当前通过 `/api/v1` 调用后端，已支持登录、知识库选择、文档上传、状态追踪和聊天。

## 项目结构

```text
app/
  api/          FastAPI app、/api/v1 路由、错误处理、限流
  config/       settings 与日志配置
  core/         JWT、密码、安全工具
  db/           SQLAlchemy session 与 ORM models
  memory/       LangGraph checkpointer
  mcp/          独立 MCP server 示例，不挂入 FastAPI 主进程
  retrieval/    loaders、splitter、pgvector、hybrid、rerank、引用
  runtime/      chat run 生命周期、SSE StreamBridge、取消、运行态查询
  schemas/      Pydantic schemas
  services/     认证、知识库、文档、问答、缓存、日志
  workers/      Celery app 和文档任务
evaluation/     pgvector retrieval / answer eval 与 baseline
frontend/       React + Vite 前端
migrations/     Alembic migrations; 开发阶段以当前初始 schema 为准
scripts/        smoke 脚本
tests/          单元测试与 API 测试
docs/           架构、运行、规划、待办
```

## 文档导航

- AI 助手上下文入口: [docs/ai-context.md](docs/ai-context.md)
- 架构说明: [docs/architecture.md](docs/architecture.md)
- 目标架构与收口计划: [docs/target-architecture.md](docs/target-architecture.md)
- RAG runtime 适配规格: [RAG_RUNTIME_SPEC.md](RAG_RUNTIME_SPEC.md)
- 开发与运行约定: [docs/development.md](docs/development.md)
- 多租户企业知识库 RAG 规划: [docs/multitenant-rag.md](docs/multitenant-rag.md)
- 入库策略: [docs/ingestion.md](docs/ingestion.md)
- 质量评测闭环: [docs/evaluation.md](docs/evaluation.md)
- 项目现状: [docs/project-status.md](docs/project-status.md)
- 路线图: [docs/roadmap.md](docs/roadmap.md)
- 项目发展计划: [docs/development-plan.md](docs/development-plan.md)
- 待办清单: [docs/todo.md](docs/todo.md)
- 已完成清单归档: [docs/todo-done.md](docs/todo-done.md)
- 面试亮点与演示路径: [docs/interview-highlights.md](docs/interview-highlights.md)
