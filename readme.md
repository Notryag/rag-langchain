# rag-langchain

多租户企业知识库 RAG 后端。当前主线是 FastAPI + SQLAlchemy 2.0 + PostgreSQL + pgvector + Redis + Celery + JWT。

旧 `/api + Chroma + Agent + CLI + Streamlit` 链路已经删除。新增能力默认进入 `/api/v1`、`app/services/`、`app/retrieval/` 和数据库模型。

## 当前能力

- 用户注册、登录、JWT 鉴权
- 每个用户管理自己的知识库
- 文档上传、状态追踪、同步/异步解析
- 文档切片、embedding、pgvector 入库
- 问答时按 `user_id + kb_id` 在 SQL 层做权限过滤
- 回答返回结构化引用来源
- 聊天会话、消息、chat run、usage、操作日志
- SSE 流式回答、热点问题缓存、接口限流
- pgvector retrieval / answer eval、baseline manifest、bad case 导出

## 快速开始

```powershell
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
uv run python -m app.main web
```

完整后端一键启动:

```powershell
docker compose up -d
```

API 默认地址: `http://127.0.0.1:8000`

## 必要环境变量

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=change-me-in-production
UPLOAD_DIR=./storage/uploads
```

如果使用本地 `bge-m3`，通常需要:

```env
EMBEDDING_DIMENSION=1024
```

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
uv run python -m unittest discover -s tests

# 多租户 smoke
uv run python scripts/smoke_multitenant.py --skip-chat

# pgvector 配置诊断
uv run python -m evaluation.check_pgvector_embedding_config

# pgvector baseline
uv run python -m evaluation.run_pgvector_baseline --user-id 1 --kb-id 1 --retrieval-limit 10 --skip-answer
```

## 前端

```powershell
cd frontend
npm install
npm run build
```

FastAPI 会托管 `frontend/dist/`。本地开发:

```powershell
cd frontend
npm run dev
```

前端当前通过 `/api/v1` 调用后端。现阶段仍是调试形态，聊天需要设置:

```env
VITE_API_TOKEN=<access_token>
VITE_KB_ID=<kb_id>
```

下一步会补齐登录、知识库选择、文档上传和状态追踪，详见 [docs/todo.md](docs/todo.md)。

## 项目结构

```text
app/
  api/          FastAPI app、/api/v1 路由、错误处理、限流
  config/       settings 与日志配置
  core/         JWT、密码、安全工具
  db/           SQLAlchemy session 与 ORM models
  memory/       LangGraph checkpointer
  retrieval/    loaders、splitter、pgvector、hybrid、rerank、引用
  schemas/      Pydantic schemas
  services/     认证、知识库、文档、问答、缓存、日志
  workers/      Celery app 和文档任务
evaluation/     pgvector retrieval / answer eval 与 baseline
frontend/       React + Vite 前端
migrations/     Alembic migrations
scripts/        smoke 脚本
tests/          单元测试与 API 测试
docs/           架构、运行、规划、待办
```

## 文档导航

- AI 助手上下文入口: [docs/ai-context.md](docs/ai-context.md)
- 架构说明: [docs/architecture.md](docs/architecture.md)
- 目标架构与收口计划: [docs/target-architecture.md](docs/target-architecture.md)
- 开发与运行约定: [docs/development.md](docs/development.md)
- 多租户企业知识库 RAG 规划: [docs/multitenant-rag.md](docs/multitenant-rag.md)
- 入库策略: [docs/ingestion.md](docs/ingestion.md)
- 项目现状: [docs/project-status.md](docs/project-status.md)
- 路线图: [docs/roadmap.md](docs/roadmap.md)
- 待办清单: [docs/todo.md](docs/todo.md)
- 已完成清单归档: [docs/todo-done.md](docs/todo-done.md)
