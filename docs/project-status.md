# 项目现状

## 项目阶段

当前项目不是从 0 到 1 的空壳，而是已经具备最小可用闭环的本地 RAG 工程。

已落地的链路包括:

- 文档加载、切分、去重、入库
- Embeddings 与 Chroma 向量库初始化
- 检索、格式化、引用提取
- Tool 化检索能力
- Agent 构建与流式对话
- CLI 交互
- Streamlit 演示界面

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
- `app/streamlit_app.py`: Web 端演示界面
- `evaluation/`: 顶层离线评测与 trace 工具目录

## 当前优点

- 主链路完整，已经具备继续迭代的基础。
- retrieval、tool、agent、service 已经有初步分层，不完全是脚本堆叠。
- 已经支持引用展示和流式输出，这对调试和用户感知都很重要。
- 当前数据集和场景相对集中，适合走垂直知识助手路线。

## 当前不足

- 还没有评测体系，无法客观判断优化是否有效。
- 会话状态目前更偏开发态，尚未进入持久化和服务化阶段。
- Agent、middleware、service 的职责边界还可以继续收紧。
- 当前更像本地实验型项目，还没有进入可运营、可部署的产品阶段。

## 当前目录判断

当前实际核心结构如下:

```text
app/
  agent/
  cli/
  config/
  middleware/
  retrieval/
  services/
  tools/
evaluation/
data/
  raw/
storage/
```

这是合理的最小骨架，但还没有演化成长期稳定的工程结构。

## 当前最重要的结论

接下来最值得投入的方向不是继续扩展功能数量，而是优先补下面三件事:

1. 质量闭环
2. 工程边界
3. 检索质量升级

如果没有先建立质量闭环，后续的 reranker、hybrid search、prompt 优化都很容易变成“体感调参”。
