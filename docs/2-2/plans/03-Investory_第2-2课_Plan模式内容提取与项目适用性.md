# Investory 第2-2课：Plan 模式内容提取与项目适用性

## 1. Plan 模式核心结论

课程里的 `Plan` 模式解决的是：在真正执行前，先让模型只生成计划、影响说明和风险评估，再由系统策略决定是否自动执行、记录警告或等待人工确认。

它不是普通的“先想一想”，而是一个执行前风控层。

核心流程：

```text
用户任务
  -> generate_plan(task)
       只生成计划，不执行操作
       输出 steps / risk_level / risk_reason / reversible
  -> classify_and_route
       根据 risk_level + reversible 决定 auto_approved
  -> auto_execute 或 wait_confirm
  -> 输出 result
```

课程示例 `s03_plan_mode.py` 的关键点：

| 阶段 | 职责 | 关键输入 | 关键输出 |
|---|---|---|---|
| `generate_plan` | 只生成执行计划和风险评估 | `task` | `steps`, `risk_level`, `risk_reason`, `reversible` |
| `classify_and_route` | 根据风险策略决定是否自动放行 | `plan` | `auto_approved` |
| `auto_execute` | 自动执行低风险计划 | `steps` | `result` |
| `wait_confirm` | 对高风险或不可回滚计划等待确认 | `task`, `steps` | 执行或取消结果 |

最低记忆单元：

```text
Phase 1: 只生成计划 + 风险评估
Phase 2: 按策略自动执行或等待确认
```

## 2. Plan 输出结构应包含什么

课程示例要求模型输出：

```json
{
  "steps": [
    {
      "step": 1,
      "action": "具体操作",
      "impact": "这一步会改变什么"
    }
  ],
  "risk_level": "low | medium | high",
  "risk_reason": "风险评估依据",
  "reversible": true
}
```

关键字段含义：

| 字段 | 含义 | Investory 落地意义 |
|---|---|---|
| `steps` | 执行步骤列表 | 用户和系统都能审阅将要发生什么 |
| `action` | 每一步具体操作 | 避免“执行任务”这种不可审计描述 |
| `impact` | 每一步会改变什么 | 用于判断是否影响状态、成本、外部系统或合规边界 |
| `risk_level` | 整体风险等级 | 决定自动放行、记录警告还是人工确认 |
| `risk_reason` | 风险依据 | 便于日志、调试、用户解释和后续审计 |
| `reversible` | 是否可回滚 | 中风险任务能否自动执行的重要条件 |

Plan 的重点不是生成更长的步骤，而是把执行前决策变成结构化、可测试、可审计的策略输入。

## 3. 策略路由规则

课程示例中的策略非常清晰：

```text
low:
  自动放行

medium + reversible:
  自动放行，但需要记录

medium + irreversible:
  等待人工确认

high:
  等待人工确认
```

这体现了一个重要边界：风险策略不应该写死在业务 handler 里，而应该集中在结构决策层。

错误做法：

```text
summary handler 自己判断是否需要确认
brief handler 自己判断是否高风险
tool handler 自己判断是否允许执行
```

更合理的做法：

```text
PlanPolicyGate
  -> 根据 risk_level / reversible / action_type / tool_requires_confirmation 统一决策
  -> 返回 auto_approved / requires_user_confirmation / refused
```

## 4. 和 Routing、To-Do、Reflection 的关系

第 07 课的结构化决策顺序可以映射为：

```text
Routing:
  输入进来时，判断交给哪条路径。

To-Do + 并发:
  复杂任务进入某条路径后，拆成可验证子任务并决定并发关系。

Plan:
  执行前判断风险、可回滚性和是否需要用户确认。

Reflection:
  执行后检查结果质量和安全边界。
```

因此 Plan 不应该替代 Routing，也不应该替代 Reflection。

在 Investory 中更合理的位置是：

```text
/learning-entry
  -> InvestoryPolicyGate
  -> Routing / TaskSpec
  -> Optional PlanPolicyGate
  -> TaskExecutor 或 Tool Execution
  -> Optional Reflection
```

其中：

- Routing 解决“要执行哪个任务”。
- To-Do 解决“复杂任务怎么拆”。
- Plan 解决“这些动作能不能执行、是否需要确认”。
- Reflection 解决“执行结果是否达标”。

## 5. Investory 当前项目状态

Investory 目前已经有 Plan 模式可以落地的基础，但还没有独立的 Plan 层。

现有相关能力：

| 位置 | 当前能力 | 与 Plan 的关系 |
|---|---|---|
| `InvestoryPolicyGate` | 缺字段、投资建议、实时数据、用户确认、低置信度路由 | 已经承担部分执行前策略判断 |
| `learning_entry_rules.py` | `requires_confirmation`, `confirmation_granted` 字段检测 | 可作为 Plan 人工确认机制的现有输入 |
| `LearningEntryFlow` | policy gate 后进入任务解析和执行 | 可在执行前插入 Plan 分支 |
| `ToolRegistry` | `requires_confirmation` 和确认参数校验 | 工具层已经有局部 Plan 风控雏形 |
| `TodoExecutionPlan` / runner | 子任务、依赖、失败策略、并发上限 | 未来复合任务可先生成 todo，再对整体计划做 Plan 风控 |

当前链路大致是：

```text
/learning-entry
  -> InvestoryPolicyGate
  -> resolve_task_spec
  -> TaskExecutor
  -> TaskExecutionPipeline
```

这意味着：

```text
当前不建议为了 Plan 模式立即改造所有单任务请求。
更适合先把 Plan 做成“高风险动作或工具执行前的可选风控层”。
```

## 6. Investory 里最适合 Plan 的场景

### 6.1 用户明确要求执行动作

适用性：高。

示例：

```text
立即执行这个操作
确认执行这个批量任务
run now
perform action
```

当前 `learning_entry_rules.py` 已经有：

```text
REQUIRES_CONFIRMATION_FIELD = "requires_confirmation"
CONFIRMATION_GRANTED_FIELD = "confirmation_granted"
CONFIRMATION_TERMS = (...)
```

这说明项目已经把“确认”作为前置策略的一部分。Plan 可以在这里补充更细的说明：

```text
不只是问用户“确认吗”，而是先展示：
1. 将执行哪些步骤
2. 每一步影响是什么
3. 为什么需要确认
4. 是否可回滚
```

推荐策略：

```text
requires_confirmation=true
  -> generate_plan
  -> 返回 plan + confirmation_required
  -> 用户确认后再执行
```

### 6.2 未来接入有副作用的工具

适用性：高。

当前 `ToolRegistry` 已经支持：

```text
ToolSpec.requires_confirmation
confirmation_granted
ToolValidationErrorCode.CONFIRMATION_REQUIRED
```

这很适合与 Plan 结合。

推荐流程：

```text
模型提出 tool call
  -> ToolRegistry 校验工具是否允许
  -> 如果 requires_confirmation:
       generate_tool_plan(tool_name, args)
       输出 steps / impact / risk_level / reversible
       等待用户确认
  -> 确认后才真正调用工具
```

适合 Plan 的工具类型：

```text
写入数据库
更新用户偏好
发送外部请求
产生费用的 API 调用
触发批量任务
导出或删除用户数据
```

当前不适合执行的工具类型：

```text
下单交易
投资组合自动调仓
绕过实时数据能力限制的行情推断
任何会形成个性化投资建议的动作
```

这些应由 Policy Gate 拒绝或转成学习型问题，而不是靠 Plan 放行。

### 6.3 多材料或多标的 batch 任务

适用性：中到高，适合未来接入 To-Do runner 后使用。

示例：

```text
帮我并发整理 8 份基金材料，并生成最终学习报告。
```

推荐顺序：

```text
Routing
  -> To-Do plan builder 生成 TodoExecutionPlan
  -> PlanPolicyGate 评估整体风险和可回滚性
  -> TodoExecutionRunner 执行
  -> Reflection 验收最终报告
```

Plan 在这里不负责拆任务，拆任务属于 To-Do。Plan 只负责判断：

```text
是否会产生大量模型调用成本
是否会触发外部 API
是否会写入持久化状态
失败后是否可重试或回滚
是否需要用户确认
```

### 6.4 离线评估、批量回归、prompt 实验

适用性：高，工程侧优先。

示例：

```text
批量跑 100 个 fixture，比较两个 prompt 版本。
```

这类任务不是用户在线路径，但可能消耗大量成本或时间。Plan 可以先输出：

```text
样本数量
预计调用次数
是否会写入报告
是否会覆盖已有文件
失败策略
```

推荐策略：

```text
low:
  小样本 dry-run 自动执行

medium + reversible:
  写入新报告文件，自动执行并记录

high:
  覆盖历史结果、大批量调用、外部服务压力较高时等待确认
```

### 6.5 实时数据或外部数据请求

适用性：中，但必须放在 Policy Gate 之后。

当前 `InvestoryPolicyGate` 已经会处理：

```text
requires_realtime_data(payload)
supports_realtime_data=False -> refuse_and_redirect
```

如果未来系统支持实时数据工具，Plan 可以用于执行前确认：

```text
将调用哪个数据源
是否产生费用
数据时间戳是什么
是否会缓存结果
是否只用于教育说明
```

但如果当前不支持实时数据，Plan 不应该生成“看起来可执行”的计划。正确做法仍然是前置拒绝或澄清。

## 7. 不适合 Plan 的场景

| 场景 | 原因 | 推荐处理 |
|---|---|---|
| 普通 `finance_qa` 概念解释 | 无副作用，成本低，执行前审批价值不高 | 直接执行，必要时用 Reflection |
| 普通 `learning_material_summary` | 低风险生成任务 | 直接执行，输出后验收 |
| 普通 `instrument_brief` | 通常是学习型生成，不改变外部状态 | Policy Gate + Reflection |
| 缺少必填字段 | 没有足够信息生成可靠计划 | `ASK_FOR_MISSING_INPUT` |
| 投资建议请求 | 应前置拒绝，不应先计划再执行 | `REFUSE_AND_REDIRECT` |
| 不支持的实时数据请求 | 能力缺失，不能靠计划补齐 | `REALTIME_DATA_NOT_AVAILABLE` |
| 纯规则可判断的安全问题 | LLM 评估不如代码稳定 | deterministic validator |

原则：

```text
Plan 用于“可执行但需要风控”的任务。
不可执行、越界或信息不足的任务，应在 Plan 前被拦截。
```

## 8. 推荐的 Investory Plan 合约

如果后续落地，建议新增独立合约，不把字段散落在 flow handler 里。

### 8.1 风险等级

```python
from enum import Enum


class PlanRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

### 8.2 计划步骤

```python
from pydantic import BaseModel


class ExecutionPlanStep(BaseModel):
    step: int
    action: str
    impact: str
```

### 8.3 执行计划

```python
class ExecutionPlan(BaseModel):
    steps: list[ExecutionPlanStep]
    risk_level: PlanRiskLevel
    risk_reason: str
    reversible: bool
```

### 8.4 Plan 策略结果

```python
class PlanPolicyDecision(str, Enum):
    AUTO_APPROVE = "auto_approve"
    AUTO_APPROVE_WITH_AUDIT = "auto_approve_with_audit"
    REQUIRE_USER_CONFIRMATION = "require_user_confirmation"
    REFUSE = "refuse"


class PlanPolicyResult(BaseModel):
    decision: PlanPolicyDecision
    reason: str
    plan: ExecutionPlan
```

这符合仓库规则：

```text
固定业务状态用 str, Enum。
稳定字段名、prompt 文件名、metadata key 用模块级常量。
不要在多个模块里散落 "high"、"reversible"、"confirmation_required" 等 raw string。
```

## 9. 推荐的策略实现

第一版可以不调用 LLM，先实现确定性策略函数。

```text
evaluate_plan_policy(plan):
  if plan.risk_level == LOW:
    return AUTO_APPROVE

  if plan.risk_level == MEDIUM and plan.reversible:
    return AUTO_APPROVE_WITH_AUDIT

  if plan.risk_level == MEDIUM and not plan.reversible:
    return REQUIRE_USER_CONFIRMATION

  if plan.risk_level == HIGH:
    return REQUIRE_USER_CONFIRMATION
```

后续可扩展额外规则：

```text
tool_requires_confirmation=True -> REQUIRE_USER_CONFIRMATION
external_cost_estimate > threshold -> REQUIRE_USER_CONFIRMATION
will_write_persistent_state=True -> REQUIRE_USER_CONFIRMATION
investment_advice_risk=True -> REFUSE
unsupported_realtime_data=True -> REFUSE
```

这里需要注意：

```text
PlanPolicyGate 只能放行“允许执行但需风控”的任务。
投资建议、能力缺失、缺字段仍然由 InvestoryPolicyGate 前置处理。
```

## 10. 推荐落地架构

建议把 Plan 作为独立 runtime 组件，而不是嵌入 `TaskExecutionPipeline`。

推荐新增模块：

```text
src/investory/agent_core/contracts/execution_plan.py
src/investory/agent_core/runtime/plan_core/plan_generator.py
src/investory/agent_core/runtime/plan_core/plan_policy_gate.py
src/investory/agent_core/prompts/flows/execution_plan.md
```

推荐链路：

```text
/learning-entry
  -> InvestoryPolicyGate
  -> resolve_task_spec
  -> should_require_plan?
       no  -> TaskExecutor.run()
       yes -> ExecutionPlanGenerator.generate()
              -> PlanPolicyGate.evaluate()
              -> auto execute / return confirmation request
```

`TaskExecutionPipeline` 不建议承担 Plan 职责。它现在的边界很清楚：

```text
validate input
  -> build prompt
  -> call model
  -> validate output
  -> build result
```

Plan 属于执行前结构决策层，不属于单个任务的执行细节。

## 11. 可行性分析

### 技术可行性

可行性：高。

原因：

- 项目已经大量使用 Pydantic 结构化模型，Plan 输出可以沿用同一模式。
- `InvestoryPolicyGate` 已经是执行前策略门，Plan 可以作为其后续补充。
- `ToolRegistry` 已经有 `requires_confirmation`，可以与 Plan 的人工确认策略对齐。
- `LearningEntryFlow` 是 LangGraph 编排，增加一个条件分支在架构上可行。

主要工程工作：

```text
1. 新增 ExecutionPlan / PlanPolicyResult 合约。
2. 新增 plan prompt，要求只生成计划、不执行。
3. 新增 PlanPolicyGate，集中处理 risk_level + reversible。
4. 在需要确认的路径返回 plan，而不是直接执行。
5. 增加 tests 覆盖 low / medium reversible / medium irreversible / high。
```

### 产品可行性

可行性：中到高。

收益：

- 高风险动作前用户能看到清晰步骤和影响。
- 系统能解释为什么需要确认。
- 后续支持工具调用、batch 任务和外部数据源时更安全。
- 审计日志可以记录 `risk_reason` 和 `reversible`。

代价：

- 多一次 LLM 调用，增加延迟和成本。
- 如果所有任务都强制 Plan，会让普通学习请求变慢。
- 风险等级由模型判断时可能不稳定，必须叠加确定性规则。

因此建议只对需要风控的任务启用，不对所有普通学习任务启用。

### 合规可行性

可行性：中。

Plan 能增强执行前透明度，但不能替代合规策略。

原因：

- LLM 判断风险等级不是确定性合规判定。
- 投资建议请求必须由 `InvestoryPolicyGate` 前置拒绝。
- 不支持实时数据时，不能让 Plan 生成伪执行路径。
- 对有副作用的工具，最终仍需要工具白名单、参数校验、确认字段和审计日志。

## 12. 推荐落地优先级

### Phase 1：文档和合约先行

目标：明确 Plan 在项目中的边界。

做法：

```text
新增 ExecutionPlan / PlanRiskLevel / PlanPolicyDecision 合约。
新增纯函数 PlanPolicyGate。
不接入在线链路。
```

验收：

```text
low -> auto_approve
medium + reversible -> auto_approve_with_audit
medium + irreversible -> require_user_confirmation
high -> require_user_confirmation
```

### Phase 2：接入工具确认路径

目标：让有副作用或需确认工具先展示计划。

做法：

```text
ToolSpec.requires_confirmation=True
  -> 生成 tool execution plan
  -> 返回 confirmation_required + plan
  -> 用户确认后再执行
```

这比先接入普通 QA 或 summary 更有价值，因为工具调用天然有执行风险。

### Phase 3：接入 batch / To-Do runner

目标：控制批量任务成本和失败影响。

做法：

```text
TodoExecutionPlan 生成后
  -> PlanPolicyGate 评估整体风险
  -> 自动执行或等待确认
```

重点检查：

```text
预计调用次数
并发上限
失败策略
是否写入文件或状态
是否可回滚
```

### Phase 4：选择性接入 `/learning-entry`

目标：只对明确需要确认的请求启用 Plan。

建议触发条件：

```text
requires_confirmation=true
contains confirmation terms
future tool call requires confirmation
future batch request estimated cost is above threshold
future external data call has cost or side effect
```

不建议触发条件：

```text
普通材料总结
普通概念解释
普通 instrument brief
低置信度 routing fallback
投资建议拒答
```

## 13. 实施风险与控制手段

| 风险 | 表现 | 控制手段 |
|---|---|---|
| 模型低估风险 | 高风险任务被标成 low | 叠加代码规则：工具副作用、外部成本、持久化写入强制确认 |
| Plan 变成冗余延迟 | 普通学习请求都多一次 LLM 调用 | 只对确认、工具、batch、外部数据路径启用 |
| 用户误以为确认等于投资建议可执行 | Plan 展示了被禁止的投资动作 | Policy Gate 必须先拒绝投资建议类请求 |
| 可回滚性判断不可靠 | 模型声称可回滚但实际不可回滚 | 对写入、删除、外部 API 调用使用 deterministic reversible 标记 |
| 策略分散 | handler、tool、flow 各自判断 | 统一由 PlanPolicyGate 和 ToolRegistry 承担 |
| 审计不足 | 事后不知道为什么自动执行 | 记录 plan、risk_reason、decision、confirmation_granted |

## 14. 对当前项目的结论

Plan 模式适合 Investory，但不应该现在铺到所有任务上。

推荐结论：

- 当前 `InvestoryPolicyGate` 已经承担了缺字段、投资建议、实时数据、用户确认和低置信度路由兜底，Plan 应该作为它之后的“可执行动作风控层”。
- 普通 `finance_qa`、`learning_material_summary`、`instrument_brief` 不需要默认 Plan，优先用 Policy Gate 前置拦截和 Reflection 后置验收。
- 最适合先落地 Plan 的位置是未来的工具调用确认路径、batch / To-Do runner、外部数据源调用和离线批量评估。
- `TaskExecutionPipeline` 不应该被改造成 Plan 执行器，它应继续保持“给定 TaskSpec + payload 后执行任务”的职责。
- 工程实现应使用 `str, Enum`、Pydantic 合约和模块级常量，避免风险等级、决策结果、确认字段等 raw string 分散在代码中。

最小可行版本：

```text
ExecutionPlan
  -> steps, risk_level, risk_reason, reversible

PlanPolicyGate
  -> low: auto_approve
  -> medium + reversible: auto_approve_with_audit
  -> medium + irreversible: require_user_confirmation
  -> high: require_user_confirmation
```

这条路径和当前 Investory 架构最兼容：前置由 `InvestoryPolicyGate` 排除不可执行和越界请求，Plan 只处理“可以执行但需要风控”的动作，最后由 `TaskExecutor`、工具层或 To-Do runner 执行。

## 15. 具体 Implementation Steps

下面给一套可以直接落地到当前仓库的实现步骤，默认目标是“新增 Plan 能力，不破坏现有 learning-entry 主链路”。

### Step 1：新增 Plan 合约（先做强类型，不接流量）

新增文件：

```text
src/investory/agent_core/contracts/execution_plan.py
```

建议先定义：

```text
PlanRiskLevel (str, Enum)
PlanPolicyDecision (str, Enum)
ExecutionPlanStep (Pydantic)
ExecutionPlan (Pydantic)
PlanPolicyResult (Pydantic)
```

实现要求：

```text
所有业务状态值用 Enum，不散落 raw string
默认字段使用模块级常量
风险等级仅 low/medium/high
```

### Step 2：新增 PlanPolicyGate（先 deterministic）

新增文件：

```text
src/investory/agent_core/runtime/flow/plan_policy_gate.py
```

实现一个纯函数或轻量类：

```text
evaluate(plan: ExecutionPlan) -> PlanPolicyResult
```

第一版策略固定为：

```text
low -> auto_approve
medium + reversible -> auto_approve_with_audit
medium + irreversible -> require_user_confirmation
high -> require_user_confirmation
```

注意点：

```text
PlanPolicyGate 只处理“可执行但需风控”的动作
缺字段 / 投资建议 / 不支持实时数据仍由 InvestoryPolicyGate 前置处理
```

### Step 3：新增 Plan prompt 和生成器（独立组件）

新增文件：

```text
src/investory/agent_core/prompts/flows/execution_plan.md
src/investory/agent_core/runtime/flow/plan_generator.py
```

`plan_generator.py` 职责：

```text
输入 task context
调用 RequestRunner
按 ExecutionPlan 结构化解析输出
```

Prompt 约束必须包含：

```text
只生成计划，不执行动作
每一步给出 action + impact
给出 risk_level + risk_reason + reversible
```

### Step 4：在 learning_entry_flow 中接可选分支（默认关闭）

编辑文件：

```text
src/investory/agent_core/runtime/flow/learning_entry_flow.py
```

改造方式：

```text
在 resolve_task_spec -> execute_task 之间加可选 Plan 分支
仅当 payload 明确 requires_confirmation 或触发高风险信号时进入 Plan
默认普通 QA/summary/brief 不进入 Plan
```

建议新增节点：

```text
GENERATE_PLAN
EVALUATE_PLAN_POLICY
BUILD_CONFIRMATION_REQUIRED_RESULT
```

并保持向后兼容：

```text
不触发 Plan 时，行为与当前版本一致
```

### Step 5：接入工具确认路径（优先于全量接入）

编辑文件：

```text
src/investory/agent_core/runtime/react_core/tool_registry.py
```

实现策略：

```text
ToolSpec.requires_confirmation=True 时
先生成 tool plan
返回 confirmation_required + plan
确认后再执行工具
```

原因：

```text
工具调用天然有副作用或成本，Plan 在这里收益最高
```

### Step 6：补齐测试（按层）

新增或编辑测试：

```text
tests/test_plan_policy_gate.py
tests/test_learning_entry_flow.py
tests/test_learning_entry_gateway_api.py
```

至少覆盖：

```text
low / medium reversible / medium irreversible / high
Plan 触发与不触发路径
confirmation_required 响应结构
普通学习请求不被 Plan 拖慢路径
```

再做编译与回归：

```text
.venv\Scripts\python.exe -m pytest ...
python -m py_compile ...
```

### Step 7：观测与灰度开关

建议加配置项（例如在 `src/investory/config.py`）：

```text
ENABLE_PLAN_GATE=false
PLAN_CONFIDENCE_THRESHOLD
PLAN_MAX_STEPS
```

上线顺序：

```text
先灰度到 requires_confirmation 场景
再扩展到 batch / tool / high-cost requests
最后评估是否需要更广覆盖
```

## 16. 最小交付检查清单

MVP 完成标准：

```text
有 execution_plan 合约
有 deterministic plan policy gate
有 plan 生成器和 prompt
learning_entry_flow 能按条件触发 Plan
confirmation_required 响应可用
测试覆盖核心分支并通过
```

只要这 6 项完成，就可以在不重构主链路的前提下，把 Plan 以“可选风控层”落地。
