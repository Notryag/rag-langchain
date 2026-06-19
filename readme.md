# rag-langchain

一个用于“本地知识库问答”的 LangChain RAG 示例项目，适合做 PoC、课程演示和小型内部助手。

## 这个项目能做什么

- 把本地文档（TXT/MD/PDF/DOCX/HTML）切分并写入 Chroma 向量库
- 用 Agent + Tool 进行检索增强问答（RAG）
- 在回答中输出引用来源
- 支持 CLI 交互、Streamlit 页面和 FastAPI Web 控制台
- 提供基础离线评测脚本（retrieval / answer）

## 5 分钟快速开始

### 1) 安装依赖

```bash
uv sync
```

### 2) 配置环境变量（`.env`）

最少需要：

```env
OPENAI_API_KEY=your_key
# 可选：兼容网关/本地服务
# OPENAI_BASE_URL=http://xxx/v1
```

可选模型参数（不填有默认值）：

```env
CHAT_MODEL=gpt-4.1-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
CHECKPOINTER_TYPE=sqlite
CHECKPOINTER_SQLITE_PATH=./storage/checkpoints.sqlite3
FEEDBACK_LOG_PATH=./storage/feedback.jsonl
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/rag
REDIS_URL=redis://localhost:6379/0
```

### 3) 导入本地知识库

```bash
uv run python -m app.main ingest --data-dir ./data/raw
```

### 4) 启动对话

CLI:

```bash
uv run python -m app.main cli
```

Web:

```bash
uv run python -m app.main streamlit
```

FastAPI Web:

```bash
cd frontend
npm install
npm run build
cd ..
uv run python -m app.main web
```

启动后打开 `http://127.0.0.1:8000`，FastAPI 会托管 React 构建产物。

React 前端开发:

```bash
cd frontend
npm install
npm run dev
```

开发服务默认打开 `http://127.0.0.1:5173`，并代理 `/api` 到 FastAPI。

GitHub Pages 预览:

- 推送到 `master`/`main` 后，`.github/workflows/frontend-pages.yml` 会构建并发布 `frontend/`。
- Pages 只托管 React 静态页面；完整问答需要单独部署 FastAPI。
- 如果已有公开 API 地址，可在 GitHub 仓库变量中设置 `VITE_API_BASE_URL`。

## 常用命令

```bash
# 检索评测
uv run python -m evaluation.evaluate_retrieval --limit 10

# 删除单个文档索引
uv run python -m app.main delete-source 维护保养.txt

# 查看基础运行指标
curl http://127.0.0.1:8000/api/metrics

# 启动 PostgreSQL + Redis
docker compose up -d postgres redis

# 一键启动多租户后端: PostgreSQL + Redis + FastAPI + Celery worker
docker compose up -d

# 执行数据库迁移
uv run alembic upgrade head

# 多租户端到端 smoke
uv run python scripts/smoke_multitenant.py --skip-chat

# 采样生成回答
uv run python -m evaluation.generate_answers --limit 10

# 回答评测
uv run python -m evaluation.evaluate_answers --limit 10
```

如果容器要访问宿主机上的 Ollama，请在 `.env` 中使用 `OPENAI_BASE_URL=http://host.docker.internal:11434/v1`。使用 `bge-m3` 时同时设置 `EMBEDDING_DIMENSION=1024`。

## 项目结构（简版）

```text
app/
  agent/       # Agent 装配、prompt 与 middleware
  retrieval/   # 入库、向量库、检索、引用格式化
  tools/       # 暴露给 Agent 的工具
  services/    # 业务编排（UI / CLI 共用）
  api/         # FastAPI 接口与 Web 静态资源托管
  cli/         # 命令行入口
frontend/      # React + Vite + TypeScript 前端
evaluation/    # 离线评测脚本
data/          # 原始数据与评测数据
docs/          # 架构、路线图、开发说明
```

## 文档导航

- AI 助手上下文入口: [docs/ai-context.md](docs/ai-context.md)
- 目标架构与收口计划: [docs/target-architecture.md](docs/target-architecture.md)
- 架构说明: [docs/architecture.md](docs/architecture.md)
- 多租户企业知识库 RAG 规划: [docs/multitenant-rag.md](docs/multitenant-rag.md)
- 架构评审: [docs/architecture-review.md](docs/architecture-review.md)
- 开发与运行约定: [docs/development.md](docs/development.md)
- 入库策略: [docs/ingestion.md](docs/ingestion.md)
- Hybrid Search 需求评估: [docs/hybrid-search-evaluation.md](docs/hybrid-search-evaluation.md)
- 项目现状: [docs/project-status.md](docs/project-status.md)
- 路线图: [docs/roadmap.md](docs/roadmap.md)
- 待办清单: [docs/todo.md](docs/todo.md)
- 已完成清单归档: [docs/todo-done.md](docs/todo-done.md)

## 适用场景

- 说明书/FAQ 问答
- 售后支持知识助手
- 企业内部知识检索问答

---

如果你是第一次接触这个仓库，推荐顺序：
1. 先按“快速开始”跑通 ingest + cli。
2. 再看 `docs/architecture.md` 理解主链路。
3. 最后跑一次 `evaluation` 看质量基线。
