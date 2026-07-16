# rag-langchain

[![CI](https://github.com/Notryag/rag-langchain/actions/workflows/ci.yml/badge.svg)](https://github.com/Notryag/rag-langchain/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=111)

一个可运行、可评测、边界清晰的多租户 Agentic RAG 工程基线。

它覆盖从文档上传、异步解析、向量入库，到按需检索、流式回答、引用保存和质量评测的完整链路。项目重点不是堆叠连接器或可视化工作流，而是展示一套可以继续演进的后端分层、租户隔离和 RAG 评测方法。

## 项目定位

适合：

- 学习和验证生产化 RAG 的完整工程路径；
- 构建需要用户/知识库隔离的内部文档问答服务；
- 比较 similarity、MMR、hybrid 和 reranker 的检索效果；
- 在明确代码边界上继续扩展业务能力。

它不是 Dify 或 RAGFlow 的轻量替代品。目前不提供可视化工作流、大量数据源连接器、组织级 RBAC/ACL 或通用工具市场。

## 设计原则

### Agentic RAG，而非固定检索流水线

Agent 根据请求和已有上下文判断是否调用 `retrieve_context`：文档事实、指定来源和需要证据的问题通常检索；寒暄、一般推理或上下文已经足够时可以直接回答。

如果业务要求每次严格执行“检索 -> 生成 -> 校验”，应使用 LangGraph 等确定性工作流显式编排，而不是通过 Prompt 假装强制执行。

### 执行上下文不进入 Prompt

`user_id`、`kb_id`、数据库 session、`top_k`、reranker 等参数通过 `ToolRuntime` 传递。System Prompt 只描述模型需要理解的角色、工具选择、证据和输出规则。

### 权限过滤进入 SQL

知识库、文档、chunk、聊天记录和向量召回都由服务端认证主体约束。pgvector 查询在候选召回前使用 `user_id + kb_id` 过滤，不依赖模型或应用层后过滤实现租户隔离。

## 运行架构

```text
React Web / API Client
          |
          v
FastAPI /api/v1  -- JWT、限流、错误协议
          |
          v
Runtime + ChatService -- run 生命周期、SSE、取消、持久化
          |
          v
LangChain Agent
     |                     |
     | 无需文档上下文       | 需要文档证据
     v                     v
直接回答             retrieve_context tool
                            |
                            v
               PostgreSQL + pgvector
               user_id + kb_id SQL 过滤
                            |
                            v
                 hybrid / MMR / rerank
                            |
                            v
                    回答 + 结构化引用

文档上传 -> Celery worker -> parse -> split -> embedding -> pgvector
```

## 已实现能力

### 产品与权限

- 用户注册、登录和 JWT 鉴权；
- 用户级知识库、文档、聊天会话和消息隔离；
- `admin / user` 最小 RBAC，Prompt 版本管理仅管理员可用；
- 上传大小、扩展名和 MIME 校验；
- API 限流和操作日志。

### 文档与检索

- `.txt`、`.md`、`.pdf`、`.docx`、`.html` 文档；
- 同步处理与 Celery 异步处理、有限重试和执行超时；
- PostgreSQL + pgvector 向量存储；
- similarity、MMR、hybrid 检索；
- 内置 embedding/lexical reranker 和可插拔 HTTP reranker；
- 引用格式化、去重和上下文字符预算。

### Agent 与运行态

- LangChain tool-calling Agent，按需调用知识库检索；
- LangGraph checkpointer 提供会话状态；
- SSE 流式回答、run 取消和运行态查询；
- tool/result/complete/error 事件时间线；
- Prompt 版本创建、启用和回滚；
- usage、token cost、trace id/url 和 LangSmith 配置入口；
- 本地 stdio MCP 示例。

### 质量闭环

- retrieval / answer evaluation；
- baseline manifest 和 bad case 导出；
- 多租户 smoke test；
- 后端、前端和迁移 CI。

## 快速开始

### Docker Compose

要求 Docker 24+ 和 Docker Compose v2。首次启动前创建环境文件并填写模型配置：

```bash
cp .env.example .env
```

至少配置：

```env
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=
CHAT_MODEL=gpt-4.1-mini

EMBEDDING_API_KEY=your_embedding_key
EMBEDDING_BASE_URL=
EMBEDDING_MODEL=bge-m3
EMBEDDING_DIMENSION=1024

JWT_SECRET_KEY=replace-with-a-long-random-secret
```

启动完整项目：

```bash
docker compose up -d --build
```

打开 `http://127.0.0.1:8000`。API 容器会执行数据库迁移，FastAPI 同时托管构建后的 React 前端。

容器访问宿主机 Ollama 或 OpenAI 兼容服务时，不要使用容器内的 `127.0.0.1`：

```env
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
```

### 本机开发

要求 Python 3.11+、Node.js 22+、uv、PostgreSQL/pgvector 和 Redis。

```bash
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
uv run python -m app.main web --reload
```

前端热更新：

```bash
cd frontend
npm ci
npm run dev
```

Vite 默认运行在 `http://127.0.0.1:5173`，后端默认运行在 `http://127.0.0.1:8000`。

## 常用命令

```bash
# 创建 Prompt 管理员
uv run python -m app.main create-admin \
  --username admin \
  --email admin@example.com \
  --password "change-this-password"

# 后端检查
uv run ruff check .
uv run python scripts/run_tests.py

# 前端检查
cd frontend
npm test
npm run build

# 多租户 smoke
uv run python scripts/smoke_multitenant.py --skip-chat

# pgvector 配置诊断
uv run python -m evaluation.check_pgvector_embedding_config

# 保存 retrieval baseline
uv run python -m evaluation.run_pgvector_baseline \
  --user-id 1 \
  --kb-id 1 \
  --retrieval-dataset data/eval/current_kb_retrieval.jsonl \
  --retrieval-limit 10 \
  --skip-answer
```

## Embedding 维度

当前 schema 默认使用 `vector(1024)`，与默认 `bge-m3` 配置一致。切换 embedding 模型时必须同步设置 `EMBEDDING_DIMENSION`，并重建旧向量数据。

项目目前不维护不同 embedding 维度之间的数据迁移兼容。已经建立旧维度表时，请重建数据库或清空 `document_chunks` 后重新处理文档。

## 项目结构

```text
app/
  api/          FastAPI、/api/v1、鉴权、限流和错误协议
  agent/        Agent 装配与稳定 System Prompt policy
  config/       配置与日志
  core/         JWT、密码和安全工具
  db/           SQLAlchemy、ORM 和 session
  memory/       LangGraph checkpointer
  mcp/          独立本地 MCP 示例
  retrieval/    parser、splitter、pgvector、hybrid、rerank、引用
  runtime/      run 生命周期、SSE bridge、取消和状态查询
  schemas/      Pydantic schemas
  services/     业务编排
  tools/        Agent tools，通过 ToolRuntime 获取可信上下文
  workers/      Celery 文档任务
evaluation/     retrieval / answer eval 与 baseline
frontend/       React + Vite
migrations/     Alembic migrations
scripts/        测试与 smoke 脚本
tests/          单元测试和 API 测试
docs/           架构、运行、评测和路线图
```

## 已知边界

- MCP 当前是可信本地 stdio 示例；公开部署前必须增加调用方认证和服务端身份绑定。
- 指定 `source` 的检索目前在 Top-K 召回后过滤，后续需要下推到 SQL 候选查询。
- 检索预览和 MCP 参数需要补充明确的 `top_k/fetch_k` 上限。
- 暂不实现组织/团队 ACL、多向量数据库适配、复杂长期记忆和通用 Agent marketplace。
- Prompt 不是权限边界；认证、租户隔离和敏感操作必须由代码与数据库保证。

## 文档

优先阅读：

- [AGENTS.md](AGENTS.md)：Agent/RAG 工程边界和仓库工作规则；
- [docs/ai-context.md](docs/ai-context.md)：代码助手的渐进式上下文入口；
- [docs/architecture.md](docs/architecture.md)：当前分层和主路径；
- [docs/development.md](docs/development.md)：完整配置、开发和部署；
- [docs/evaluation.md](docs/evaluation.md)：评测数据与 baseline；
- [docs/roadmap.md](docs/roadmap.md)：路线图；
- [docs/todo.md](docs/todo.md)：近期工作。

更多设计记录位于 [docs/](docs/)。

## 参考项目

本项目没有复制下列项目的产品层或工作流实现，主要参考其公开架构、README 信息组织和 RAG 工程实践：

- [RAGFlow](https://github.com/infiniflow/ragflow)：文档处理流水线、可追溯引用和自托管说明；
- [Dify](https://github.com/langgenius/dify)：AI 应用平台的能力分层、模型接入和 LLMOps 表达；
- [LightRAG](https://github.com/HKUDS/LightRAG)：检索策略、评测、reranker 和可观测性实践；
- [Kotaemon](https://github.com/Cinnamon/kotaemon)：面向终端用户与开发者的清晰定位，以及文档引用体验；
- [LangChain](https://github.com/langchain-ai/langchain)：tool-calling Agent、middleware 和 runtime context 基础能力。

借鉴不等于功能对齐。本仓库坚持较小的产品范围，优先保证代码可读、租户边界明确、检索可评测。
