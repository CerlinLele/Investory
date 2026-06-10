# Investory 第2-2课：Routing 内容提取与项目落点

## 1. Routing 核心结论

课程里的 routing 本质是：先分类，后处理。

Routing 不应该直接回答用户问题，也不应该执行具体业务。它只负责判断输入应该进入哪条处理路径，然后把请求交给对应 handler、prompt、工具集或任务执行器。

核心流程：

1. `classify_intent(user_input)` 判断用户意图。
2. 输出结构化结果：`route`、`confidence`、`reason`。
3. `dispatch_step` 根据 `confidence` 和 `route` 选择后续路径。
4. `confidence` 低于阈值时进入兜底路径。
5. 每条 route 有独立的 prompt、处理逻辑和工具集。
6. 未知 route 回到 `general` 或澄清路径。

课程示例对应流程：

```text
输入 question
  -> route_step: LLM 判断 weather / exchange / travel_plan / general
  -> 写入 state.intent + state.question
  -> dispatch_step:
       if confidence < 0.6 -> handle_low_confidence
       else route -> 对应 handler
  -> 返回 answer + route_label
```

## 2. Routing 的关键设计原则

### 2.1 Router 只分流，不回答

Router 的职责是输出结构化决策，例如：

```json
{
  "route": "finance_qa",
  "confidence": 0.91,
  "reason": "用户基于材料提出概念解释问题，适合进入问答任务。"
}
```

Router 不应该生成最终业务答案。最终答案应由对应任务 handler 或执行器生成。

### 2.2 每条分支独立 prompt 和工具集

错误做法：

```text
所有任务共用一个大 prompt，里面塞入所有工具说明。
```

问题是模型容易误选工具、误判边界，也难以审计。

更合理的做法：

```text
finance_qa -> 问答 prompt + 材料问答工具
learning_material_summary -> 摘要 prompt + 摘要输出结构
instrument_brief -> 标的简报 prompt + 标的材料结构化工具
realtime_market -> 行情工具 + 风控 gate
```

### 2.3 必须有低置信度兜底

当 route 置信度不足时，不要强行执行任务。

推荐兜底动作：

```text
ask_for_missing_input
ask_for_clarification
refuse_and_redirect
general_learning_clarification
```

### 2.4 Routing 属于结构决策层

课程里的三层分工可以映射为：

```text
结构决策层：route、拆任务、风控、验收
行为执行层：ReAct Loop 内 Reason -> Act -> Observe
单次调用层：一次 LLM 请求的结构化输出
```

Routing 是结构决策层，不是 ReAct loop 本身。

## 3. Investory 当前已有的 Routing 位置

### 3.1 HTTP task routing

文件：

```text
src/investory/gateway/routing.py
```

当前职责：

```text
qa -> finance_qa
summary -> learning_material_summary
brief -> instrument_brief
```

这是显式任务路由，也就是 deterministic routing。用户已经传入 `task_type` 时，系统直接解析到对应 `TaskSpec`。

这个位置适合继续保留规则映射，不建议加入 LLM 判断。原因是用户已经显式指定任务类型，LLM 不应该覆盖用户明确选择。

### 3.2 Learning entry flow routing

文件：

```text
src/investory/agent_core/runtime/flow/learning_entry_flow.py
```

当前流程已经具备 routing 形态：

```text
check_missing_fields
  -> missing? build_missing_input_result
  -> complete? decide_policy

decide_policy
  -> advice? build_refusal_result
  -> learning? resolve_task_spec

resolve_task_spec
  -> execute_task
```

这是 Investory 里最适合承载课程 routing 模式的位置。

它已经有三类路由：

```text
missing input route
advice refusal route
learning execution route
```

后续可以扩展为完整的学习入口 router。

### 3.3 Policy gate routing

文件：

```text
src/investory/agent_core/runtime/flow/investory_policy_gate.py
```

当前已有策略判断：

```text
missing_required_input
investment_advice_request
realtime_data_not_available
user_confirmation_required
ready_to_execute
```

这个模块更接近“路由前置策略门”。它适合负责是否允许继续、是否需要澄清、是否拒绝、是否需要确认。

建议后续让 `learning_entry_flow.py` 复用 `InvestoryPolicyGate`，避免把策略判断分散在多个 flow handler 里。

## 4. Investory 最适合新增 Routing 的位置

### 4.1 `/learning-entry` 是首选入口

文件：

```text
src/investory/gateway/api.py
src/investory/agent_core/runtime/flow/learning_entry_flow.py
```

`/learning-entry` 面向自然语言学习请求，比 `/tasks` 更适合作为智能入口。

典型用户输入：

```text
帮我解释这篇 ETF 材料
总结这段材料
根据这个基金说明写个简报
我该不该买 VOO？
```

这些输入不一定显式携带 `task_type`，所以需要 routing 判断应该进入：

```text
finance_qa
learning_material_summary
instrument_brief
ask_for_missing_input
refuse_and_redirect
```

### 4.2 `infer_candidate_task_type()` 是规则路由基础

文件：

```text
src/investory/agent_core/runtime/flow/learning_entry_rules.py
```

当前规则：

```text
material_text + question -> qa
material_text -> summary
instrument_name_or_code + source_material -> brief
```

这是很好的第一层 routing。建议继续保留，因为它稳定、便宜、可测试。

LLM routing 应该只在规则无法判断或自然语言入口字段不足时启用，而不是替代所有规则。

### 4.3 ReAct tool routing 适合未来扩展

文件目录：

```text
src/investory/agent_core/runtime/react_core
```

未来如果 ReAct loop 有多个工具，不建议所有任务共用全量工具。

更合适的是 route 决定工具白名单：

```text
finance_qa -> material QA tools
learning_material_summary -> summary tools
instrument_brief -> extraction + brief generation tools
realtime_market -> market data tools, only if policy allows
execution/order -> default refuse or require confirmation
```

这能减少误调用，也方便审计。

## 5. 不适合加入 Routing 的位置

### 5.1 `TaskExecutionPipeline`

文件：

```text
src/investory/agent_core/runtime/task_execution_pipeline.py
```

当前职责是线性执行：

```text
validate input -> build prompt -> call model -> validate output -> build result
```

它是 route 之后的执行器，不应该再判断业务意图。

如果在这里加入 routing，会导致执行层和决策层混杂，后续很难测试和维护。

### 5.2 显式 `/tasks` 请求

文件：

```text
src/investory/gateway/api.py
```

`/tasks` 的输入已经包含 `task_type`。

推荐行为：

```text
用户传 qa -> 执行 finance_qa
用户传 summary -> 执行 learning_material_summary
用户传 brief -> 执行 instrument_brief
未知 task_type -> 返回 400
```

除非后续新增 `task_type="auto"`，否则这里不需要 LLM routing。

## 6. 推荐的 Investory Routing 设计

### 6.1 Route 枚举

建议新增闭集枚举，避免散落 raw string。

```python
from enum import Enum


class LearningEntryRoute(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    FINANCE_QA = "finance_qa"
    LEARNING_MATERIAL_SUMMARY = "learning_material_summary"
    INSTRUMENT_BRIEF = "instrument_brief"
    GENERAL_LEARNING_CLARIFICATION = "general_learning_clarification"
```

### 6.2 Route decision model

```python
from pydantic import BaseModel, Field


class LearningEntryRouteDecision(BaseModel):
    route: LearningEntryRoute
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    missing_fields: list[str] = Field(default_factory=list)
```

### 6.3 分层策略

推荐顺序：

```text
1. 规则校验：缺字段、投资建议、实时数据、确认要求
2. 规则路由：payload shape 能明确判断时直接选 task
3. LLM routing：规则无法判断时才调用
4. 低置信度兜底：返回澄清，不执行任务
5. 执行：resolve_task_spec -> TaskExecutor.run()
```

这比“所有输入先问 LLM”更稳，也更便宜。

### 6.4 当前实现修改逻辑

当前代码修改遵循一个原则：`/learning-entry` 是结构决策层，`TaskExecutionPipeline` 仍然只是被选中任务的执行层。

也就是说，routing 相关判断集中在：

```text
src/investory/agent_core/runtime/flow/learning_entry_flow.py
src/investory/agent_core/runtime/flow/investory_policy_gate.py
src/investory/agent_core/runtime/flow/learning_entry_rules.py
src/investory/agent_core/runtime/flow/learning_entry_router.py
```

执行任务仍然交给：

```text
resolve_task_spec -> TaskExecutor.run() -> TaskExecutionPipeline
```

#### Step 1：先统一 policy gate

修改前，`learning_entry_flow.py` 自己做了两类判断：

```text
detect_missing_fields()
looks_like_investment_advice()
```

但项目里已经有 `InvestoryPolicyGate.evaluate()`，而且它能覆盖更多前置策略：

```text
missing_required_input
investment_advice_request
realtime_data_not_available
user_confirmation_required
ready_to_execute
```

所以 Step 1 的逻辑是：让 flow 的第一个节点变成 policy gate 评估，而不是在 flow 里分散写策略判断。

现在链路变成：

```text
/learning-entry
  -> evaluate_policy_gate
       ask_for_missing_input -> build_missing_input_result
       refuse_and_redirect -> build_refusal_result
       execute_learning_task -> resolve_task_spec
  -> execute_task
```

这样做的原因：

```text
1. 缺字段、拒绝、实时数据、确认要求属于前置策略，不属于任务执行。
2. flow 只根据 gate 的结构化 action 分流，不重复实现策略细节。
3. 后续新增 policy 分支时，优先扩展 gate，而不是继续加 flow handler。
```

#### Step 2：保留规则路由

Step 2 没有把所有请求都交给 LLM，而是继续保留 `infer_candidate_task_type()`。

规则路由仍然负责最稳定的 payload shape 判断：

```text
material_text + question -> qa
material_text -> summary
instrument_name_or_code + source_material -> brief
```

当前实现中，`InvestoryPolicyGate.evaluate()` 在 policy 放行后调用 `infer_candidate_task_type()`。如果规则能判断出候选任务，就直接返回：

```text
action = execute_learning_task
metadata["candidate_task_type"] = qa | summary | brief
```

这里新增了 `CANDIDATE_TASK_TYPE_METADATA_KEY`，原因是 `candidate_task_type` 是 gate 和 flow 之间的稳定字段，不应该以 raw string 分散在多个文件里。

这样做的原因：

```text
1. 明确字段组合比 LLM 判断更稳定、更便宜、更容易测试。
2. 用户已经提供足够结构化 payload 时，不需要额外模型调用。
3. LLM router 只作为规则无法判断时的补充，而不是替代规则。
```

#### Step 3：增加可选 LLM router

Step 3 新增的是可选 router，而不是默认强制调用 LLM。

新增模块：

```text
src/investory/agent_core/runtime/flow/learning_entry_router.py
src/investory/agent_core/prompts/flows/learning_entry_router.md
```

router 的结构化输出是：

```text
route
confidence
reason
missing_fields
```

当前 `InvestoryPolicyGate` 只有在以下条件全部满足时才会调用 `llm_router`：

```text
1. 缺字段规则没有直接拦截。
2. 投资建议、实时数据、确认要求等 policy gate 没有直接拦截。
3. infer_candidate_task_type() 无法判断 qa / summary / brief。
4. 调用方显式注入了 llm_router。
```

如果没有注入 `llm_router`，默认行为仍然保持保守：

```text
candidate_task_type is None
  -> ask_for_missing_input
```

LLM router 的 route 会被映射回现有 flow action：

```text
finance_qa -> execute_learning_task + candidate_task_type=qa
learning_material_summary -> execute_learning_task + candidate_task_type=summary
instrument_brief -> execute_learning_task + candidate_task_type=brief
ask_for_missing_input -> ask_for_missing_input
refuse_and_redirect -> refuse_and_redirect
general_learning_clarification -> ask_for_missing_input / clarification fallback
```

这样做的原因：

```text
1. 先保护确定性路径，避免 LLM 覆盖稳定规则。
2. LLM router 只处理自然语言入口里规则看不懂的请求。
3. router 只输出结构化决策，不生成最终答案。
4. 是否启用 LLM router 由调用方显式注入，方便测试、成本控制和灰度。
```

#### Step 4：增加低置信度兜底

Step 4 解决的问题是：即使已经接入 LLM router，也不能因为模型勉强给了一个 route，就直接执行任务。

如果 router 输出像这样：

```json
{
  "route": "finance_qa",
  "confidence": 0.42,
  "reason": "看起来像问答，但任务类型不够明确。"
}
```

这类结果不应该继续走：

```text
resolve_task_spec -> execute_task
```

否则系统会把一个其实不够明确的请求，当成明确任务执行掉。

当前实现把这个判断放在 `InvestoryPolicyGate`，而不是放在 flow 或 executor 里。也就是说，LLM route 进入执行前，还会再过一层：

```text
if confidence < 0.6:
    fallback -> clarification
```

当前 gate 的低置信度规则有两类：

```text
1. route_decision.confidence < 0.6
2. route == general_learning_clarification
```

命中后不会执行任务，而是返回：

```text
action = ask_for_missing_input
reason = low_confidence_route
```

这里保留 `ask_for_missing_input` 这个既有 action，而不是再扩一个新的 HTTP/result action，原因是：

```text
1. 不需要改现有接口返回契约。
2. flow 仍然走已有 missing-input 分支，改动面更小。
3. 差异放在 message 和 policy reason 上表达就够了。
```

因此，Step 4 之后实际链路变成：

```text
规则可判断
  -> 直接执行

规则不可判断 + 未启用 llm_router
  -> ask_for_missing_input

规则不可判断 + 启用 llm_router
  -> LLM route
       if confidence < 0.6 -> clarification fallback
       elif route == general_learning_clarification -> clarification fallback
       else -> 进入对应任务执行
```

在 `learning_entry_flow.py` 里，低置信度 fallback 和“真的缺字段”都复用了 `build_missing_input_result()`，但 message 不同：

```text
缺字段:
  Please provide enough material or instrument context to continue.

低置信度:
  Please clarify whether you want an explanation, a summary, or an instrument brief...
```

这样做的原因：

```text
1. 低置信度本质上是“信息不足以安全决策”，不是“已经知道该执行哪个任务”。
2. 兜底应该发生在结构决策层，而不是任务执行层。
3. gate 统一处理后，flow 只负责分支结果组装，不需要知道 confidence 细节。
4. prompt 也同步约束：教育型但模糊的请求应优先返回 general_learning_clarification，并把 confidence 压低到 0.6 以下。
```

#### 没有修改的位置

这几处保持不变是有意设计：

```text
src/investory/gateway/routing.py
```

显式 `/tasks` 请求已经带 `task_type`，继续用 deterministic routing，不引入 LLM。

```text
src/investory/agent_core/runtime/task_execution_pipeline.py
```

它仍然只做：

```text
validate input -> build prompt -> call model -> validate output -> build result
```

不在执行层里判断业务意图，避免 routing 层和 execution 层混在一起。

## 7. 推荐落地步骤

### Step 1：统一 policy gate

让 `learning_entry_flow.py` 复用：

```text
InvestoryPolicyGate.evaluate()
```

把缺字段、投资建议、实时数据、确认要求收束到一个 gate。

### Step 2：保留当前规则路由

继续使用：

```text
infer_candidate_task_type()
```

明确字段组合能判断任务时，不需要 LLM。

### Step 3：增加可选 LLM router

只在规则无法判断时调用。

输出字段：

```text
route
confidence
reason
missing_fields
```

### Step 4：增加低置信度兜底

例如：

```text
confidence < 0.6 -> GENERAL_LEARNING_CLARIFICATION
```

返回用户可理解的澄清问题，而不是执行错误任务。

### Step 5：为每条 route 单独测试

需要覆盖：

```text
qa route
summary route
brief route
missing input route
refusal route
low confidence route
unknown route fallback
```

## 8. 一句话结论

Investory 最适合把 routing 放在 `/learning-entry` 的结构决策层：先用规则和 policy gate 做安全、稳定的分流，再在规则无法判断时引入 LLM router；`TaskExecutionPipeline` 只做被选中任务的执行，不承担意图判断。
