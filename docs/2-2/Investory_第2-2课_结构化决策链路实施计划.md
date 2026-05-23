# Investory 第 2-2 课：结构化决策链路实施计划

## 一、目标

本次实践目标是把第 2-2 课里的结构化决策链路落到 Investory 当前项目中。

课程中的目标链路是：

```text
user input
-> planner
-> TaskDecision
-> ActionValidator
-> ActionCall
-> ActionRouter
-> ActionExecutor
-> ActionResult
-> ResultBackfill
-> replan or final response
```

Investory 当前已经有一条较小的任务执行链路：

```text
TaskRequest
-> resolve_task_spec
-> decide_missing_fields_action
-> TaskExecutor
-> MinimalTaskFlow
-> prepare_context
-> call_model
-> finalize_result
```

本次不建议直接做大型 agent 框架，而是在现有代码上补齐一个可校验、可路由、可执行、可回填的最小闭环：

```text
TaskRequest
-> build_task_decision
-> validate_decision
-> build_action_call
-> route_action
-> execute_action
-> backfill_action_result
-> build_task_response
```

第一版仍然围绕已有任务能力展开：

```text
finance_qa
learning_material_summary
instrument_brief
ask_missing_fields
refuse_investment_advice
```

暂不接入外部行情、基金数据库、交易、账户、组合分析或实时检索。

## 二、当前项目状态

已具备的基础：

```text
src/investory/agent_core/contracts/task_spec.py
src/investory/agent_core/contracts/result_types.py
src/investory/agent_core/contracts/flow_state.py
src/investory/agent_core/contracts/action_decision.py
src/investory/agent_core/runtime/minimal_flow.py
src/investory/agent_core/runtime/task_executor.py
src/investory/agent_core/runtime/request_runner.py
src/investory/gateway/api.py
src/investory/gateway/schemas.py
src/investory/gateway/routing.py
```

当前已经落地的 2-1 能力：

```text
instrument_brief task 已注册
缺少必填字段时可以生成 ask_missing_fields action
gateway 会在执行模型前拦截 missing fields
TaskExecutor 可以执行完整 task 并返回 TaskResult
```

当前缺口：

```text
AskMissingFieldsAction 还是单独对象，不是统一 TaskDecision
gateway 内联了 action 判断，没有统一 ActionValidator / Router / Executor
缺少 ActionCall 和 ActionResult 合约
TaskFlowState 没有保存 decision、action_call、action_result
模型执行结果和动作执行结果还没有统一回填路径
失败兜底只覆盖模型调用链路，还没有覆盖 action 执行链路
```

## 三、实施原则

这次实践遵守三个边界。

第一，模型只提出或参与决策，系统负责校验和执行。

```text
模型/规则层输出 TaskDecision
系统校验 TaskDecision
系统转换成 ActionCall
系统按 registry 路由 executor
executor 返回 ActionResult
系统回填状态并决定最终响应
```

第二，第一版 planner 可以先做成确定性规则，不急着调用大模型。

原因是当前 HTTP API 已经要求传入 `task_type` 和 `payload`，所以系统有足够信息判断：

```text
字段缺失 -> ask_missing_fields
字段完整 -> run_task_model
高风险买卖建议 -> refuse_investment_advice
未知任务 -> 继续沿用 gateway 的 UnknownTaskTypeError
```

等 action 链路稳定后，再把自然语言 planner 或 LLM planner 接进来。

第三，先统一动作链路，再扩展动作数量。

不要一开始新增太多 action。第一阶段只实现能验证闭环的动作：

```text
ask_missing_fields
run_task_model
refuse_investment_advice
```

后续再加入：

```text
convert_to_learning_framework
suggest_study_plan
query_instrument_info_future
```

## 四、建议目录结构

建议新增或调整为：

```text
src/investory/agent_core/contracts/
  action_decision.py      # TaskDecision 和兼容现有 AskMissingFieldsAction
  action_contract.py      # ActionCall、ActionResult、ActionStatus

src/investory/agent_core/actions/
  __init__.py
  validator.py            # 校验 action 是否允许、参数是否完整
  router.py               # action name -> executor
  executors.py            # ask_missing_fields / run_task_model / refuse

src/investory/agent_core/runtime/
  flow/
    learning_qa_orchestration_flow.py   # 串联 decision -> validate -> route -> execute -> backfill
    learning_qa_decision_planner.py     # 第一版确定性 planner
```

现有文件保留：

```text
src/investory/agent_core/runtime/minimal_flow.py
src/investory/agent_core/runtime/task_executor.py
```

`MinimalTaskFlow` 继续负责单个 task 的模型调用；新的 action executor 只是在需要执行模型时调用它。

## 五、核心合约设计

### 1. TaskDecision

建议把当前 `AskMissingFieldsAction` 升级为统一决策 schema。

```python
from typing import Any, Literal

from pydantic import BaseModel, Field


ActionName = Literal[
    "ask_missing_fields",
    "run_task_model",
    "refuse_investment_advice",
]


class TaskDecision(BaseModel):
    action: ActionName
    task_name: str
    reason: str
    confidence: float = Field(ge=0, le=1, default=1.0)
    params: dict[str, Any] = Field(default_factory=dict)
    user_message: str | None = None
    need_user_confirmation: bool = False
```

第一版参数约定：

```text
ask_missing_fields.params:
  missing_fields: list[str]

run_task_model.params:
  payload: dict

refuse_investment_advice.params:
  refused_reason: str
  allowed_alternative: str | None
```

兼容策略：

```text
保留 build_ask_missing_fields_action 的 public 行为
内部可以改为返回 TaskDecision，或新增 build_missing_fields_decision
测试先覆盖新 schema，再逐步替换旧命名
```

### 2. ActionCall

`TaskDecision` 是“模型或 planner 的建议”，`ActionCall` 是“系统准备执行的调用”。

```python
class ActionCall(BaseModel):
    action: ActionName
    task_name: str
    params: dict[str, Any]
    decision_reason: str
    request_id: str | None = None
```

转换规则：

```text
TaskDecision
-> ActionValidator 校验
-> ActionCall
```

只有通过校验的 decision 才能变成 `ActionCall`。

### 3. ActionResult

动作执行结果统一收束为：

```python
ActionStatus = Literal["success", "failed", "requires_user_input", "refused"]


class ActionResult(BaseModel):
    action: ActionName
    task_name: str
    status: ActionStatus
    result: dict[str, Any] | None = None
    error: TaskError | None = None
    user_message: str | None = None
```

状态含义：

```text
success:
  动作执行成功，可以返回 result

requires_user_input:
  需要用户补充字段，通常来自 ask_missing_fields

refused:
  命中风险边界，拒绝原请求并给出学习型替代方向

failed:
  执行失败，需要进入错误兜底
```

## 六、第一阶段：统一缺字段追问链路

目标：

```text
把当前 gateway 里的 decide_missing_fields_action 拦截逻辑
迁移到 decision_flow 中
```

当前流程：

```text
gateway.execute_task_request
-> decide_missing_fields_action
-> if action: return TaskResponse
-> executor.run
```

目标流程：

```text
gateway.execute_task_request
-> LearningQaOrchestrationFlow.run(task_request)
-> TaskResponse
```

内部链路：

```text
resolve_task_spec
-> build_task_decision
-> validate_decision
-> build_action_call
-> execute_action
-> backfill_action_result
-> build_task_response
```

第一阶段验收标准：

```text
缺少 instrument_brief.source_material 时，返回 ask_missing_fields
字段完整时，仍然执行原 MinimalTaskFlow
现有 gateway response shape 不变
现有测试全部通过
```

建议新增测试：

```text
tests/test_action_contract.py
tests/test_action_validator.py
tests/test_action_router.py
tests/test_learning_qa_orchestration_flow.py
```

重点用例：

```text
TaskDecision action 不在枚举内时校验失败
ask_missing_fields 缺少 missing_fields 时校验失败
run_task_model 缺少 payload 时校验失败
router 可以找到 ask_missing_fields executor
router 可以找到 run_task_model executor
LearningQaOrchestrationFlow 对缺字段请求返回 requires_user_input
LearningQaOrchestrationFlow 对完整请求调用 TaskExecutor
```

## 七、第二阶段：引入 run_task_model action

目标：

```text
把“执行模型任务”本身也视为一个 action
```

这样 Investory 的执行链路会更接近课程里的设计：

```text
TaskDecision(action="run_task_model")
-> ActionCall
-> RunTaskModelExecutor
-> TaskExecutor.run
-> ActionResult(status="success" or "failed")
-> ResultBackfill
```

建议实现：

```text
RunTaskModelExecutor 接收 TaskSpec、payload、TaskExecutor
内部调用 executor.run(spec, payload)
把 TaskResult.ok=True 转成 ActionResult.success
把 TaskResult.ok=False 转成 ActionResult.failed
```

这一步完成后，`MinimalTaskFlow` 不需要知道 action 的存在；它仍然只负责：

```text
prepare_context
call_model
finalize_result
```

`LearningQaOrchestrationFlow` 负责更外层的决策和路由。

## 八、第三阶段：增加风险拒绝 action

目标：

```text
为投资建议类高风险请求建立显式动作
```

建议 action：

```text
refuse_investment_advice
```

第一版不做复杂意图识别，只在明确字段或显式 task_type 下验证链路。例如后续如果加入自然语言入口，可以对这类输入触发：

```text
现在能不能买？
这只基金未来会涨吗？
帮我决定是否买入。
```

返回结果示例：

```json
{
  "action": "refuse_investment_advice",
  "task_name": "instrument_brief",
  "status": "refused",
  "user_message": "I cannot decide whether you should buy or sell. I can help turn this into an educational brief based on materials you provide."
}
```

系统边界：

```text
不判断涨跌
不推荐买卖
不根据用户资产情况给配置建议
允许转成学习型解释、材料摘要、风险概念说明
```

## 九、第四阶段：ResultBackfill 与状态扩展

当前 `TaskFlowState`：

```python
class TaskFlowState(BaseModel):
    task_id: str
    task_name: str
    input_payload: dict[str, Any]
    status: TaskFlowStatus = "pending"
    validated_input: dict[str, Any] | None = None
    messages: list[Any] | None = None
    model_result: dict[str, Any] | None = None
    output: TaskResult | None = None
    error: TaskError | None = None
```

建议扩展为：

```python
decision: TaskDecision | None = None
action_call: ActionCall | None = None
action_result: ActionResult | None = None
```

也可以先不改 `TaskFlowState`，新增更外层状态：

```python
class LearningQaFlowState(BaseModel):
    task_id: str
    task_name: str
    input_payload: dict[str, Any]
    decision: TaskDecision | None = None
    action_call: ActionCall | None = None
    action_result: ActionResult | None = None
    output: TaskResult | None = None
    error: TaskError | None = None
```

推荐第一版使用 `LearningQaFlowState`，原因是：

```text
MinimalTaskFlow 仍保持简单
LearningQaOrchestrationFlow 独立承载 2-2 课的新概念
不会把模型调用状态和动作编排状态混在一起
```

回填规则：

```text
ActionResult.success:
  写入 output.ok=True
  result 来自 action_result.result

ActionResult.requires_user_input:
  写入 output.ok=True
  result 包含 action、missing_fields、user_message、reason

ActionResult.refused:
  写入 output.ok=True
  result 包含 refusal 和 allowed alternative

ActionResult.failed:
  写入 output.ok=False
  error 来自 action_result.error
```

## 十、第五阶段：为 LLM planner 预留接口

第一版 `DecisionPlanner` 可以是确定性的：

```text
spec + payload
-> missing fields?
-> TaskDecision
```

后续预留接口：

```python
class DecisionPlanner:
    def decide(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskDecision:
        ...
```

以后如果要从自然语言入口升级，可以新增：

```text
LLMDecisionPlanner
NaturalLanguageTaskRequest
TaskSelectionDecision
```

但当前不建议马上做。原因是当前 Investory 的公开 API 已经有 `task_type`，先把 action 链路做稳更符合第 2-2 课的重点。

## 十一、建议执行顺序

### Step 1：新增 action contract

文件：

```text
src/investory/agent_core/contracts/action_contract.py
```

内容：

```text
ActionName
TaskDecision
ActionCall
ActionResult
ActionStatus
```

测试：

```text
tests/test_action_contract.py
```

验收：

```text
schema 能校验 action 枚举
confidence 范围为 0 到 1
ActionResult 能表达 success / failed / requires_user_input / refused
```

### Step 2：新增 validator

文件：

```text
src/investory/agent_core/actions/validator.py
```

职责：

```text
校验 action 是否允许
校验 params 是否包含必要字段
校验 missing_fields 是否属于 TaskSpec.input_model
校验 run_task_model 的 payload 是否存在
校验 refuse action 是否有 user_message 或 refused_reason
```

当前落地逻辑：

```text
validate_decision(decision, spec, request_id=None) -> ActionCall
```

`validator` 的定位是从“planner 的建议”到“系统批准执行的调用”的安全门：

```text
TaskDecision = planner 的建议
ActionCall = 系统校验后批准执行的调用
```

第一层校验是 action 白名单。当前只允许：

```text
ask_missing_fields
run_task_model
refuse_investment_advice
```

虽然 `TaskDecision` 的 Pydantic schema 已经限制 action 枚举，`validator` 仍然保留白名单校验，用于防止测试 mock、`model_construct()` 或后续 LLM 原始输出转换绕过 schema。

第二层校验是 `decision.task_name` 必须和当前 `TaskSpec.name` 一致。这样可以避免已经 resolve 出来的任务定义和 planner 产出的 decision 错位。

第三层校验按 action 分支处理：

```text
ask_missing_fields:
  params.missing_fields 必须存在
  missing_fields 必须是非空 list
  missing_fields 每一项必须是字符串
  missing_fields 每一项必须属于 spec.input_model.model_fields

run_task_model:
  params.payload 必须存在
  payload 必须是 dict

refuse_investment_advice:
  必须有 decision.user_message 或 params.refused_reason 之一
  refused_reason 如果存在，必须是非空字符串
  allowed_alternative 如果存在，必须是非空字符串
```

全部校验通过后，`validator` 生成 `ActionCall`：

```text
action = decision.action
task_name = decision.task_name
params = decision.params
decision_reason = decision.reason
request_id = request_id
```

后续 `ActionRouter` 和 executor 可以假设拿到的 `ActionCall` 已经满足基本合约，不需要重复处理缺字段、非法字段名或 task 错位问题。

测试：

```text
tests/test_action_validator.py
```

### Step 3：新增 router 和 executors

文件：

```text
src/investory/agent_core/actions/router.py
src/investory/agent_core/actions/executors.py
```

第一版 executor：

```text
AskMissingFieldsExecutor
RunTaskModelExecutor
RefuseInvestmentAdviceExecutor
```

当前 router 落地逻辑：

`router.py` 的职责是根据 `ActionCall.action` 找到对应的 executor。它不负责决定应该做什么，也不负责执行动作，只负责把已经通过 validator 的 `ActionCall` 分发给正确的执行器。

在完整链路中的位置是：

```text
TaskDecision
-> validate_decision
-> ActionCall
-> ActionRouter
-> ActionExecutor
```

`ActionRouter` 初始化时有两种用法。

第一种是不传 `executors`，使用默认注册表：

```text
ask_missing_fields -> AskMissingFieldsExecutor
run_task_model -> RunTaskModelExecutor
refuse_investment_advice -> RefuseInvestmentAdviceExecutor
```

其中 `run_task_model` 比较特殊，它内部需要调用已有 `TaskExecutor`，所以 `ActionRouter` 支持传入 `task_executor`，再交给 `RunTaskModelExecutor` 复用：

```text
ActionRouter(task_executor=some_task_executor)
```

这方便 gateway 后续注入已有 executor，也方便测试用 fake executor 验证调用。

第二种是传入自定义 `executors` registry：

```text
ActionRouter(executors={
  "ask_missing_fields": fake_executor
})
```

这主要用于单元测试，或者以后局部替换某个 action 的执行器。

真正路由发生在：

```text
ActionRouter.route(call)
```

逻辑是：

```text
读取 call.action
-> 从 self._executors 查找 executor
-> 找到则返回 executor
-> 找不到则抛 ActionRoutingError
```

`route_action(call, router=None)` 是一个便捷函数。没有传 router 时会创建默认 `ActionRouter`，传入 router 时则复用调用方提供的 registry。

因此，`router.py` 本质上是 action executor registry。后续新增 action 时，需要新增对应 executor，并把它注册到默认 registry 或调用方自定义 registry 中。

当前 executors 落地逻辑：

`executors.py` 负责真正执行 action。它接收已经通过 validator 的 `ActionCall`，返回统一的 `ActionResult`。

在完整链路中的位置是：

```text
TaskDecision
-> validate_decision
-> ActionCall
-> ActionRouter
-> ActionExecutor
-> ActionResult
```

所有 executor 都遵守同一个接口约定：

```text
execute(call: ActionCall, spec: TaskSpec) -> ActionResult
```

代码中用 `ActionExecutor(Protocol)` 表达这个接口约定：

```python
class ActionExecutor(Protocol):
    def execute(self, call: ActionCall, spec: TaskSpec) -> ActionResult:
        ...
```

`AskMissingFieldsExecutor`、`RunTaskModelExecutor` 和 `RefuseInvestmentAdviceExecutor` 不需要显式继承 `ActionExecutor`。它们只要实现同样形状的方法：

```text
execute(call, spec) -> ActionResult
```

就符合这个 protocol。这是 Python 的 structural typing：不看类继承了谁，只看对象是否具备需要的方法结构。

这个联系主要体现在 router 的 registry 类型上：

```text
dict[ActionName, ActionExecutor]
```

默认 registry 可以把三个具体 executor 实例统一保存为 `ActionExecutor`：

```text
ask_missing_fields -> AskMissingFieldsExecutor()
run_task_model -> RunTaskModelExecutor()
refuse_investment_advice -> RefuseInvestmentAdviceExecutor()
```

因此 `ActionRouter.route(call)` 可以统一返回 `ActionExecutor`，调用方只需要执行：

```text
executor.execute(call, spec)
```

不需要知道具体 executor 类型。

第一版包含三个 executor。

`AskMissingFieldsExecutor` 负责缺字段追问。它复用现有 `build_ask_missing_fields_action`，因此 gateway 看到的 result shape 可以保持和旧链路一致。执行结果收束为：

```text
ActionResult.status = requires_user_input
ActionResult.result = ask_missing_fields action dict
ActionResult.user_message = action.user_message
```

`RunTaskModelExecutor` 负责执行原来的模型任务。它不直接处理 prompt 或模型调用细节，而是继续调用已有稳定入口：

```text
RunTaskModelExecutor
-> TaskExecutor.run(spec, payload)
-> MinimalTaskFlow
```

然后把旧的 `TaskResult` 转换为新的 `ActionResult`：

```text
TaskResult.ok=True
-> ActionResult.status = success

TaskResult.ok=False
-> ActionResult.status = failed
```

这个转换由 `action_result_from_task_result(call, task_result)` 承担。

`RefuseInvestmentAdviceExecutor` 负责明确拒绝投资建议请求。它返回：

```text
ActionResult.status = refused
```

并把以下字段放入 result：

```text
action
task_name
refused_reason
allowed_alternative
user_message
```

其中 `refused_reason` 优先来自 `call.params.refused_reason`，否则使用 `call.decision_reason`；`user_message` 优先来自 `call.params.user_message`，否则使用默认拒绝买卖建议文案。

因此，`executors.py` 的边界是：

```text
输入：已校验的 ActionCall + TaskSpec
输出：统一 ActionResult
不负责 planner 决策
不负责 action 路由
不负责最终 TaskResponse 回填
```

测试：

```text
tests/test_action_router.py
tests/test_action_executors.py
```

### Step 4：新增 decision planner

文件：

```text
src/investory/agent_core/runtime/flow/learning_qa_decision_planner.py
```

第一版规则：

```text
如果缺少必填字段 -> ask_missing_fields
否则 -> run_task_model
```

后续再加风险拒绝规则。

测试：

```text
tests/test_learning_qa_decision_planner.py
```

### Step 5：新增 decision flow

文件：

```text
src/investory/agent_core/runtime/flow/learning_qa_orchestration_flow.py
```

职责：

```text
resolve spec 后接收 spec + payload
调用 planner 生成 TaskDecision
调用 validator 生成 ActionCall
调用 router 找 executor
执行 action
回填 ActionResult
返回 TaskResult
```

当前 LearningQaOrchestrationFlow 落地逻辑：

`learning_qa_orchestration_flow.py` 是新的外层编排器。它把前面几步串成完整的最小闭环：

```text
payload
-> DecisionPlanner
-> TaskDecision
-> validate_decision
-> ActionCall
-> ActionRouter
-> ActionExecutor
-> ActionResult
-> TaskResult
```

`LearningQaOrchestrationFlow` 初始化时可以接收三个可替换依赖：

```text
planner: DecisionPlanner | None
router: ActionRouter | None
task_executor: TaskExecutor | None
```

默认情况下：

```text
planner = DecisionPlanner()
router = ActionRouter(task_executor=task_executor)
```

其中 `task_executor` 会传给默认 router，再由 `RunTaskModelExecutor` 使用。这让 gateway 后续可以继续注入已有 `TaskExecutor`，测试也可以使用 fake executor。

`LearningQaFlowState` 用来记录最近一次执行链路中的中间产物：

```text
task_id
task_name
input_payload
decision
action_call
action_result
output
error
```

当前实现通过 `LearningQaOrchestrationFlow.last_state` 保存最近一次 state，主要用于测试和调试。第一版不做持久化、checkpoint 或多轮恢复。

`LearningQaOrchestrationFlow.run(spec, payload, request_id=None)` 的执行步骤是：

```text
1. 创建 LearningQaFlowState
2. planner.decide(spec, payload) -> TaskDecision
3. validate_decision(decision, spec, request_id) -> ActionCall
4. router.route(action_call) -> ActionExecutor
5. executor.execute(action_call, spec) -> ActionResult
6. backfill_action_result(action_result) -> TaskResult
7. 更新 state.output / state.error 并返回 TaskResult
```

回填规则由 `backfill_action_result(action_result)` 负责：

```text
ActionResult.status == failed
-> TaskResult(ok=False, error=...)

其他状态
-> TaskResult(ok=True, result=...)
```

因此第一版状态映射是：

```text
success -> ok=True
requires_user_input -> ok=True
refused -> ok=True
failed -> ok=False
```

如果 action 返回 `failed` 但没有携带 `TaskError`，`LearningQaOrchestrationFlow` 会生成一个兜底 `TaskError`，避免出现 `ok=False` 但 `error=None` 的不完整结果。

`LearningQaOrchestrationFlow` 的边界是：

```text
负责串联 planner / validator / router / executor / backfill
不负责 HTTP TaskResponse 组装
不直接处理 prompt 或模型调用细节
不负责自然语言 planner 或复杂多轮 replan
```

测试：

```text
tests/test_learning_qa_orchestration_flow.py
```

### Step 6：改造 gateway

文件：

```text
src/investory/gateway/api.py
```

目标：

```text
移除 gateway 内联的 decide_missing_fields_action 分支
改为调用 LearningQaOrchestrationFlow
保持 TaskResponse schema 不变
```

测试：

```text
tests/test_gateway_task_api.py
tests/test_gateway_api.py
tests/test_gateway_schemas.py
```

## 十二、最小验收场景

### 场景 1：缺少字段时追问

请求：

```json
{
  "task_type": "instrument_brief",
  "payload": {
    "instrument_name_or_code": "VOO"
  }
}
```

预期：

```text
DecisionPlanner -> ask_missing_fields
ActionValidator -> 通过
ActionRouter -> AskMissingFieldsExecutor
ActionResult.status -> requires_user_input
TaskResponse.ok -> true
TaskResponse.result.action -> ask_missing_fields
TaskResponse.result.missing_fields -> ["source_material"]
```

### 场景 2：字段完整时执行模型任务

请求：

```json
{
  "task_type": "instrument_brief",
  "payload": {
    "instrument_name_or_code": "VOO",
    "source_material": "VOO tracks a broad US equity index."
  }
}
```

预期：

```text
DecisionPlanner -> run_task_model
ActionValidator -> 通过
ActionRouter -> RunTaskModelExecutor
MinimalTaskFlow -> 正常执行
ActionResult.status -> success
TaskResponse.ok -> true
TaskResponse.result -> InstrumentBriefResult dict
```

### 场景 3：模型结构化输出失败

预期：

```text
RunTaskModelExecutor 捕获 TaskResult.ok=False
ActionResult.status -> failed
ResultBackfill -> TaskResult.ok=False
TaskError.error_type -> structured_output_failed
```

### 场景 4：高风险投资建议请求

第一版可以先用单元测试模拟 `TaskDecision(action="refuse_investment_advice")`。

预期：

```text
ActionRouter -> RefuseInvestmentAdviceExecutor
ActionResult.status -> refused
TaskResponse.ok -> true
result.user_message 明确拒绝买卖建议
result.allowed_alternative 指向学习型分析
```

## 十三、测试策略

建议测试分层：

```text
contract tests:
  只测 Pydantic schema 和字段约束

validator tests:
  只测 action params 是否合规

router tests:
  只测 action name 是否能路由到 executor

executor tests:
  用 FakeTaskExecutor 验证执行和错误收束

decision_flow tests:
  验证完整闭环，不调用真实模型

gateway tests:
  验证 HTTP 层 response shape 不变
```

不建议在第一版测试中调用真实 LLM。

## 十四、完成后的项目链路

完成后，Investory 的核心链路应变为：

```text
HTTP /tasks
-> resolve_session_id
-> resolve_task_spec
-> LearningQaOrchestrationFlow
   -> DecisionPlanner
   -> TaskDecision
   -> ActionValidator
   -> ActionCall
   -> ActionRouter
   -> ActionExecutor
   -> ActionResult
   -> ResultBackfill
-> TaskResponse
```

其中模型调用只是 `run_task_model` 的一个 executor：

```text
RunTaskModelExecutor
-> TaskExecutor
-> MinimalTaskFlow
-> RequestRunner.with_structured_output
```

这能保持两个层次清晰：

```text
LearningQaOrchestrationFlow:
  负责动作决策、校验、路由、回填

MinimalTaskFlow:
  负责单个 task 的 prompt 构建、模型调用、结构化输出校验
```

## 十五、不做事项

本轮不做：

```text
不新增外部金融数据工具
不接入实时行情
不做交易或投资建议
不做用户资产画像
不做复杂多轮 agent planning
不把所有任务都改成 LLM planner 自动选择
不改变现有 TaskResponse 外层结构
```

## 十六、推荐提交粒度

建议分 4 个小提交完成：

```text
1. add action contracts and validator
2. add action router and executors
3. add decision planner and decision flow
4. route gateway task execution through decision flow
```

每个提交都应能通过对应单元测试，避免一次性改动过大。




