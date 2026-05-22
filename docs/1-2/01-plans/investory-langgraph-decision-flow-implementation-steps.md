# Investory LangGraph LearningQaOrchestrationFlow 重构实施步骤

## 目标

把当前手写顺序执行的 `DecisionFlow` 重构为 LangGraph `StateGraph`，并统一命名为 `LearningQaOrchestrationFlow`。

本次只处理编排层：

- 保留 `LearningQaOrchestrationFlow.run(spec, payload, request_id=None) -> TaskResult` 对外契约。
- 保留 `TaskExecutor` 作为最小任务执行单位。
- 保留 `TaskExecutionPipeline`、`RequestRunner`、prompt、模型调用与网关协议不变。
- 用 LangGraph 显式表达“决策 -> 条件分支 -> 执行动作 -> 统一返回”。

## 当前基线

当前代码路径：

```text
Gateway
-> LearningQaOrchestrationFlow.run(...)
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
-> LearningQaOrchestrationFlow.run(...)
   -> compiled LangGraph.invoke(initial_state)
      -> classify_request
      -> validate_decision_contract
      -> route by action
         -> ask_for_missing_input
         -> refuse_advice_and_redirect
         -> answer_learning_question
      -> build_task_response
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

## 命名调整清单（本次采用）

```text
Flow class:
DecisionFlow -> LearningQaOrchestrationFlow

State:
DecisionFlowState -> LearningQaFlowState

Routing function:
route_action_name -> route_by_action_key

Graph nodes:
decide_action -> classify_request
validate_action -> validate_decision_contract
execute_action -> execute_routed_action (Layer 1 temporary node)
execute_ask_missing_fields -> ask_for_missing_input
execute_run_task_model -> answer_learning_question
execute_refuse_investment_advice -> refuse_advice_and_redirect
finalize_result -> build_task_response
```

不改名（保持契约稳定）：

- `action` 枚举值：`ask_missing_fields` / `run_task_model` / `refuse_investment_advice`
- `TaskResult` 和 gateway request/response schema 字段

兼容策略：

- 短期保留 `DecisionFlow = LearningQaOrchestrationFlow` 别名，避免一次性影响导入方。
- 测试和 gateway 导入逐步迁移到新类名后，再移除别名。

## Implementation Steps

### Layer 0：准备层（不改行为）

#### Step 0.1 基线快照

```powershell
python -m pytest tests/test_decision_flow.py tests/test_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
python -m pytest tests/test_task_executor.py tests/test_task_execution_pipeline.py -q
```

通过条件：

- `LearningQaOrchestrationFlow` 三类路径稳定：缺字段、执行模型、拒答。
- `TaskExecutor` / `TaskExecutionPipeline` 测试不受影响。

#### Step 0.2 依赖准备

在 `pyproject.toml` 增加 `langgraph` 固定版本，并更新 lock。

```powershell
python -m pip install -e .[dev]
python -c "from langgraph.graph import StateGraph, START, END; print('ok')"
python -m pip freeze > requirements.lock.txt
```

通过条件：

- 本地可导入 `StateGraph`、`START`、`END`。
- 依赖声明和 lock 一致。

### Layer 1：主干骨架（先线性）

目标：先把 `LearningQaOrchestrationFlow` 改成 graph 调用，但仍按线性路径走，不做分支。

#### Step 1.1 固定状态对象

继续使用现有状态结构，并改名为 `LearningQaFlowState`（可先别名过渡）。

通过条件：

- `last_state` 仍可观察最终状态。

#### Step 1.2 拆主干节点（最小集）

先只拆 4 个节点：

```text
classify_request
validate_decision_contract
execute_routed_action   # 临时总执行节点
build_task_response
```

说明：

- 此阶段的 `execute_routed_action` 内部还允许走 router，先不拆三个 action 节点。

#### Step 1.3 编译线性图

```text
START -> classify_request -> validate_decision_contract -> execute_routed_action -> build_task_response -> END
```

通过条件：

- `LearningQaOrchestrationFlow.run(...)` 已改为 `graph.invoke(initial_state)`。
- 对外签名保持 `run(spec, payload, request_id=None) -> TaskResult`。

### Layer 2：引入条件路由点

目标：把 “按 action 分流” 从 node 内部 if/else 提升到 graph 路由。

执行约定（2026-05-22）：在 Layer 1/Step 1.x 阶段继续保持当前 `DecisionPlanner` 分类边界（默认仅 `ask_missing_fields` / `run_task_model`）。`refuse_investment_advice` 的分类规则延后到 Layer 2/3 一并补齐，不在 Step 1.2 范围内新增业务判定。

#### Step 2.1 路由函数

```python
def route_by_action_key(state: LearningQaFlowState) -> str:
    if state.action_call is None:
        return "build_task_response"
    return state.action_call.action
```

术语约束：

- `action` 不是 node。
- `action` 不是 edge。
- `action` 是 conditional routing key。

#### Step 2.2 三个 action 执行节点

把 `execute_routed_action` 拆成：

```text
ask_for_missing_input
answer_learning_question
refuse_advice_and_redirect
```

通过条件：

- 分支决策只由 `route_by_action_key` 返回值决定。
- action executor 内不写路由 if/else。

执行约定（2026-05-22 补充）：

- `validate_decision_contract` 在路由前只做公共校验与 `action_call` 构建：
  - validate allowed action
  - validate task_name match
  - build action_call
- 各 action 的参数细校验下沉到对应 action 执行节点（或其调用链）：
  - `ask_for_missing_input` 负责 `missing_fields` 相关约束
  - `answer_learning_question` 负责 `payload` 相关约束
  - `refuse_advice_and_redirect` 负责拒答参数相关约束

### Layer 3：图结构定型

目标：形成最终目标图，并清理过渡代码。

#### Step 3.1 图连线定型

```text
START
-> classify_request
-> validate_decision_contract
-> conditional route(action key)
   -> ask_for_missing_input
   -> answer_learning_question
   -> refuse_advice_and_redirect
-> build_task_response
-> END
```

#### Step 3.2 清理过渡路径

- 删除或收敛临时 `execute_routed_action`。
- 确保 `run()` 仅做：
  - 创建 initial state
  - graph invoke
  - 写入 `last_state`
  - 返回 `output`

通过条件：

- `LearningQaOrchestrationFlow.run()` 不再手写节点串联。

### Layer 4：环节拆细与错误收束

目标：把单节点内部再拆成明确子环节，便于维护和测试。

执行约定（2026-05-22 补充）：

- 本轮先不做 Layer 4 的“环节拆细”落地实现（Step 4.1 ~ Step 4.4 延后）。
- 先保持当前节点边界稳定，优先完成图结构与分支路由收口。

#### Step 4.1 `classify_request` 子环节

```text
read input_payload
-> planner.decide(spec, payload)
-> write state.decision
```

#### Step 4.2 `validate_decision_contract` 子环节

```text
validate allowed action
-> validate task_name match
-> build action_call
```

#### Step 4.3 `execute_*` 子环节

```text
validate action-specific params
-> router.route(action_call)
-> executor.execute(action_call, spec)
-> write state.action_result
```

#### Step 4.4 `build_task_response` 子环节

```text
backfill_action_result(action_result)
-> write output
-> write error
```

错误策略保持：

1. 业务失败：`ActionResult(status="failed", error=...)` 经 `build_task_response` 统一收束为 `TaskResult(ok=False, error=...)`。
2. 图节点异常：短期暴露给测试，不额外吞异常（不在 flow 内吞错）。
3. 测试覆盖要求：
   - 覆盖业务失败收束路径（返回失败 `TaskResult`）。
   - 覆盖节点异常冒泡路径（直接抛异常）。

### Layer 5：测试与文档收口

#### Step 5.1 测试覆盖

重点文件：`tests/test_decision_flow.py`

必测：

- `ask_missing_fields` 路径。
- `run_task_model` 路径。
- `refuse_investment_advice` 路径。
- `backfill_action_result` 失败收束路径（通过 `build_task_response`）。
- `last_state` 在 graph 执行后可观察。

补充：

- graph 已编译（初始化后可调用）。
- route 函数按 `action_call.action` 返回正确 key。

#### Step 5.2 回归命令

```powershell
python -m pytest tests/test_decision_flow.py tests/test_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
python -m pytest -q
```

#### Step 5.3 文档同步

更新：

- `docs/1-2/investory-最小编排适用场景.md`
- `src/investory/agent_core/runtime/smoke/README.md`

需要明确：

- LangGraph 只用于 `LearningQaOrchestrationFlow` 编排层。
- `TaskExecutor` 仍是最小任务执行单位。
- `TaskExecutionPipeline` 仍是 `TaskExecutor` 内部实现。

### 最终完成标准

功能完成：

- Gateway `/tasks` 行为与响应 schema 不变。
- 三种 action 分支行为可区分且稳定（action 值不改）。

工程完成：

- 编排逻辑由 `StateGraph` 显式表达。
- `LearningQaOrchestrationFlow.run()` 只保留入口职责。
- `TaskExecutor` / `TaskExecutionPipeline` 边界不被侵入。

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
