# Investory LangGraph DecisionFlow 重构实施步骤

## 目标

把当前手写顺序执行的 `DecisionFlow` 重构为 LangGraph `StateGraph`。

本次只处理编排层：

- 保留 `DecisionFlow.run(spec, payload, request_id=None) -> TaskResult` 对外契约。
- 保留 `TaskExecutor` 作为最小任务执行单位。
- 保留 `TaskExecutionPipeline`、`RequestRunner`、prompt、模型调用与网关协议不变。
- 用 LangGraph 显式表达“决策 -> 条件分支 -> 执行动作 -> 统一返回”。

## 当前基线

当前代码路径：

```text
Gateway
-> DecisionFlow.run(...)
   -> DecisionPlanner.decide(...)
   -> validate_decision(...)
   -> ActionRouter.route(...)
   -> executor.execute(...)
   -> backfill_action_result(...)
-> TaskResult
```

目标代码路径：

```text
Gateway
-> DecisionFlow.run(...)
   -> compiled LangGraph.invoke(initial_state)
      -> decide_action
      -> validate_action
      -> route by action
         -> ask_missing_fields
         -> refuse_investment_advice
         -> run_task_model
      -> finalize_result
-> TaskResult
```

## LangGraph 约束

参考 LangGraph 官方文档：

- `StateGraph` 用 state schema 定义共享状态。
- node 接收 state，返回 state update。
- `START` 和 `END` 表示图入口与出口。
- 条件分支用 `add_conditional_edges(...)`。
- 同一个节点应避免同时使用普通 edge 和条件 edge 指向不同后续节点，降低路由歧义。

官方参考：

- <https://docs.langchain.com/oss/python/langgraph/overview>
- <https://docs.langchain.com/oss/python/langgraph/quickstart>

## Implementation Steps

### 1. 基线确认

执行当前相关测试，记录改造前行为：

```powershell
python -m pytest tests/test_decision_flow.py tests/test_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
python -m pytest tests/test_task_executor.py tests/test_task_execution_pipeline.py -q
```

验收：

- 当前 `DecisionFlow` 三类路径可用：缺失字段、执行模型、拒答。
- `TaskExecutor` 和 `TaskExecutionPipeline` 测试不受影响。

### 2. 引入 LangGraph 依赖

在 `pyproject.toml` 增加：

```toml
"langgraph==<pinned-version>"
```

建议执行：

```powershell
python -m pip install -e .[dev]
python -c "from langgraph.graph import StateGraph, START, END; print('ok')"
python -m pip freeze > requirements.lock.txt
```

验收：

- 本地可导入 `StateGraph`、`START`、`END`。
- 依赖声明与 lock 文件一致。

### 3. 保留并收敛状态契约

继续使用现有 `DecisionFlowState` 字段：

```python
class DecisionFlowState(BaseModel):
    task_id: str
    task_name: str
    input_payload: dict[str, Any]
    decision: TaskDecision | None = None
    action_call: ActionCall | None = None
    action_result: ActionResult | None = None
    output: TaskResult | None = None
    error: TaskError | None = None
```

实现建议：

- 初期可继续保留在 `decision_flow.py`，避免额外文件迁移。
- 如果 LangGraph 类型检查或序列化不顺，再单独抽到 `contracts/decision_flow_state.py`。
- 不新增 planner/tool/memory/session/checkpoint 字段。

验收：

- `DecisionFlow.last_state` 仍保存最终状态。
- 现有测试里对 `last_state.decision/action_call/action_result/error` 的断言继续成立。

### 4. 拆出图节点函数

在 `decision_flow.py` 中先拆出纯节点函数，保持每个节点只做一件事：

```text
decide_action
validate_action
execute_ask_missing_fields
execute_refuse_investment_advice
execute_run_task_model
finalize_result
```

节点职责：

- `decide_action`：调用 `self.planner.decide(spec, payload)`，写入 `decision`。
- `validate_action`：调用 `validate_decision(...)`，写入 `action_call`。
- `execute_ask_missing_fields`：通过 router 执行动作，写入 `action_result`。
- `execute_refuse_investment_advice`：通过 router 执行动作，写入 `action_result`。
- `execute_run_task_model`：通过 router 执行动作，写入 `action_result`。
- `finalize_result`：调用 `backfill_action_result(...)`，写入 `output/error`。

验收：

- 节点函数单测可直接构造 state 调用。
- 节点返回 `DecisionFlowState` 或 state update，不直接返回 `TaskResult`。

### 5. 定义条件路由函数

新增内部路由函数：

```python
def route_action_name(state: DecisionFlowState) -> str:
    if state.action_call is None:
        return "finalize_result"
    return state.action_call.action
```

路由 key 映射：

```text
ask_missing_fields -> execute_ask_missing_fields
refuse_investment_advice -> execute_refuse_investment_advice
run_task_model -> execute_run_task_model
```

验收：

- 不在 action executor 里写 if/else 分支。
- 条件分支只由 `action_call.action` 决定。

### 6. 编译 LangGraph

在 `DecisionFlow.__init__` 中编译图：

```text
START
-> decide_action
-> validate_action
-> conditional route
   -> execute_ask_missing_fields
   -> execute_refuse_investment_advice
   -> execute_run_task_model
-> finalize_result
-> END
```

实现建议：

- `self.graph = self._build_graph()`
- `_build_graph()` 只负责声明节点和边，不执行业务逻辑。
- `run()` 只创建 initial state、调用 `self.graph.invoke(...)`、保存 `last_state`、返回 `output`。

验收：

- `DecisionFlow.run(...)` 内不再手写顺序串联。
- `DecisionFlow.run(...)` 仍是外部稳定入口。

### 7. 错误收束

需要明确两类错误策略：

1. 业务动作失败：由 `ActionResult(status="failed", error=...)` 进入 `finalize_result`。
2. 图节点异常：短期先让异常暴露给测试，后续再统一包装。

本次不新增通用异常吞掉逻辑，原因：

- 当前手写实现也没有统一捕获 `validate_decision` / `router.route` 异常。
- 过早吞异常会掩盖编排定义错误。

验收：

- `backfill_action_result(...)` 仍是 ActionResult -> TaskResult 的唯一收束点。
- 现有失败任务执行器测试继续通过。

### 8. 更新测试

调整或新增测试：

```text
tests/test_decision_flow.py
```

覆盖：

- 缺失字段路径：`ask_missing_fields`。
- 完整 payload 路径：`run_task_model`。
- 拒答路径：`refuse_investment_advice`。
- action executor 失败路径：`backfill_action_result` 保持兼容。
- `last_state` 在 LangGraph 执行后仍可观察。

新增图结构倾向测试：

- 确认 `DecisionFlow` 初始化后有 compiled graph。
- 确认 route 函数按 `action_call.action` 返回正确 key。

验收命令：

```powershell
python -m pytest tests/test_decision_flow.py tests/test_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
python -m pytest -q
```

### 9. 更新文档与 smoke 说明

更新：

- `docs/1-2/investory-最小编排适用场景.md`
- `src/investory/agent_core/runtime/smoke/README.md`

需要明确：

- LangGraph 只用于 `DecisionFlow` 编排层。
- `TaskExecutor` 仍是最小任务执行单位。
- `TaskExecutionPipeline` 仍是 `TaskExecutor` 内部实现，不是编排层。
- 本阶段不做 checkpoint、memory、parallel branch、human-in-the-loop。

### 10. 最终验收

功能验收：

- Gateway `/tasks` 调用路径不变。
- 缺字段请求返回可补充信息。
- 完整请求仍调用 `TaskExecutor`。
- 拒答路径仍可通过自定义 planner/router 测试。
- `TaskResult` / gateway response schema 不变。

工程验收：

- `DecisionFlow.run()` 不再承担节点串联细节。
- 条件分支由 LangGraph 显式表达。
- `TaskExecutor`、`TaskExecutionPipeline` 不被 LangGraph 污染。
- 测试可证明三个 action 分支和最终 backfill 行为。

## 建议提交切分

1. `build(runtime): add langgraph dependency`
2. `refactor(flow): split decision flow nodes`
3. `feat(flow): compile decision flow with langgraph`
4. `test(flow): cover langgraph decision branches`
5. `docs(flow): document langgraph decision flow refactor`

## 不建议本次做

- 不把 `TaskExecutionPipeline` 改成 LangGraph。
- 不把每个 action executor 改成独立 LangGraph 子图。
- 不引入 checkpoint saver。
- 不引入并行分支。
- 不改 gateway request/response schema。
