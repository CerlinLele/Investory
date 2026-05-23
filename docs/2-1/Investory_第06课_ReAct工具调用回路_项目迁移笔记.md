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

## 更具体的实施步骤

下面步骤按“先不破坏现有任务链路，再逐步接入工具”的原则设计。每一步都应该能独立测试，避免一次性把工具层、action 层、planner 层和 flow 层全部改完。

### Step 0: 固定当前行为基线

目标：

- 确认现有 `finance_qa`、`learning_material_summary`、`instrument_brief` 行为不被工具改造影响。
- 明确第一阶段只新增能力，不改变默认执行路径。

检查文件：

```text
src/investory/agent_core/runtime/task_execution_pipeline.py
src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py
src/investory/agent_core/runtime/flow/learning_qa_decision_planner.py
src/investory/agent_core/actions/router.py
src/investory/agent_core/actions/executors.py
```

建议先跑：

```powershell
python -m pytest tests/test_task_execution_pipeline.py tests/test_learning_qa_orchestration_flow.py tests/test_learning_qa_decision_planner.py tests/test_action_router.py tests/test_action_executors.py -q
```

验收标准：

- 所有现有测试通过。
- 默认 planner 仍然只在缺字段时 `ask_missing_fields`，字段齐全时 `run_task_model`。

### Step 1: 新增工具契约

目标：

- 建立工具层的最小公共接口。
- 让后续 mock 工具和真实 provider 工具有统一输入输出形状。

新增文件：

```text
src/investory/agent_core/tools/__init__.py
src/investory/agent_core/tools/contracts.py
tests/test_tool_contracts.py
```

建议模型：

```python
from typing import Protocol
from pydantic import BaseModel, Field


class ToolSource(BaseModel):
    provider: str
    source_url: str | None = None
    as_of: str | None = None


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: dict | None = None
    error: str | None = None
    elapsed_ms: int | None = None


class ToolExecutionError(Exception):
    pass


class ToolExecutor(Protocol):
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]

    def run(self, payload: BaseModel) -> BaseModel:
        ...
```

测试重点：

- `ToolSource` 可序列化。
- `ToolCallRecord` 可记录成功和失败。
- `ToolExecutor` 是结构协议，不要求具体工具继承基类。

验收标准：

- 工具契约不依赖 LangChain、LangGraph 或 FastAPI。
- 工具契约只依赖标准库和 Pydantic。

### Step 2: 新增 Tool Registry

目标：

- 用注册表管理工具，避免 `if/else` 分散在 planner 或 executor 中。
- 为后续 `RunToolExecutor` 提供统一查找入口。

新增文件：

```text
src/investory/agent_core/tools/registry.py
tests/test_tool_registry.py
```

建议接口：

```python
class UnknownToolError(ValueError):
    pass


class ToolRegistry:
    def __init__(self, tools: list[ToolExecutor] | None = None) -> None:
        self._tools = {tool.name: tool for tool in tools or []}

    def register(self, tool: ToolExecutor) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolExecutor:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise UnknownToolError(f"Unknown tool: {name}") from exc

    def list_names(self) -> list[str]:
        return sorted(self._tools)
```

测试重点：

- 能注册和查找工具。
- 未知工具抛 `UnknownToolError`。
- 重名工具的覆盖策略明确。第一版可以允许覆盖，后续再收紧。

验收标准：

- `ToolRegistry` 不调用工具，只负责管理工具。
- executor 可以通过 registry 查找工具。

### Step 3: 新增第一批 Mock Tools

目标：

- 在没有外部 API 的情况下跑通工具执行。
- 先服务投资学习场景，不接交易能力。

新增文件：

```text
src/investory/agent_core/tools/financial_concepts.py
src/investory/agent_core/tools/instrument_profile.py
src/investory/agent_core/tools/material_extraction.py
src/investory/agent_core/tools/mocks.py
tests/test_financial_concept_tool.py
tests/test_instrument_profile_tool.py
tests/test_material_extraction_tool.py
```

第一批工具：

```text
lookup_financial_concept
lookup_instrument_profile
extract_learning_material_facts
```

建议约束：

- 所有工具只读。
- 所有输出必须有 `uncertainty`。
- 涉及来源的数据必须有 `source` 或 `as_of`。
- 工具不得输出 buy/sell/hold/suitability/allocation 结论。

示例 `lookup_instrument_profile` 输出：

```python
class InstrumentProfileOutput(BaseModel):
    instrument_name_or_code: str
    resolved_name: str
    instrument_type: str
    source_material: str
    facts: list[dict]
    source: ToolSource
    uncertainty: list[str] = Field(default_factory=list)
```

验收标准：

- 三个工具都能独立单测。
- mock 返回稳定，不依赖网络。
- 工具输出可以被 `model_dump()` 后放入 prompt 或 action result。

### Step 4: 扩展 Action Contract 支持 `run_tool`

目标：

- 把工具执行纳入现有 action 链路，而不是绕过 `ActionRouter`。
- 让 planner 的决策仍然先经过 validator。

修改文件：

```text
src/investory/agent_core/contracts/action_contract.py
src/investory/agent_core/actions/validator.py
tests/test_action_contract.py
tests/test_action_validator.py
```

建议新增：

```python
RUN_TOOL = "run_tool"
```

`run_tool` params 建议形状：

```json
{
  "tool_name": "lookup_instrument_profile",
  "payload": {
    "instrument_name_or_code": "VTI"
  }
}
```

validator 需要检查：

- `tool_name` 是非空字符串。
- `payload` 是 dict。
- `task_name` 仍然必须匹配当前 `TaskSpec.name`。
- 第一版可以不在 validator 中检查工具是否存在，把这个交给 `ToolRegistry`。

验收标准：

- `TaskDecision(action="run_tool", ...)` 可以被转换为 `ActionCall`。
- 非法 `tool_name` 和非法 `payload` 会被拒绝。
- 现有三个 action 的测试不回归。

### Step 5: 新增 `RunToolExecutor`

目标：

- 通过 `ActionRouter` 执行工具。
- 把工具成功或失败统一包装成 `ActionResult`。

修改文件：

```text
src/investory/agent_core/actions/executors.py
src/investory/agent_core/actions/router.py
tests/test_action_executors.py
tests/test_action_router.py
```

建议执行流程：

```text
ActionCall(params.tool_name, params.payload)
-> ToolRegistry.get(tool_name)
-> tool.input_model.model_validate(payload)
-> tool.run(validated_payload)
-> tool.output_model.model_validate(result)
-> ActionResult(status="success", result={...})
```

失败处理：

- 未知工具：`ActionResult(status="failed", error=TaskError(...))`
- 参数校验失败：`ActionResult(status="failed", error=TaskError(error_type="input_validation_failed", ...))`
- 工具执行异常：`ActionResult(status="failed", error=TaskError(error_type="provider_unavailable" 或 "unknown_error", ...))`

建议保留 `ToolCallRecord`：

```python
result={
    "tool_name": tool_name,
    "tool_result": output.model_dump(),
    "tool_call": record.model_dump(),
}
```

验收标准：

- `ActionRouter` 默认 registry 包含 `RUN_TOOL` executor。
- `RunToolExecutor` 成功时返回 `ActionResult(status="success")`。
- 工具失败时不会抛穿到 gateway，而是收束成 `ActionResult(status="failed")`。

### Step 6: Planner 支持第一条工具决策规则

目标：

- 让 `instrument_brief` 在缺少 `source_material` 但有 `instrument_name_or_code` 时，可以先调用工具补资料。
- 保持其他任务默认行为不变。

修改文件：

```text
src/investory/agent_core/runtime/flow/learning_qa_decision_planner.py
tests/test_learning_qa_decision_planner.py
```

建议第一条规则：

```text
task_name == "instrument_brief"
payload has instrument_name_or_code
payload missing source_material
-> run_tool lookup_instrument_profile
```

注意：

- 如果 `instrument_name_or_code` 也缺失，仍然走 `ask_missing_fields`。
- 如果用户已经提供 `source_material`，仍然走 `run_task_model`。
- 不要让 planner 在第一版调用 LLM 选工具。

验收标准：

- `instrument_brief` 只缺 `source_material` 时返回 `run_tool` decision。
- 缺两个字段时仍返回 `ask_missing_fields`。
- 完整输入仍返回 `run_task_model`。

### Step 7: Flow 处理工具结果回填

目标：

- 让 `run_tool` 后可以继续进入 `run_task_model`。
- 第一版只支持单次工具补全，不做完整 ReAct Loop。

修改文件：

```text
src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py
tests/test_learning_qa_orchestration_flow.py
```

建议新增节点：

```text
NODE_RUN_TOOL
NODE_APPLY_TOOL_RESULT
```

推荐链路：

```text
classify_request
-> validate_decision_contract
-> run_tool
-> apply_tool_result
-> answer_learning_question
-> build_task_response
```

`apply_tool_result` 第一版只处理 `lookup_instrument_profile`：

```text
tool_result.source_material -> payload.source_material
```

失败路径：

```text
run_tool failed -> build_task_response
```

验收标准：

- 工具成功后会继续执行模型任务。
- 工具失败后返回清晰错误，不继续调用模型。
- 现有 `ask_missing_fields`、`run_task_model`、`refuse_investment_advice` 路径不回归。

### Step 8: Gateway 与 Smoke 验证

目标：

- 从 HTTP `/tasks` 跑通工具补全链路。
- 保持 API response shape 不变。

涉及文件：

```text
src/investory/gateway/api.py
tests/test_gateway_task_api.py
src/investory/agent_core/runtime/smoke/task.py
```

建议新增测试请求：

```json
{
  "task_type": "brief",
  "payload": {
    "instrument_name_or_code": "VTI"
  }
}
```

预期：

- planner 判断需要 `lookup_instrument_profile`。
- mock tool 返回 `source_material`。
- flow 把 `source_material` 回填。
- 最终仍返回 `TaskResponse(ok=true, task_name="instrument_brief", result=...)`。

验收标准：

- gateway 测试通过。
- response 不暴露内部异常堆栈。
- 如需要暴露工具调用记录，应放在明确字段中，不混进最终学习回答。

### Step 9: 第二阶段再做独立 ReAct Loop

目标：

- 当单次工具补全稳定后，再实现多轮 Reason / Act / Observe。

新增文件：

```text
src/investory/agent_core/runtime/flow/react_tool_loop_flow.py
tests/test_react_tool_loop_flow.py
```

状态模型建议：

```python
class ReactToolLoopState(BaseModel):
    task_id: str
    question: str
    payload: dict
    step: int = 0
    max_steps: int = 4
    observations: list[ToolObservation] = []
    final_answer: dict | None = None
    error: TaskError | None = None
```

每轮节点：

```text
reason
-> validate_tool_calls
-> act
-> observe
-> should_continue
```

第二阶段必须有的保护：

- `max_steps`
- 每轮最多工具数
- 工具白名单
- timeout
- tool error normalization
- 最后一次 grace final answer

验收标准：

- 达到 `max_steps` 不会无限循环。
- 工具失败会变成 observation，而不是直接崩溃。
- final answer 必须声明使用了哪些 observations，以及哪些信息仍不确定。

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
