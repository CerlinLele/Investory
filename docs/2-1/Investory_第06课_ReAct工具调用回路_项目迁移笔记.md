# Investory 第06课 ReAct 工具调用回路项目迁移笔记

## 背景

课程主题是“工具调用回路与 ReAct Loop”。核心内容包括：

- 工具调用的四个节点：模型收到 prompt + tool schema、模型输出工具调用、系统执行工具并回填结果、模型基于 observation 继续生成。
- Tool schema 的作用：用 `name`、`description`、`parameters` 告诉模型有哪些工具、何时调用、如何传参。
- 两种工具调用路径：模型原生 function calling，以及结构化输出 + 外部编排。
- ReAct Loop：Reason -> Act -> Observe 多轮循环，直到信息足够或达到最大步数。
- 真实工程优化：工具调用日志、最大步数、错误回填、并行工具执行、最后一次 grace call。

对 Investory 来说，这节课的价值不在于立刻完整复刻 ReAct Loop，而在于把工具抽象、工具执行、工具日志和工具结果回填能力补齐。

## 当前 Investory 状态

项目现在已经有一部分适合接工具的基础：

- `TaskSpec`：定义任务名、prompt、输入模型、输出模型。
- `RequestRunner`：通过 LangChain `with_structured_output` 做结构化模型调用。
- `TaskExecutionPipeline`：负责输入校验、prompt 构建、模型调用、结果封装。
- `LearningQaOrchestrationFlow`：使用 LangGraph 串联 planner、validator、router、executor。
- `ActionRouter`：按 action 分发到对应 executor。
- `ActionResult`：统一表达 action 执行结果。
- `mock_tools_enabled`：配置里已经预留 mock tool 开关。

但项目还没有真正的工具层：

- 没有 `agent_core/tools`。
- 没有 tool schema / registry。
- 没有 `run_tool` action。
- 没有 tool call log。
- 没有多轮 ReAct loop。

因此，最合理的迁移方式是渐进式接入。

## 可以直接吸收的课程内容

### 1. Tool Schema

课程里 tool schema 的三个核心字段可以直接变成 Investory 的工具契约：

```text
name        工具名
description 工具用途说明
parameters  参数 schema
```

建议新增：

```text
src/investory/agent_core/tools/
  __init__.py
  contracts.py
  registry.py
  mocks.py
  financial_concepts.py
  material_extraction.py
  instrument_profile.py
```

建议工具接口：

```python
from typing import Protocol
from pydantic import BaseModel


class ToolExecutor(Protocol):
    name: str
    description: str

    def run(self, payload: BaseModel) -> BaseModel:
        ...
```

### 2. Tool Call Log

课程里展示了 `tool_logs`，这对 Investory 很重要，因为投资学习类应用需要可追踪来源和审计记录。

建议新增：

```python
from pydantic import BaseModel


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: dict | None = None
    error: str | None = None
    elapsed_ms: int | None = None
```

后续可以把 `ToolCallRecord` 放进：

- `ActionResult.result`
- flow state
- gateway response 的 debug 字段
- 日志系统

### 3. 结构化输出 + 外部编排

课程里对比了“模型原生 function calling”和“结构化输出 + TriggerFlow 编排”。

Investory 当前更适合第二条路径，因为项目已经有：

- Pydantic schema
- `with_structured_output`
- planner
- validator
- `ActionRouter`
- executor

所以可以让 planner 输出结构化 decision：

```json
{
  "action": "run_tool",
  "task_name": "instrument_brief",
  "reason": "Need instrument source material before generating the brief.",
  "params": {
    "tool_name": "lookup_instrument_profile",
    "payload": {
      "instrument_name_or_code": "VTI"
    }
  }
}
```

系统再校验 decision，转成 `ActionCall`，最后由 executor 执行工具。

### 4. Max Steps

课程里的 ReAct Loop 有 `max_steps`，这是实际工程必须保留的保护机制。

Investory 后续如果做多轮工具 loop，应强制加入：

```python
max_steps: int = 4
```

并且达到上限时必须返回安全结果：

```text
当前信息不足以继续可靠查询，请补充材料或缩小问题范围。
```

### 5. Observation 回填

ReAct 的关键不是“调用工具”，而是把工具结果作为 observation 放回状态中。

Investory 可以把 observation 设计成：

```python
class ToolObservation(BaseModel):
    tool_name: str
    output: dict
    source: str | None = None
    as_of: str | None = None
    uncertainty: list[str] = []
```

然后让最终回答严格基于 observations 和用户材料生成。

## 推荐迁移顺序

### Phase 1: 工具基础层

先加工具契约、registry、mock 工具，不改模型调用方式。

优先工具：

- `lookup_financial_concept`
- `extract_learning_material_facts`
- `lookup_instrument_profile`

这一阶段目标是让工具能独立测试。

### Phase 2: 新增 `run_tool` action

扩展当前 action contract：

```python
RUN_TOOL = "run_tool"
```

需要改动：

```text
src/investory/agent_core/contracts/action_contract.py
src/investory/agent_core/actions/validator.py
src/investory/agent_core/actions/router.py
src/investory/agent_core/actions/executors.py
```

新增 executor：

```python
class RunToolExecutor:
    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        ...
```

### Phase 3: Planner 支持工具决策

当前 `LearningQaDecisionPlanner` 主要判断缺字段和执行模型。

可以扩展为：

```text
缺必填字段 -> ask_missing_fields
请求买卖建议 -> refuse_investment_advice
需要标的资料 -> run_tool
资料齐全 -> run_task_model
```

这里暂时不需要让模型自己选工具，可以先用规则判断。

### Phase 4: 工具结果增强 payload

第一版工具结果不必进入多轮 ReAct，可以先作为 task payload enrichment。

推荐链路：

```text
planner -> run_tool -> tool result -> enrich payload -> run_task_model
```

例如：

```json
{
  "instrument_name_or_code": "VTI",
  "source_material": "Tool-provided factsheet text..."
}
```

这条路径对现有 `instrument_brief` 最有用。

### Phase 5: 单独实现 ReAct Flow

完整 ReAct Loop 不建议塞进 `TaskExecutionPipeline`。

如果后续需要多工具、多步推理，建议新增独立 flow：

```text
src/investory/agent_core/runtime/flow/react_tool_loop_flow.py
```

这个 flow 可以包含：

```text
Reason -> Act -> Observe -> Reason
```

并强制具备：

- `max_steps`
- `tool_history`
- timeout
- retry
- tool error normalization
- final answer fallback

## 不建议现在做的内容

### 不建议直接上模型原生 function calling

原因：

- 当前 `RequestRunner` 的主能力是 structured output。
- 直接接 function calling 会改变模型调用协议。
- 当前测试体系围绕 `TaskResult`、`ActionResult` 和 Pydantic 输出构建。
- 工具调用如果由模型自由控制，安全边界会更难收敛。

### 不建议把 ReAct Loop 塞进 `TaskExecutionPipeline`

`TaskExecutionPipeline` 现在是稳定的单次任务执行器：

```text
input validation -> prompt build -> model call -> result
```

ReAct Loop 是多轮工具编排，应放在 orchestration flow 层，而不是底层 pipeline。

### 不建议封装交易执行工具

短期不要封装：

- `place_order`
- `rebalance_portfolio`
- `recommend_buy_sell`
- `calculate_position_size`
- `predict_price_target`

这会把 Investory 从投资学习助手推向投资建议或交易执行系统，不符合当前 prompt 和安全边界。

## 对 Investory 最有价值的实现清单

第一批建议做：

1. `ToolExecutor` protocol
2. `ToolRegistry`
3. `ToolCallRecord`
4. mock `lookup_financial_concept`
5. mock `lookup_instrument_profile`
6. mock `extract_learning_material_facts`
7. `RUN_TOOL` action
8. `RunToolExecutor`
9. planner 规则扩展
10. 工具结果回填到 task payload

第二批再做：

1. 多工具并行执行
2. tool timeout / retry
3. tool observation history
4. 独立 `ReactToolLoopFlow`
5. max steps + grace final answer

## 最终判断

第06课内容能给 Investory 增加的能力可以分成两层：

第一层是“工具工程能力”，应该马上加：

- tool schema
- tool registry
- tool executor
- tool logs
- `run_tool` action
- mock tools

第二层是“ReAct 多轮推理能力”，应该后置：

- Reason / Act / Observe loop
- 多工具并行
- max steps
- observation history
- grace call

以当前项目阶段看，先做第一层更合适。这样能复用现有 `ActionRouter`、`ActionResult`、`TaskSpec` 和 `TaskExecutionPipeline`，同时为后续完整 ReAct Loop 留出清晰入口。
