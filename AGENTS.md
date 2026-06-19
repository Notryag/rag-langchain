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
- 旧 `app/agent/`、`app/tools/`、`app/cli/` 与 Streamlit 链路已删除，不要恢复为新主线

## 运行约定

- 统一使用 `uv` 执行：`uv run python -m ...`
- 常用入口：
  - `uv run python -m app.main web`
  - `uv run alembic upgrade head`
  - `uv run python scripts/smoke_multitenant.py --skip-chat`

## 提交前检查（最小）

- 文档更新时，确保 README 与 docs 导航一致。
- 改动检索/回答逻辑时，至少运行相关 evaluation 命令验证。
- 不要引入与当前任务无关的大规模目录重构。

## 推荐阅读顺序

1. `docs/ai-context.md`
2. `readme.md`
3. 按任务从 `docs/ai-context.md` 的“按任务渐进读取”继续选择文档
