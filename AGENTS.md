# AGENTS.md

本文件提供给在本仓库内工作的自动化代码代理（agent）。

## 项目定位

当前项目已经具备最小可运行 RAG 闭环，重点应放在：

1. 质量评测闭环（retrieval / answer eval）
2. 工程边界收敛（services / retrieval / api/v1 分层）
3. 检索质量迭代（在可评测前提下优化）

## 代码改动优先级

- 新业务流程优先放 `app/services/`
- 新检索能力优先放 `app/retrieval/`
- HTTP 能力优先放 `app/api/v1/`
- 旧 `app/cli/` 与 Streamlit 链路已删除，不要恢复为新主线
- `app/agent/` 与 `app/tools/` 属于当前 `/api/v1 + pgvector` 问答主线；tool 必须走 `app/retrieval/pgvector_store.py` 并保留多租户过滤，不要恢复旧 Chroma vectorstore

## 运行约定

- 统一使用 `uv` 执行：`uv run python -m ...`
- 常用入口：
  - `uv run python -m app.main web`
  - `uv run alembic upgrade head`
  - `uv run python scripts/run_tests.py`
  - `uv run python scripts/smoke_multitenant.py --skip-chat`

## 提交前检查（最小）

- 文档更新时，确保 README 与 docs 导航一致。
- 改动检索/回答逻辑时，至少运行相关 evaluation 命令验证。
- 不要引入与当前任务无关的大规模目录重构。

## 推荐阅读顺序

1. `docs/ai-context.md`
2. `readme.md`
3. 按任务从 `docs/ai-context.md` 的“按任务渐进读取”继续选择文档

## Agent Engineering Standards

本仓库默认实现 Agentic RAG。新增或修改 Agent、Prompt、tool、runtime 和检索代码时，遵守以下边界。

## Agentic RAG

- Agent 自主判断当前请求是否需要检索。文档事实、指定来源、需要证据或上下文不足时检索；寒暄、一般推理和已有上下文足够时可以直接回答。
- 不要用 Prompt 强制每一轮都调用检索工具。需要固定的“检索 -> 生成 -> 校验”流程时，使用 LangGraph 或其他确定性工作流显式编排。
- 是否默认检索、召回数量和 reranker 策略应由评测与产品需求决定，不靠不断叠加 Prompt 规则决定。

## Runtime And Prompt Boundaries

- `user_id`、`kb_id`、`thread_id`、数据库 session、`top_k`、`fetch_k`、reranker 开关和其他执行参数只存在于 runtime/config/tool 层。
- 不要把运行时标识、消息计数、遥测数据或检索配置格式化成自然语言注入 System Prompt。
- 对话连续性由 messages 和 checkpointer 提供，不要再用 Prompt 描述 `first_turn`、`follow_up` 或历史轮数。
- System Prompt 只包含模型确实需要理解的角色、领域规则、工具选择原则、证据规则和输出约束。
- Tool 描述应说明“什么时候有帮助”和输入语义，不应把非确定性的工具选择伪装成系统安全机制。

## Security Boundaries

- Prompt 不是认证、授权、租户隔离、输入校验或数据完整性的安全边界。
- 产品内 Agent tool 必须从可信 `ToolRuntime` 获取当前身份和租户范围；不要把 `user_id`、`tenant_id` 作为模型可填写参数。
- SQL 查询必须使用服务端认证主体约束 `user_id + kb_id`。不能先全局召回再在 Python 中做权限过滤。
- 外部 MCP 服务必须在传输层认证调用者，并在服务端绑定 principal 与可访问资源。让调用方自行提交 `user_id` 只适用于明确标注的可信本地开发工具。
- 检索到的文档是不可信数据。Prompt 注入防护可以辅助模型，但敏感操作仍需代码级权限和动作校验。

## Retrieval Boundaries

- 元数据过滤、来源过滤和租户过滤必须在候选召回之前进入数据库查询；不要先取 Top-K 再做 Python 后过滤。
- 检索参数由 `RetrievalProfile` 或服务端配置控制，通过 runtime 传给工具，不向模型展示。
- 只有实际使用检索结果时才生成引用；引用必须来自本轮真实召回结果。
- Agent 选择不检索是合法路径，调用检索但证据不足也是合法结果，二者都必须可观测和可评测。

## Review Checklist

提交 Agent/RAG 改动前检查：

1. 这是 Agent 自主决策，还是确定性业务流程？后者应放到代码或 LangGraph。
2. 是否把本应留在 runtime 的参数塞进了 Prompt 或 tool 参数？
3. 是否错误地把 Prompt 当成权限、隔离或一致性保证？
4. SQL 是否在召回前完成身份、知识库和来源过滤？
5. 工具调用、未调用、空结果和失败路径是否都能被观测和评测？
6. 自定义 Prompt 是否仍保留必要的证据和不可信文档规则？

## Known Follow-ups

- `app/mcp/server.py` 当前是可信本地 stdio 示例，工具参数中的 `user_id` 不是可公开部署的多租户授权方案。公开 MCP 前必须增加认证主体绑定并移除调用方自报身份。
- `app/tools/retrieve_context.py` 当前对 `source` 做召回后过滤，可能漏掉目标文件。应把来源过滤下推到 pgvector/SQL 候选查询。
- `app/api/v1/chat.py` 的检索预览参数与 `app/mcp/server.py` 的检索参数缺少明确上限。外部输入必须限制 `top_k/fetch_k`，并限制可触发的付费 reranker，避免单请求放大数据库和外部服务成本。
