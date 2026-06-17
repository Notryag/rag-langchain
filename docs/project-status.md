# 项目现状

## 项目阶段

当前项目不是从 0 到 1 的空壳，而是已经具备最小可用闭环的本地 RAG 工程，并开始向多租户企业知识库 RAG 后端演进。

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

- 多租户认证、知识库 CRUD、文档上传、pgvector 入库和问答接口还在建设中。
- 当前 Chroma 本地检索主链路仍在，新 pgvector 链路尚未替换主链路。
- Agent、middleware、service 与新的多租户 service 边界还需要继续收紧。
- 当前已进入产品化改造期，但还没有形成完整可部署企业知识库后端。

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

这是合理的最小骨架，但还没有演化成长期稳定的工程结构。

## 当前最重要的结论

接下来最值得投入的方向是分批完成多租户后端主链路:

1. 用户认证
2. 知识库 CRUD
3. 文档上传与状态追踪
4. pgvector 入库与权限过滤检索
5. 问答接口、引用返回和聊天记录

质量评测仍然重要，但当前工程主线已经切到多租户企业知识库能力建设。
