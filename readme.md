# rag-langchain

一个面向本地知识库问答场景的 LangChain RAG 项目。

当前已具备的基础能力:

- 本地文档入库
- Chroma 向量检索
- Agent + Tool 调用
- CLI 对话
- Streamlit 界面
- 流式输出与引用展示

## 文档导航

- 项目现状: [docs/project-status.md](docs/project-status.md)
- 规划与路线图: [docs/roadmap.md](docs/roadmap.md)
- 执行清单: [docs/todo.md](docs/todo.md)
- 开发与运行约定: [docs/development.md](docs/development.md)

## 当前目录

```text
app/
  agent/
  cli/
  config/
  middleware/
  retrieval/
  services/
  tools/
data/
  raw/
storage/
pyproject.toml
readme.md
```

## 当前判断

这个项目已经有完整最小闭环，但还处在从“能跑”向“可评估、可维护、可产品化”过渡的阶段。

下一阶段重点不是继续堆功能，而是:

- 建立质量评测闭环
- 收紧工程边界
- 再逐步升级检索与产品能力
