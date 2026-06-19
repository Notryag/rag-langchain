# 开发与运行约定

如果你是 AI 助手，不确定该读哪些文档时，先看 [ai-context.md](ai-context.md)。本文只负责运行、配置、API 使用和本地验证细节。

## Python 环境

本项目统一使用 `uv` 执行命令，不直接写死 `.venv\Scripts\python.exe`，也不建议直接使用系统 `python`。

推荐方式:

```powershell
uv run python -m evaluation.evaluate_retrieval --limit 2
```

原因:

- `uv` 会自动使用项目环境与锁文件
- 不需要手动关心 `.venv` 路径
- 能减少“系统 python 缺依赖”这类问题
- 当前仓库已经验证 `uv run` 可以直接执行评测命令

## 环境准备

首次拉起项目时，先同步依赖:

```powershell
uv sync
```

后续运行脚本时，统一使用:

```powershell
uv run python -m <module>
```

## 环境变量策略

- `OPENAI_API_KEY` 是必填项，即使接本地兼容服务也需要显式提供一个非空值。
- `OPENAI_BASE_URL` 是可选项；走官方 OpenAI 可留空，走兼容网关或本地模型服务时填写。
- `CHAT_MODEL`、`EMBEDDING_MODEL`、`VECTOR_DB_DIR`、`COLLECTION_NAME`、`LOG_DIR`、`LOG_FILE_NAME` 都有默认值，但不允许为空字符串。
- `EMBEDDING_DIMENSION` 默认 `1536`，必须和当前 embedding 模型输出维度一致；例如 `text-embedding-3-small` 是 `1536`，`bge-m3` 通常是 `1024`。
- `TOP_K`、`RETRIEVAL_FETCH_K`、`CHUNK_SIZE` 必须大于 `0`。
- `RETRIEVAL_MAX_CONTEXT_CHARS` 必须大于 `0`，用于限制传给模型的检索上下文字符数。
- `CHUNK_OVERLAP` 必须大于等于 `0`，且必须小于 `CHUNK_SIZE`。
- `RETRIEVAL_SEARCH_TYPE` 当前支持 `similarity`、`mmr` 和 `hybrid`。
- `RETRIEVAL_FETCH_K` 必须大于等于 `TOP_K`。
- `RERANKER_ENABLED` 是可选布尔开关，默认 `false`。
- `RERANKER_STRATEGY` 当前只支持 `embedding_lexical`。
- `LOG_LEVEL` 当前只支持 `CRITICAL`、`ERROR`、`WARNING`、`INFO`、`DEBUG`。
- `CHECKPOINTER_TYPE` 当前支持 `sqlite` 和 `memory`，默认 `sqlite`，用于保存多轮会话状态。
- `CHECKPOINTER_SQLITE_PATH` 默认 `./storage/checkpoints.sqlite3`，仅在 `CHECKPOINTER_TYPE=sqlite` 时使用。
- `FEEDBACK_LOG_PATH` 默认 `./storage/feedback.jsonl`，用于保存 Web/API 提交的回答反馈。
- `DATABASE_URL` 默认 `postgresql+psycopg://rag:rag@localhost:5432/rag`，用于多租户业务数据和后续 pgvector 检索。
- `REDIS_URL` 默认 `redis://localhost:6379/0`。
- `CELERY_BROKER_URL` 默认 `redis://localhost:6379/1`。
- `CELERY_RESULT_BACKEND` 默认 `redis://localhost:6379/2`。
- `JWT_SECRET_KEY` 默认值仅适合本地开发，生产环境必须替换。
- `ACCESS_TOKEN_EXPIRE_MINUTES` 默认 `60`。
- `UPLOAD_DIR` 默认 `./storage/uploads`，用于保存上传原始文件。
- `RATE_LIMIT_ENABLED` 默认 `true`，用于开启 `/api/v1` 接口限流。
- `RATE_LIMIT_REQUESTS` 默认 `60`，表示一个窗口内允许的请求数。
- `RATE_LIMIT_WINDOW_SECONDS` 默认 `60`，表示限流窗口秒数。
- `HOT_QUESTION_CACHE_ENABLED` 默认 `true`，用于缓存同一用户同一知识库的热点问题回答。
- `HOT_QUESTION_CACHE_TTL_SECONDS` 默认 `300`，表示热点问题缓存有效期秒数。
- 入库当前支持 `.txt`、`.md`、`.pdf`、`.docx`、`.html`、`.htm`。

## 常用评测命令

### 数据库服务

仅启动 PostgreSQL + Redis 依赖:

```powershell
docker compose up -d postgres redis
uv run alembic upgrade head
```

当前 Alembic migration 环境已经接入 SQLAlchemy metadata。新增或修改 ORM 模型后，使用:

```powershell
uv run alembic revision --autogenerate -m "message"
```

### Celery Worker

本地开发时，启动 Redis 后，可以启动文档处理 worker:

```powershell
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

上传文档成功后，API 会尝试投递 `documents.process` 任务。若 Redis / broker 暂不可用，上传记录仍会保留为 `pending`，可以稍后通过同步处理入口重试。

### API smoke tests

```powershell
uv run python -m unittest tests.test_api
```

### 多租户端到端 Smoke

方式一：一键启动完整后端（PostgreSQL / Redis / FastAPI / Celery worker）:

```powershell
docker compose up -d
uv run python scripts/smoke_multitenant.py
```

`api` 服务启动时会自动执行 `alembic upgrade head`，然后监听 `http://127.0.0.1:8000`。

如果容器内 API / worker 需要访问宿主机上的 Ollama 或兼容 OpenAI 服务，不要在 `.env` 里使用 `http://127.0.0.1:11434/v1`，应改为:

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

方式二：本机进程调试。先启动依赖和数据库迁移:

```powershell
docker compose up -d postgres redis
uv run alembic upgrade head
```

再分别启动 API 和 Celery worker:

```powershell
uv run python -m app.main web
uv run celery -A app.workers.celery_app.celery_app worker --loglevel=INFO
```

执行端到端 smoke:

```powershell
uv run python scripts/smoke_multitenant.py
```

如果使用本地 `bge-m3` embedding，请确保 `.env` 或当前 shell 中设置:

```env
EMBEDDING_DIMENSION=1024
```

Docker Compose 的 `api` / `worker` 服务会读取 `.env` 中的模型配置，并自动把数据库和 Redis 地址改为容器内部服务名。

修改 embedding 维度后，需要重新执行:

```powershell
uv run alembic upgrade head
```

如果数据库中已经存在旧维度的 pgvector 列，Compose 环境也需要重新运行迁移，必要时清理本地 `postgres_data` volume 后重建开发环境。

该脚本会依次执行:

1. 健康检查
2. 用户注册 / 登录
3. 创建知识库
4. 上传 txt 文档
5. 等待异步处理完成
6. 如果异步处理未完成，默认调用同步处理接口兜底
7. 调用问答接口并检查 references
8. 查询聊天会话和消息记录

如果当前环境没有可用模型配置，可先跳过问答调用，只验证认证、知识库、上传和处理链路:

```powershell
uv run python scripts/smoke_multitenant.py --skip-chat
```

本地模型首次推理较慢时，可以调大请求超时:

```powershell
uv run python scripts/smoke_multitenant.py --request-timeout 240
```

### 检索评测

```powershell
uv run python -m evaluation.evaluate_retrieval
uv run python -m evaluation.evaluate_retrieval --limit 10
uv run python -m evaluation.evaluate_retrieval --search-type similarity mmr --top-k 3 5 --fetch-k 8 12
uv run python -m evaluation.evaluate_retrieval --show-passes
uv run python -m evaluation.evaluate_retrieval --search-type similarity --top-k 3 --fetch-k 8 --reranker off on
uv run python -m evaluation.evaluate_retrieval --search-type hybrid --top-k 3 --fetch-k 8 --reranker off on
uv run python -m evaluation.evaluate_retrieval --source 扫地机器人100问2.txt
uv run python -m evaluation.evaluate_retrieval --metadata-filter-json '{"source":"维护保养.txt"}'
uv run python -m evaluation.evaluate_retrieval --limit 10 --manifest-output storage/exports/retrieval_eval_manifest.json
uv run python -m evaluation.evaluate_hybrid_need --show-failures
uv run python -m evaluation.evaluate_hybrid_search --show-changes
```

### 采样回答

```powershell
uv run python -m evaluation.generate_answers --limit 5
```

### 回答评测

```powershell
uv run python -m evaluation.evaluate_answers --limit 5
uv run python -m evaluation.evaluate_answers --show-passes
uv run python -m evaluation.evaluate_answers --bad-cases-out data/eval/bad_cases.jsonl
```

### 抓取单次 Trace

```powershell
uv run python -m evaluation.capture_trace "扫地机器人连不上WiFi怎么办"
```

## 统一入口

常用启动方式现在可以统一走 `app.main`:

```powershell
uv run python -m app.main cli
uv run python -m app.main ingest --data-dir ./data/raw
uv run python -m app.main ingest --data-dir ./data/raw --mode rebuild
uv run python -m app.main delete-source 维护保养.txt
uv run python -m app.main streamlit
uv run python -m app.main web
```

如果需要自定义 Streamlit 地址或端口:

```powershell
uv run python -m app.main streamlit --server-address 0.0.0.0 --server-port 8501
```

如果需要自定义 FastAPI Web 地址或端口:

```powershell
uv run python -m app.main web --host 0.0.0.0 --port 8000
uv run python -m app.main web --reload
```

## React 前端

前端位于 `frontend/`，使用 React + Vite + TypeScript。开发时先启动 FastAPI:

```powershell
uv run python -m app.main web
```

另开终端启动 Vite:

```powershell
cd frontend
npm install
npm run dev
```

Vite 默认地址为 `http://127.0.0.1:5173`，`/api` 会代理到 `http://127.0.0.1:8000`。

生产构建:

```powershell
cd frontend
npm run build
```

构建产物位于 `frontend/dist/`。当该目录存在时，FastAPI Web 入口会优先托管 React 构建产物。

## GitHub Pages 预览

仓库内置 `.github/workflows/frontend-pages.yml`，推送到 `master` 或 `main` 后会构建 `frontend/` 并发布到 GitHub Pages。

Pages 只适合预览 React 静态界面。完整 RAG 问答需要 FastAPI 后端运行在可访问的服务上。如果已经部署了后端，可在 GitHub 仓库变量中设置:

```text
VITE_API_BASE_URL=https://your-api.example.com
```

本地开发不需要设置该变量，Vite 会继续代理 `/api` 到 `http://127.0.0.1:8000`。

## API 检索参数

`POST /api/chat` 与 `POST /api/chat/stream` 支持可选 `retrieval_profile`，用于单次请求覆盖默认检索策略:

```json
{
  "message": "扫地机器人连不上 WiFi 怎么办？",
  "thread_id": "web_xxx",
  "retrieval_profile": {
    "search_type": "mmr",
    "top_k": 4,
    "fetch_k": 10,
    "reranker_enabled": true,
    "max_context_chars": 3000
  }
}
```

不传时使用 `.env` / `settings` 中的默认检索配置。

React Web 控制台侧栏提供对应的检索设置面板，发送消息时会随请求带上当前 profile。

## 多租户认证 API

新的产品化接口从 `/api/v1` 开始。认证接口:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

注册请求:

```json
{
  "username": "alice",
  "email": "alice@example.com",
  "password": "password-123"
}
```

登录请求:

```json
{
  "username_or_email": "alice",
  "password": "password-123"
}
```

登录响应会返回 `access_token`。后续 `/api/v1` 业务接口通过 Bearer Token 鉴权:

```text
Authorization: Bearer <access_token>
```

## 多租户知识库 API

知识库接口:

```text
POST   /api/v1/kbs
GET    /api/v1/kbs
GET    /api/v1/kbs/{kb_id}
PUT    /api/v1/kbs/{kb_id}
DELETE /api/v1/kbs/{kb_id}
```

所有接口都依赖当前登录用户，只能访问当前用户自己的知识库。

创建请求:

```json
{
  "name": "产品知识库",
  "description": "产品说明、售后和故障排查资料"
}
```

## 多租户文档 API

文档接口:

```text
POST   /api/v1/kbs/{kb_id}/documents
GET    /api/v1/kbs/{kb_id}/documents
GET    /api/v1/documents/{document_id}
DELETE /api/v1/documents/{document_id}
POST   /api/v1/documents/{document_id}/process
```

上传接口使用 `multipart/form-data`，字段名为 `file`。上传成功后保存原始文件、创建 `documents` 记录，初始状态为 `pending`，并尝试投递 Celery 异步处理任务。

同步处理入口会加载原始文件并更新状态:

```text
pending -> processing -> completed
pending -> processing -> failed
```

当前同步处理会完成解析、切片、embedding 和 pgvector 入库。处理成功后状态变为 `completed`，失败时变为 `failed` 并写入 `error_message`。

Celery 任务复用同一套同步处理逻辑，因此失败状态和幂等策略与同步入口一致。每次处理会先删除该 document 已有 chunks，再重新写入新 chunks，避免任务重试造成重复入库。

pgvector 检索模块会在 SQL 层按 `user_id + kb_id` 过滤:

```text
document_chunks.user_id = current_user.id
document_chunks.kb_id = requested_kb_id
```

检索结果会转换为结构化 references，供后续问答接口保存到 `chat_messages.references`。

## 多租户问答 API

问答和聊天记录接口:

```text
POST /api/v1/kbs/{kb_id}/chat
POST /api/v1/kbs/{kb_id}/chat/stream
GET  /api/v1/chat-sessions
GET  /api/v1/chat-sessions/{session_id}/messages
```

问答请求:

```json
{
  "question": "这个系统怎么计费？",
  "session_id": 1
}
```

`session_id` 可选。不传时创建新会话，传入时只允许复用当前用户自己的会话，且会话必须属于当前 `kb_id`。

问答流程:

1. 校验当前用户有权访问知识库。
2. 保存用户问题到 `chat_messages`。
3. 使用 pgvector 在 `user_id + kb_id` 范围内检索 chunks。
4. 调用模型生成回答。
5. 保存助手回答和结构化 references。
6. 返回 `answer / references / session_id`。

同步问答响应会额外返回 `usage`，尽量包含 `input_tokens`、`output_tokens`、`total_tokens` 和 `cached`。不同模型网关可能不返回 token usage，此时本接口会返回 0 值占位并继续完成回答。

流式问答接口返回 `text/event-stream`，事件包括:

- `answer`: 增量回答片段，字段为 `content` 和当前累计 `answer`
- `complete`: 完整回答、references、session_id、cache_hit 和 usage

## 用户反馈

React Web 控制台会在助手回答下方显示有帮助 / 没帮助按钮。提交后，FastAPI 会将反馈追加写入 `FEEDBACK_LOG_PATH` 指向的 JSONL 文件，字段包括 `thread_id`、`message_id`、`rating`、问题、回答、引用和检索参数快照。

也可以直接调用 API:

```json
POST /api/feedback
{
  "thread_id": "web_xxx",
  "message_id": "assistant_message_id",
  "rating": "down",
  "question": "扫地机器人连不上 WiFi 怎么办？",
  "answer": "检查路由器频段...",
  "citations": [{"source": "故障排除.txt"}],
  "metadata": {"search_type": "hybrid"}
}
```

## 运行指标

FastAPI 提供基础进程内指标:

```powershell
curl http://127.0.0.1:8000/api/metrics
```

当前包含:

- `chat_requests_total`
- `chat_stream_requests_total`
- `chat_errors_total`
- `feedback_total`
- `feedback_up_total`
- `feedback_down_total`
- `average_chat_elapsed_ms`
- `last_chat_elapsed_ms`
- `uptime_seconds`

这些指标随进程重启清零，适合本地调试和轻量部署观测。需要长期趋势或告警时，再接入 Prometheus / OpenTelemetry 等外部系统。

## 注意事项

- `evaluate_retrieval` 依赖本地向量库和 embedding 检索链路。
- `generate_answers` 与 `capture_trace` 会真实调用模型，需要 `.env` 中的模型配置和 API Key 可用。
- `evaluate_answers` 默认会把未通过样本导出到 `data/eval/bad_cases.jsonl`，便于后续回看 bad case。
- 如果命令报依赖缺失，先执行 `uv sync`，再重试 `uv run ...`。
