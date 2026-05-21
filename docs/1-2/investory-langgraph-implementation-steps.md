# Investory 第 1-2 课：LangGraph 实施步骤（Implementation Steps）

## 目标与边界

- 目标：把当前最小编排层升级为基于 `langgraph` 的显式流程。
- 保持外部契约稳定：`TaskExecutor.run(spec, payload) -> TaskResult` 不变。
- 本次不引入 planner、tool call、memory、checkpoint、多轮会话管理。

## Implementation Steps

### 1. 基线确认与冻结

- 执行并记录当前基线测试：
  - `tests/test_minimal_flow.py`
  - `tests/test_task_executor.py`
  - `tests/test_flow_state.py`
- 产物：
  - 改造前测试结果记录（通过/失败项）。

### 2. 引入依赖

- 在 `pyproject.toml` 的 `dependencies` 增加 `langgraph`。
- 安装依赖并验证 `import langgraph`。
- 产物：
  - 依赖声明更新。
  - 本地运行环境可导入 `langgraph`。

### 3. 明确状态契约

- 保留并复用 `TaskFlowState`（`contracts/flow_state.py`）。
- 约定每个图节点输入输出均为 `TaskFlowState`。
- 产物：
  - 状态字段不扩张，仅用于最小编排。

### 4. 用 LangGraph 重构最小流程

- 文件：`src/investory/agent_core/runtime/minimal_flow.py`
- 保留三个节点函数（可沿用现有逻辑）：
  - `prepare_context`
  - `call_model`
  - `finalize_result`
- 组装 `StateGraph`：
  - `prepare_context -> condition`
  - `condition: error -> finalize_result`
  - `condition: ok -> call_model -> finalize_result`
  - `finalize_result -> END`
- 在 `MinimalTaskFlow.__init__` 编译 graph，在 `run()` 调用 graph。
- 产物：
  - 从手写顺序流切换为图编排执行。

### 5. 对齐错误与重试语义

- 在 `call_model` 节点兼容处理：
  - `StructuredOutputError`（映射 `output_validation`）
  - `ModelCallError`（映射 `model_call`）
- 保留 `retry_count` 透传到 `TaskError`。
- 继续使用 `normalize_task_error(stage=...)`，保持 error_type 与 stage 稳定。
- 产物：
  - 错误结构与既有 API 兼容。

### 6. 让 TaskExecutor 委托到 Flow

- 文件：`src/investory/agent_core/runtime/task_executor.py`
- `TaskExecutor.run()` 只做委托：
  - `return self.flow.run(spec, payload)`
- 删除/收敛重复逻辑（输入校验、prompt 构建、模型调用）以避免双路径维护。
- 产物：
  - 单一执行路径，职责更清晰。

### 7. 测试调整与补强

- 更新 `tests/test_minimal_flow.py`：
  - 成功路径（`ok=True`）
  - 输入校验失败（`input_validation`）
  - prompt 构建失败（`prompt_build`）
  - 输出校验失败（`output_validation`）
  - 模型调用超时（`model_call`）
  - 分支断言：`prepare_context` 失败时不调用 runner
- 更新 `tests/test_task_executor.py`：
  - 保持原有对外语义断言。
  - 验证 `retry_count` 与 `error_type/stage` 一致。
- 产物：
  - 覆盖图执行路径且确保兼容。

### 8. 回归与验收

- 执行：
  - `pytest tests/test_flow_state.py tests/test_minimal_flow.py tests/test_task_executor.py`
  - `pytest`
- 验收标准：
  - `TaskExecutor` 外部接口不变。
  - 各错误路径的 `stage/error_type/retry_count` 与改造前一致。
  - `RequestRunner` 仍是唯一直接模型调用点。

### 9. 文档同步

- 更新课程计划文档中“是否引入 LangGraph”的描述，确保文档与实现一致。
- 明确本阶段仅是最小 LangGraph 编排，不等于完整 agent runtime。

### 10. 提交切分建议

- `build(runtime): add langgraph dependency`
- `feat(flow): migrate minimal flow to langgraph state graph`
- `refactor(executor): delegate task execution to minimal flow`
- `test(flow): align minimal flow and executor coverage`
- `docs(flow): update chapter 1-2 plan with langgraph adoption`

