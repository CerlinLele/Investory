# Investory 第 1-2 课：最小编排流程操作计划

本计划对应课程主题“Agently TriggerFlow 入门与最小编排流程”，但 Investory 本阶段不引入 Agently。我们只吸收这一课的工程思想：把第 1-1 课的单次任务执行器升级成一个显式的最小流程。

当前第 1-1 课已经具备：

```text
TaskSpec + payload
-> TaskExecutor
-> input validation
-> prompt build
-> RequestRunner
-> structured output
-> TaskResult
```

第 1-2 课要做的不是增加模型能力，而是让模型调用运行在清晰的流程节点里：

```text
prepare_context
-> call_model
-> finalize_result
```

## 目标

- 在 Investory 自己的 `agent_core/runtime` 中建立最小编排层。
- 显式管理任务运行状态，而不是让状态散落在 `TaskExecutor.run()` 的局部变量中。
- 把“准备上下文、调用模型、整理输出”拆成可测试的节点。
- 保持第 1-1 课已有的 `TaskSpec`、`RequestRunner`、`TaskResult` 契约，不为课程概念重写项目边界。
- 为后续 planner、tool、event、memory 预留扩展位置。

## 不做什么

- 不引入 Agently。
- 不引入 LangGraph 或完整 agent loop。
- 不做工具调用、planner、MCP、长期记忆、并发、流式输出。
- 不改任务 prompt 的业务语义。
- 不扩大 HTTP gateway 的功能范围，除非最小流程需要暴露状态字段。

## 推荐目录变化

```text
src/investory/agent_core/
  contracts/
    flow_state.py          # 新增：流程状态与节点状态契约
  runtime/
    minimal_flow.py        # 新增：最小三节点编排流程
    task_executor.py       # 调整：委托 minimal_flow 执行

tests/
  test_minimal_flow.py     # 新增：流程节点与错误路径测试
  test_task_executor.py    # 调整：确认 executor 仍返回兼容结果
```

如果后续流程复杂度上升，再考虑拆分为：

```text
runtime/flow/
  state.py
  nodes.py
  runner.py
```

当前阶段先保持文件数量少，避免过早抽象。

## 核心契约设计

新增一个显式流程状态，建议命名为 `FlowState` 或 `TaskFlowState`：

```python
class TaskFlowState(BaseModel):
    task_id: str
    task_name: str
    status: Literal["pending", "running", "done", "error"]
    input_payload: dict
    validated_input: dict | None = None
    messages: list[Any] | None = None
    model_result: dict | None = None
    output: TaskResult | None = None
    error: TaskError | None = None
```

设计重点：

- `task_id` 由流程入口生成，先用 `uuid4()` 即可。
- `status` 描述整个流程状态，不替代 `TaskResult.ok`。
- `validated_input` 保存输入校验后的稳定数据。
- `messages` 是 prompt build 的结果，作为 `call_model` 的输入。
- `model_result` 保存结构化模型输出的 dict。
- `output` 是最终统一返回的 `TaskResult`。
- `error` 保存规范化后的错误信息，便于后续事件和日志复用。

状态作用域：

- 当前 `TaskFlowState` 表达的是单次任务运行状态，不是多轮会话状态。
- 一次 `TaskExecutor.run(spec, payload)` 对应一份 `TaskFlowState`。
- `task_id` 更准确地说是一次任务运行 id，用来串联本轮的输入校验、prompt 构建、模型调用和输出整理。
- `messages` 是本轮 prompt build 的结果，不承载跨轮历史消息。
- 本阶段不引入 `session_id`、`conversation_id`、长期 memory、checkpoint 或多 turn trace。
- 如果后续需要多轮能力，应在外层增加会话状态，例如 `ConversationState(session_id, turns: list[TaskFlowState], memory=...)`，而不是把多轮语义提前塞进最小流程状态。

## 最小流程节点

### 1. prepare_context

职责：

- 接收 `TaskSpec` 和原始 payload。
- 创建 `task_id`。
- 校验输入模型。
- 构建 prompt messages。
- 写入 `TaskFlowState`。

输入：

```text
TaskSpec
payload
```

输出：

```text
TaskFlowState(status="running", validated_input=..., messages=...)
```

错误收束：

- 输入校验失败：`stage="input_validation"`。
- prompt 加载或组装失败：`stage="prompt_build"`。

### 2. call_model

职责：

- 从 state 中读取 `messages`。
- 调用现有 `RequestRunner.run(messages, spec.output_model)`。
- 把 Pydantic 输出转成 dict，写入 `state.model_result`。

输入：

```text
TaskFlowState(messages=...)
TaskSpec.output_model
RequestRunner
```

输出：

```text
TaskFlowState(model_result=...)
```

错误收束：

- `ValidationError`：`stage="output_validation"`。
- 其他模型调用异常：`stage="model_call"`。

### 3. finalize_result

职责：

- 把成功或失败状态统一整理成 `TaskResult`。
- 成功时设置 `status="done"`。
- 失败时设置 `status="error"`。

成功输出：

```python
TaskResult(
    ok=True,
    task_name=spec.name,
    result=state.model_result,
)
```

失败输出：

```python
TaskResult(
    ok=False,
    task_name=spec.name,
    result=None,
    error=state.error,
)
```

## 实施步骤

### 第一步：补流程状态契约

操作：

- 新增 `src/investory/agent_core/contracts/flow_state.py`。
- 定义 `TaskFlowStatus`、`TaskFlowState`。
- 先只放最小字段，不引入事件列表和节点耗时。

验收：

- `TaskFlowState` 可以表达 pending、running、done、error 四种状态。
- 单元测试覆盖默认状态和必填字段。

### 第二步：抽出最小流程实现

操作：

- 新增 `src/investory/agent_core/runtime/minimal_flow.py`。
- 实现 `prepare_context()`、`call_model()`、`finalize_result()`。
- 实现一个入口函数或类，例如 `MinimalTaskFlow.run(spec, payload)`。
- 复用 `TaskExecutor.build_messages()` 的逻辑，或把 build messages 抽成共享函数，避免复制 prompt 组装代码。

建议先采用类：

```python
class MinimalTaskFlow:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.runner = runner or RequestRunner()

    def run(self, spec: TaskSpec, payload: dict) -> TaskResult:
        ...
```

验收：

- 成功路径按 `prepare_context -> call_model -> finalize_result` 执行。
- 每个错误阶段仍然返回现有 `TaskError` 类型。
- `RequestRunner` 仍然是唯一直接调用模型的对象。

### 第三步：让 TaskExecutor 委托流程

操作：

- 调整 `TaskExecutor.run()`，让它调用 `MinimalTaskFlow`。
- 保留 `TaskExecutor` 作为外部稳定入口，避免影响 gateway、smoke test 和已有调用方。
- 如果 `build_messages()` 留在 `TaskExecutor` 里，需要避免 `minimal_flow.py` 反向依赖 `TaskExecutor` 造成职责混乱。更推荐把 prompt 组装抽到 `runtime/message_builder.py`。

推荐演进：

```text
TaskExecutor.run()
-> MinimalTaskFlow.run()
   -> prepare_context
   -> call_model
   -> finalize_result
```

验收：

- `tests/test_task_executor.py` 原有语义不变。
- 外部调用仍然只需要 `TaskExecutor(runner=...).run(spec, payload)`。

### 第四步：补测试

新增 `tests/test_minimal_flow.py`：

- 成功路径：返回 `ok=True`，包含结构化 result。
- 输入校验失败：返回 `input_validation_failed`，不调用 runner。
- prompt build 失败：返回 `prompt_load_failed`。
- 模型超时：返回 `timeout`，stage 为 `model_call`。
- 输出校验失败：返回 `structured_output_failed`，stage 为 `output_validation`。

调整 `tests/test_task_executor.py`：

- 保留第 1-1 课已有测试。
- 如果实现把 prompt 组装移动到 `message_builder.py`，同步调整 monkeypatch 位置。

验收命令：

```powershell
python -m pytest tests\test_minimal_flow.py tests\test_task_executor.py
python -m pytest
```

### 第五步：更新文档和 smoke 说明

操作：

- 在 `README.md` 或 `runtime/smoke/README.md` 中补一句：任务执行器现在通过最小流程执行。
- 说明当前流程是线性的三节点流程，不包含 planner/tool/event。

验收：

- 新读者能从文档理解：Investory 有编排层，但暂时不是完整 agent runtime。

## 最终验收标准

完成本章节后，项目应该满足：

- 输入一段任务 payload 后，系统会先生成流程状态。
- 模型调用不再直接裸露在 `TaskExecutor.run()` 的主流程里，而是位于 `call_model` 节点。
- 成功返回仍兼容现有 `TaskResult(ok=True, task_name=..., result=...)`。
- 失败返回仍兼容现有 `TaskResult(ok=False, task_name=..., error=...)`。
- 测试能证明三类边界清晰存在：上下文准备、模型调用、输出整理。

## 推荐提交顺序

1. `feat(flow): add minimal task flow state contract`
2. `feat(flow): add minimal task orchestration runtime`
3. `refactor(runtime): delegate task executor to minimal flow`
4. `test(flow): cover minimal orchestration success and errors`
5. `docs(flow): document chapter 1-2 minimal orchestration`

## 本章完成后的架构图

```text
Gateway / CLI / Smoke
-> TaskExecutor
-> MinimalTaskFlow
   -> prepare_context
      -> input_model validation
      -> prompt loading
      -> message building
   -> call_model
      -> RequestRunner
      -> LangChain structured output
   -> finalize_result
      -> TaskResult
```

一句话标准：

```text
第 1-2 课完成后，Investory 不需要更聪明，但必须更有结构。
```
