# AI 助手上下文入口

这份文档给代码助手使用。目标是用最少上下文理解项目，不要一开始读取所有文档。

## 先读这几份

每次接手任务时，优先按顺序读取:

1. [../AGENTS.md](../AGENTS.md): 仓库内工作规则、代码落点和提交前检查。
2. [architecture.md](architecture.md): 当前分层、边界和关键文件映射。
3. [target-architecture.md](target-architecture.md): 当前主架构决策、旧链路定位和收口计划。
4. [todo.md](todo.md): 当前待办、已完成批次和近期方向。

只有当任务需要时，再按下面的路由继续读取。

## 按任务渐进读取

### 运行、配置、Docker、迁移

读取:

- [development.md](development.md)
- [.env.example](../.env.example)
- [docker-compose.yml](../docker-compose.yml)
- [alembic.ini](../alembic.ini)
- `migrations/versions/`

常见问题:

- 本地统一使用 `uv run ...`。
- Docker 容器访问宿主机 Ollama 时使用 `http://host.docker.internal:11434/v1`。
- 使用 `bge-m3` embedding 时，`EMBEDDING_DIMENSION` 通常应为 `1024`。

### 多租户 API、认证、权限隔离

读取:

- [target-architecture.md](target-architecture.md)
- [multitenant-rag.md](multitenant-rag.md)
- [development.md](development.md) 的多租户 API 章节
- `app/api/v1/`
- `app/services/auth_service.py`
- `app/services/kb_service.py`
- `app/services/document_service.py`
- `app/services/chat_service.py`
- `app/db/models/`

关键原则:

- 所有知识库、文档、chunk、聊天会话都必须按当前用户过滤。
- 向量检索权限过滤必须进入 SQL 条件，不能先全局召回再应用层过滤。
- `/api/v1` 是产品化多租户接口；旧 `/api` 仍服务原本本地 RAG / React 控制台链路。

### 文档上传、异步处理、pgvector

读取:

- [multitenant-rag.md](multitenant-rag.md)
- [ingestion.md](ingestion.md)
- `app/api/v1/documents.py`
- `app/services/document_service.py`
- `app/workers/tasks.py`
- `app/retrieval/parser.py`
- `app/retrieval/pgvector_store.py`

关键路径:

```text
upload -> documents(pending) -> Celery task -> parse -> split -> embedding -> document_chunks -> completed/failed
```

### 问答、引用、聊天记录、SSE、缓存

读取:

- [development.md](development.md) 的多租户问答 API 章节
- `app/api/v1/chat.py`
- `app/services/chat_service.py`
- `app/services/hot_question_cache.py`
- `app/retrieval/pgvector_store.py`
- `app/db/models/chat.py`

当前行为:

- 问答保存 user / assistant 两类消息。
- assistant 消息保存结构化 `references`。
- 同步接口返回 `answer / references / session_id / run_id / usage`。
- SSE 接口由 `ChatService.stream()` 驱动，返回 `answer_delta`、`complete`、`error` 事件。
- 每次问答都会创建 `chat_runs`，operation log 围绕 `chat_run` 聚合，并在 details 中保留 `session_id`。
- 热点问题缓存按 `user_id + kb_id + question + top_k + 模型配置` 隔离。

### 旧本地 RAG、Agent、Tool、Chroma

读取:

- [target-architecture.md](target-architecture.md)
- [architecture.md](architecture.md)
- [ingestion.md](ingestion.md)
- [hybrid-search-evaluation.md](hybrid-search-evaluation.md)
- `app/services/rag_service.py`
- `app/services/chat_client.py`
- `app/agent/`
- `app/tools/retrieve_context.py`
- `app/retrieval/`

注意:

- 旧链路仍使用 Chroma 和 Agent tool。
- 多租户产品化链路使用 PostgreSQL + pgvector。
- 不要把这两条链路混成一个大函数；迁移时保持边界清楚。

### 检索质量、评测、rerank、hybrid

读取:

- [hybrid-search-evaluation.md](hybrid-search-evaluation.md)
- [architecture-review.md](architecture-review.md)
- `evaluation/`
- `app/retrieval/hybrid.py`
- `app/retrieval/reranker.py`
- `app/retrieval/retriever.py`
- `evaluation/evaluate_pgvector_retrieval.py`

验证建议:

- 改检索或回答逻辑时，至少跑相关 evaluation。
- 多租户主链路 pgvector retrieval eval 需要显式传 `--user-id` 和 `--kb-id`。
- 没有评测前不要靠感觉反复调 prompt。

### 前端、React、静态托管

读取:

- [development.md](development.md) 的 React 前端章节
- `frontend/`
- `app/api/main.py`

当前关系:

- Vite 开发服务代理 `/api` 到 FastAPI。
- `frontend/dist/` 存在时，FastAPI 托管构建产物。
- GitHub Pages 只适合预览静态前端，完整问答仍需要后端。

## 代码结构速览

```text
app/
  api/          FastAPI app、旧 /api、产品化 /api/v1、错误处理、限流
  agent/        旧本地 RAG Agent 装配、prompt、策略
  cli/          CLI 入口
  config/       settings 与日志配置
  core/         安全/JWT/密码工具
  db/           SQLAlchemy Base、session、ORM models
  memory/       LangGraph checkpointer
  middleware/   Agent runtime prompt middleware
  retrieval/    加载、切分、Chroma、pgvector、hybrid、rerank、引用
  schemas/      Pydantic schemas
  services/     业务编排、认证、知识库、文档、问答、缓存、日志
  tools/        Agent 可调用 tools
  workers/      Celery app 和文档任务
evaluation/     retrieval / answer eval 与 trace
frontend/       React + Vite 前端
migrations/     Alembic migrations
scripts/        端到端 smoke 脚本
tests/          单元测试与 API 测试
docs/           架构、运行、规划、待办
```

## 修改落点规则

- 新业务流程优先放 `app/services/`。
- 新检索能力优先放 `app/retrieval/`。
- 新 HTTP 接口优先放 `app/api/v1/`，旧本地 RAG API 仍在 `app/api/routes.py`。
- 新数据库结构要同步 ORM model、Alembic migration 和模型测试。
- 新配置要同步 `app/config/settings.py`、`.env.example`、`docker-compose.yml` 和 [development.md](development.md)。
- 新文档要同步 README 文档导航，必要时同步本文件。

## 推荐最小检查

按改动类型选择，不要机械全跑:

- 文档/导航: 检查 README 与 docs 导航一致。
- API/service: `uv run python -m unittest discover -s tests`
- 数据库/migration: `uv run alembic upgrade head`
- Docker/Compose: `docker compose config`
- 多租户主链路: `uv run python scripts/smoke_multitenant.py --skip-chat`
- 检索/回答质量: `uv run python -m evaluation.evaluate_retrieval` 或相关 evaluation 命令。

## 当前长期方向

第二阶段后端增强已经基本完成。后续先做架构收口，再进入第三阶段能力增强:

- 统一 retrieval interface
- chat run 生命周期
- 真正 token 级 SSE
- pgvector 多租户评测
- 混合检索: 关键词 + 向量
- 重排序 rerank
- 上下文压缩
- 召回率评估
- 更细粒度权限过滤
- 更真实的 token 级流式回答
- 组织 / 团队 / RBAC / ACL
