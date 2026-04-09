# rag-langchain

一个用于“本地知识库问答”的 LangChain RAG 示例项目，适合做 PoC、课程演示和小型内部助手。

## 这个项目能做什么

- 把本地文档（TXT/PDF）切分并写入 Chroma 向量库
- 用 Agent + Tool 进行检索增强问答（RAG）
- 在回答中输出引用来源
- 支持 CLI 交互和 Streamlit 页面
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

## 常用命令

```bash
# 检索评测
uv run python -m evaluation.evaluate_retrieval --limit 10

# 采样生成回答
uv run python -m evaluation.generate_answers --limit 10

# 回答评测
uv run python -m evaluation.evaluate_answers --limit 10
```

## 项目结构（简版）

```text
app/
  agent/       # Agent 装配、prompt 与 middleware
  retrieval/   # 入库、向量库、检索、引用格式化
  tools/       # 暴露给 Agent 的工具
  services/    # 业务编排（UI / CLI 共用）
  cli/         # 命令行入口
evaluation/    # 离线评测脚本
data/          # 原始数据与评测数据
docs/          # 架构、路线图、开发说明
```

## 文档导航

- 架构说明: [docs/architecture.md](docs/architecture.md)
- 架构评审: [docs/architecture-review.md](docs/architecture-review.md)
- 开发与运行约定: [docs/development.md](docs/development.md)
- 项目现状: [docs/project-status.md](docs/project-status.md)
- 路线图: [docs/roadmap.md](docs/roadmap.md)
- 待办清单: [docs/todo.md](docs/todo.md)

## 适用场景

- 说明书/FAQ 问答
- 售后支持知识助手
- 企业内部知识检索问答

---

如果你是第一次接触这个仓库，推荐顺序：
1. 先按“快速开始”跑通 ingest + cli。
2. 再看 `docs/architecture.md` 理解主链路。
3. 最后跑一次 `evaluation` 看质量基线。
