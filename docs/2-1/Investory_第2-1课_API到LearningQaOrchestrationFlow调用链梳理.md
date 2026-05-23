# API 到 `LearningQaOrchestrationFlow` 调用链梳理

## 结论先说

当前代码里，用户从 HTTP API 发起请求后，`POST /tasks` 已经会复用
`src/investory/gateway/api.py` 里的 `execute_task_request()`，并进入
`LearningQaOrchestrationFlow`。

这意味着：

- 如果你问的是“代码里 API 怎么调用到这个 flow”，答案是：通过 `execute_task_request()`。
- 如果你问的是“用户现在打 `/tasks` 时是否经过这个 flow”，答案是：按当前实现，会经过。

---

## 1. API 入口层

### 1.1 FastAPI 挂载入口

应用入口在 `src/investory/main.py:11-21`：

- `create_app()` 创建 `FastAPI`
- `app.include_router(gateway_router)` 挂载网关路由
- `gateway_router` 来自 `src/investory/gateway/api.py`

所以用户的 HTTP 请求会先进入 `src/investory/gateway/api.py`。

### 1.2 请求模型

`src/investory/gateway/schemas.py:23-34` 定义了 API 入参 `TaskRequest`：

- `task_type`: 任务类型
- `payload`: 任务载荷
- `session_id`: 可选，会话 ID

用户调用 `/tasks` 时，核心就是提交这 3 个字段。

---

## 2. 与 `LearningQaOrchestrationFlow` 直接相连的 API helper

### 2.1 入口函数

`src/investory/gateway/api.py:46-56`：

```python
def execute_task_request(
    task_request: TaskRequest,
    *,
    executor: TaskExecutor | None = None,
) -> TaskResponse:
    session_id = resolve_session_id(task_request.session_id)
    spec = resolve_task_spec(task_request.task_type)

    flow = LearningQaOrchestrationFlow(task_executor=executor)
    result = flow.run(spec, task_request.payload)
    return _to_gateway_response(result, session_id=session_id)
```

这条链路的步骤是：

1. 解析 `session_id`
2. 根据 `task_type` 找到 `TaskSpec`
3. 实例化 `LearningQaOrchestrationFlow`
4. 调用 `flow.run(spec, payload)`
5. 把 `TaskResult` 转成 `TaskResponse`

### 2.2 `task_type` 如何映射到 `TaskSpec`

映射逻辑在 `src/investory/gateway/routing.py:14-48`：

- `qa -> finance_qa`
- `summary -> learning_material_summary`
- `brief -> instrument_brief`

最终从 `src/investory/agent_core/tasks.py:13-38` 注册表里取出对应 `TaskSpec`。

---

## 3. `LearningQaOrchestrationFlow` 内部执行逻辑

### 3.1 `run()` 做了什么

`src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:67-101`

`run()` 的职责：

1. 组装 `LearningQaFlowState`
2. 执行 LangGraph：`self.graph.invoke(state)`
3. 把最终状态转成 `TaskResult`
4. 如果中途异常，统一收敛为 `TaskError`

初始 state 里最重要的字段是：

- `spec`
- `task_name`
- `input_payload`
- `request_id`

### 3.2 图结构

图在 `src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:103-136` 定义，主路径如下：

1. `classify_request`
2. `validate_decision_contract`
3. 按 `action_call.action` 分支
4. `build_task_response`
5. `END`

具体分支：

- `ask_missing_fields` -> `ask_for_missing_input`
- `run_task_model` -> `answer_learning_question`
- `refuse_investment_advice` -> `refuse_advice_and_redirect`

### 3.3 第 1 步：分类 / 决策

`classify_request()` 在 `src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:138-145`，
实际调用的是 `LearningQaDecisionPlanner.decide()`。

planner 实现在 `src/investory/agent_core/runtime/flow/learning_qa_decision_planner.py:13-34`。

它当前的核心逻辑非常直接：

1. 用 `get_missing_required_fields(spec, payload)` 检查缺失必填字段
2. 如果缺字段，生成 `TaskDecision(action=ASK_MISSING_FIELDS, ...)`
3. 如果字段齐全，生成 `TaskDecision(action=RUN_TASK_MODEL, ...)`

缺字段判断来自 `src/investory/agent_core/runtime/input_requirements.py:4-26`：

- 字段不存在，算缺失
- 值是 `None`，算缺失
- 值是空字符串或纯空白，算缺失

也就是说，这个 planner 现在本质上是一个“先判定输入是否完整，不完整就追问，完整就执行模型”的分流器。

### 3.4 第 2 步：校验 decision contract

`validate_decision_contract()` 在
`src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:146-157`。

它会调用 `src/investory/agent_core/actions/validator.py:83-96` 的共享校验逻辑，确认：

- `decision.action` 是否属于允许动作
- `decision.task_name` 是否和 `spec.name` 一致

通过后把 `TaskDecision` 转成 `ActionCall`。

### 3.5 第 3 步：按 action 路由到 executor

路由逻辑在：

- `route_by_action_key()`：`src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:265-268`
- `ActionRouter.route()`：`src/investory/agent_core/actions/router.py:23-36`

默认 executor 映射在 `src/investory/agent_core/actions/router.py:39-46`：

- `ask_missing_fields` -> `AskMissingFieldsExecutor`
- `run_task_model` -> `RunTaskModelExecutor`
- `refuse_investment_advice` -> `RefuseInvestmentAdviceExecutor`

### 3.6 分支 A：缺字段，追问用户

当 planner 返回 `ASK_MISSING_FIELDS` 时：

1. flow 进入 `ask_for_missing_input()`，位置：
   `src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:159-164`
2. `_execute_expected_action()` 校验 action 参数，位置：
   `src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:180-197`
3. `ActionRouter` 选中 `AskMissingFieldsExecutor`
4. `AskMissingFieldsExecutor.execute()` 返回 `ActionResult(status="requires_user_input")`，位置：
   `src/investory/agent_core/actions/executors.py:15-28`

这一分支不会真正调用底层 `TaskExecutor`，而是直接返回一个“请补充字段”的结构化结果。

所以对用户来说，这个 flow 的关键价值就是：

- 在模型执行前挡住不完整输入
- 返回缺失字段列表
- 避免把不完整 payload 直接送进主任务执行

### 3.7 分支 B：字段完整，执行任务模型

当 planner 返回 `RUN_TASK_MODEL` 时：

1. flow 进入 `answer_learning_question()`，位置：
   `src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:166-171`
2. `_execute_expected_action()` 通过 router 找到 `RunTaskModelExecutor`
3. `RunTaskModelExecutor.execute()` 调用
   `self.task_executor.run(spec, call.params["payload"])`，位置：
   `src/investory/agent_core/actions/executors.py:31-37`
4. 这里的 `task_executor` 是 `src/investory/agent_core/runtime/task_executor.py:7-12`
5. 它继续进入 `TaskExecutionPipeline.run()`，位置：
   `src/investory/agent_core/runtime/task_execution_pipeline.py:131-145`

`TaskExecutionPipeline` 的步骤是：

1. `build_execution_context()`：校验输入模型，构造 prompt messages
2. `invoke_task_model()`：调用 `RequestRunner.run()`
3. `build_task_result()`：整理成 `TaskResult`

因此，`LearningQaOrchestrationFlow` 在“字段完整”场景下，本质上是：

`API -> orchestration flow -> ActionRouter -> RunTaskModelExecutor -> TaskExecutor -> TaskExecutionPipeline -> LLM`

### 3.8 分支 C：拒绝投资建议

图里预留了 `REFUSE_INVESTMENT_ADVICE` 分支：

- flow 节点：`src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:173-178`
- executor：`src/investory/agent_core/actions/executors.py:40-61`

但当前 `LearningQaDecisionPlanner.decide()` 并没有产出这个 action。

所以这条分支目前更像是“框架能力已预埋，但默认 planner 暂未触发”的状态。

### 3.9 最终回包

无论走哪个 action 分支，最后都会进入 `build_task_response()`：

- `src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:199-203`
- `backfill_action_result()`：`src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py:249-262`

规则是：

- `action_result.status == "failed"` -> `TaskResult(ok=False, ...)`
- 否则 -> `TaskResult(ok=True, result=action_result.result)`

这也是为什么“缺字段追问”虽然不是最终答案，但仍会表现为 `ok=True`，因为它不是系统错误，而是一个有效的下一步动作结果。

---

## 4. 当前 FastAPI `/tasks` 的实际运行链路

### 4.1 当前代码

`src/investory/gateway/api.py:116-135`

```python
@router.post("/tasks", response_model=TaskResponse)
def run_task(request: Request, task_request: TaskRequest) -> TaskResponse | JSONResponse:
    executor = getattr(request.app.state, "task_executor", None) or TaskExecutor()

    try:
        return execute_task_request(task_request, executor=executor)
    except UnknownTaskTypeError as exc:
        session_id = resolve_session_id(task_request.session_id)
        return _unknown_task_response(exc, session_id=session_id)
```

这条链路是：

1. 从 `app.state` 取 `task_executor`
2. 调用 `execute_task_request(task_request, executor=executor)`
3. `execute_task_request()` 内部解析 `session_id`
4. `resolve_task_spec(task_type)` 找到 `TaskSpec`
5. 实例化 `LearningQaOrchestrationFlow`
6. `flow.run(spec, payload)`
7. 最终返回 `TaskResponse`

这里已经不再绕过 flow。

### 4.2 这意味着什么

如果严格按当前 `run_task()` 代码理解：

- `/tasks` 会先经过 `LearningQaOrchestrationFlow`
- 缺字段时会先返回 `ask_missing_fields`
- 字段完整时才继续进入 `TaskExecutor -> TaskExecutionPipeline`

---

## 5. 测试体现出的目标行为，现在与 `/tasks` 实现一致

`tests/test_gateway_task_api.py` 体现了两层预期：

### 5.1 helper `execute_task_request()` 的预期

`tests/test_gateway_task_api.py:24-68` 明确验证：

- payload 不完整时，返回 `ask_missing_fields`
- 且不会调用底层 executor
- payload 完整时，才调用 executor

这和 `LearningQaOrchestrationFlow` 的设计完全一致。

### 5.2 `/tasks` endpoint 的预期

`tests/test_gateway_task_api.py:71-122` 也在验证：

- `POST /tasks` 缺字段时，应返回 `ask_missing_fields`
- 完整时，才执行 executor

现在这和 `src/investory/gateway/api.py` 的实现是一致的，因为 `/tasks`
已经复用 `execute_task_request()` 并进入了 flow。

---

## 6. 可以把这件事理解成什么

当前比较合理的分层已经落成：

`API -> 任务类型解析 -> LearningQaOrchestrationFlow ->`

- `缺字段`：返回 `ask_missing_fields`
- `字段完整`：进入 `TaskExecutor / TaskExecutionPipeline`
- `需要拒绝`：返回 `refuse_investment_advice`

其中：

- `execute_task_request()` 是 API 层对 flow 的统一封装
- `POST /tasks` 现在直接复用了这层封装

---

## 7. 对“用户从 API 调用这个 flow”的最简调用链总结

如果只看“进入 `LearningQaOrchestrationFlow` 的链路”，最短版是：

1. 用户提交 `TaskRequest(task_type, payload, session_id)`
2. `execute_task_request()` 解析 `session_id`
3. `resolve_task_spec(task_type)` 找到 `TaskSpec`
4. `LearningQaOrchestrationFlow(task_executor=executor)`
5. `flow.run(spec, payload)`
6. planner 判断：
   - 缺字段 -> `ask_missing_fields`
   - 字段完整 -> `run_task_model`
7. router 选择 executor
8. 如果是 `run_task_model`，继续进入 `TaskExecutor -> TaskExecutionPipeline`
9. 结果包装成 `TaskResponse` 返回给 API 调用方

---

## 8. 对第 2-1 课的直接启示

如果第 2-1 课的目标是“输入信息不足时追问用户”，那么真正承载这件事的核心就在：

- `LearningQaDecisionPlanner.decide()` 负责判定缺什么
- `AskMissingFieldsExecutor` 负责把“缺失字段列表”变成可回给前端/调用方的结构化结果
- `LearningQaOrchestrationFlow` 负责保证“先追问，再决定是否执行任务模型”

现在正式 API 已经通过 `execute_task_request()` 对齐到
`LearningQaOrchestrationFlow`，因此“输入信息不足时先追问用户”的逻辑会先于任务模型执行。
