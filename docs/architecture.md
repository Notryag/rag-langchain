# 架构说明

这份文档只说明当前项目里最重要的职责边界，避免后续继续把逻辑堆进 UI 或 agent prompt。

## 主链路分层

当前主链路建议按下面的方式理解:

```text
CLI / Streamlit / Eval
        |
    services/
        |
      agent/
      tools/
        |
   retrieval/
```

核心原则:

- UI 层只负责交互和展示，不负责拼业务流程。
- `services/` 负责编排一次问答的输入、流式事件、结果聚合。
- `agent/` 负责模型装配、prompt 策略、middleware。
- `tools/` 负责把底层能力暴露给 agent 调用。
- `retrieval/` 负责向量库、检索、入库、引用格式化这些纯检索能力。

## Prompt 策略

当前 prompt 分成两层:

### 静态基线

位置:

- `app/agent/prompts.py`

职责:

- 定义长期稳定的系统角色
- 约束回答必须基于检索上下文
- 约束不足信息时要拒答
- 明确忽略文档内嵌指令

这部分应该保持稳定，不应该随着单次 bad case 临时堆规则。

### 动态运行时上下文

位置:

- `app/agent/prompt_strategy.py`
- `app/middleware/prompt_with_context.py`

职责:

- 注入当前线程 id
- 注入当前对话是首轮还是追问
- 注入当前检索参数，例如 `search_type / top_k / fetch_k`
- 强化当前轮次的执行策略，而不是替代静态 prompt

动态 prompt 更适合放“当前运行态信息”和“当前链路策略”，不适合放大段固定规则。

## Tool 与 Agent 边界

### 哪些逻辑属于 tool

以 `app/tools/retrieve_context.py` 为例，tool 只负责:

- 接收 agent 给出的查询
- 调用 retrieval 层获取 chunks
- 返回带引用标记的上下文
- 记录工具调用日志

tool 不应该负责:

- 直接回答用户问题
- 决定最终拒答还是作答
- 维护会话级业务状态
- 拼 UI 展示文案

### 哪些逻辑属于 agent

agent 负责:

- 判断是否需要调用 tool
- 读取 tool 返回的上下文
- 综合当前用户问题和检索结果生成最终回答
- 决定引用、拒答、追问时的回答策略

agent 不应该负责:

- 直接执行向量检索细节
- 直接管理向量库初始化和缓存
- 直接处理 CLI / Streamlit 的展示事件

## Service 与 UI 边界

`app/services/rag_service.py` 现在是主业务入口。

它负责:

- 发起一次问答
- 聚合底层流事件
- 提供统一的 `ask` / `stream` 输出结构

CLI、Streamlit、eval 只消费这些结果，不再自己理解底层 agent 协议。

## 当前文件映射

- `app/main.py`: 统一入口
- `app/services/rag_service.py`: 主链路编排
- `app/agent/create_agent.py`: agent 装配入口
- `app/agent/prompts.py`: 静态 prompt
- `app/agent/prompt_strategy.py`: 动态 prompt 策略
- `app/middleware/prompt_with_context.py`: 动态 prompt middleware
- `app/tools/retrieve_context.py`: agent 可调用检索 tool
- `app/retrieval/`: 入库、向量库、检索与引用格式化

## 当前结论

短期内最重要的是保持这些边界稳定:

- 新增业务能力优先落到 `services/`
- 新增检索能力优先落到 `retrieval/`
- 新增 agent 行为优先通过 prompt / middleware / tool 装配实现
- 不要把业务判断重新散回 CLI、Streamlit 或单个 tool
