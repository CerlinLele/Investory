# Investory 第 3-1 课 Tool Calling Trace & Log 实施计划（待执行）

## 目标

在不改变现有业务行为的前提下，为 `fetch_then_run_instrument_brief` 增加最小可用的可观测性，便于排查与回放。

## 范围

只做日志与追踪字段，不改动作决策、不改路由、不改结果结构。

涉及文件：

```text
src/investory/agent_core/actions/executors.py
```

## 事件点设计

在 `FetchThenRunInstrumentBriefExecutor.execute` 添加 4 个日志事件：

1. `tool_call_started`
- 字段：`request_id`, `task_name`, `action`, `tool_name`, `instrument_name_or_code`

2. `tool_call_finished`
- 字段：`request_id`, `tool_name`, `ok`, `latency_ms`, `error_type`

3. `tool_backfill_applied`
- 字段：`request_id`, `source_material_length`, `sources_count`

4. `tool_call_degraded`
- 字段：`request_id`, `reason`, `error_type`, `error_message`

## 日志规范

- 使用结构化日志（键值对），避免只打自然语言字符串。
- 不记录完整 `source_material` 正文；只记录长度或前缀摘要。
- 保留 `request_id` 贯穿单次调用链路。

## 具体执行步骤（后续再做）

1. 在 `executors.py` 引入 `logging` 与 `time.perf_counter`。
2. 新增模块级 logger（例如 `logger = logging.getLogger(__name__)`）。
3. 在工具调用前后记录 started/finished 事件并计算耗时。
4. 在回填成功后记录 backfill 事件。
5. 在降级分支记录 degraded 事件。
6. 增加单测（mock logger 或 caplog）验证关键日志事件存在。

## 验收标准

- 工具成功时能看到 `started -> finished -> backfill` 日志链路。
- 工具失败时能看到 `started -> finished -> degraded` 日志链路。
- 日志中包含 `request_id`、`tool_name`、`latency_ms`。
- 日志不泄露完整原始材料内容。

## 备注

当前仓库实现中尚未加入上述 trace/log，本计划仅保存为执行备忘。
