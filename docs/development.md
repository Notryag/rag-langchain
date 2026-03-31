# 开发与运行约定

## Python 环境

本项目统一使用 `uv` 执行命令，不直接写死 `.venv\Scripts\python.exe`，也不建议直接使用系统 `python`。

推荐方式:

```powershell
uv run python -m app.eval.retrieval_eval --limit 2
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

## 常用评测命令

### 检索评测

```powershell
uv run python -m app.eval.retrieval_eval
uv run python -m app.eval.retrieval_eval --limit 10
uv run python -m app.eval.retrieval_eval --search-type similarity mmr --top-k 3 5 --fetch-k 8 12
uv run python -m app.eval.retrieval_eval --show-passes
```

### 采样回答

```powershell
uv run python -m app.eval.sample_answers --limit 5
```

### 回答评测

```powershell
uv run python -m app.eval.answer_eval --limit 5
uv run python -m app.eval.answer_eval --show-passes
```

### 抓取单次 Trace

```powershell
uv run python -m app.eval.traces "扫地机器人连不上WiFi怎么办"
```

## 注意事项

- `retrieval_eval` 依赖本地向量库和 embedding 检索链路。
- `sample_answers` 与 `traces` 会真实调用模型，需要 `.env` 中的模型配置和 API Key 可用。
- 如果命令报依赖缺失，先执行 `uv sync`，再重试 `uv run ...`。
