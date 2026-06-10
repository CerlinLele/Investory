# Investory 投资文档审查助手 v1 任务清单可行性与实施计划

## 1. 结论

`v1_加任务清单` 对 Investory 是可行的，但不应该照搬 Agently / TriggerFlow 代码。更合适的做法是复用它的业务结构：

```text
文档输入
  -> 投资边界与缺失字段检查
  -> 文档类型路由
  -> 构建审查框架
  -> 生成结构化 To-Do Plan
  -> 按依赖分层并发执行 extract / analyze 子任务
  -> 汇总为现有 gateway 响应结构
```

当前 Investory 已经具备 v1 的大部分基础设施：

- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py` 已有投资文档审查 LangGraph 主流程。
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_router.py` 已有 LLM 文档类型路由。
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_rules.py` 已有文档类型审查框架。
- `src/investory/agent_core/contracts/todo_execution.py` 已有 To-Do plan / task / result 合约。
- `src/investory/agent_core/runtime/todo_core/runner.py` 已有依赖分层、并发、重试、失败策略执行器。
- `src/investory/agent_core/runtime/todo_core/plan_validator.py` 和 `dependency_layers.py` 已有依赖校验与拓扑分层。

所以 v1 在本项目中的重点不是“新增一个执行框架”，而是“把现有投资文档审查 single-pass 节点替换为 plan generation + todo execution + synthesis”。

## 2. 参考示例的核心能力

参考目录：

```text
C:\Users\hy120\Downloads\zhihullm\agent\lecture\08. 实战——智能文档审查助手\scripts\v1_加任务清单
```

示例 v1 相比 v0 的变化：

- 删除 `single_pass_review`。
- 新增 `plan_gen_subflow`，根据文档类型和审查框架生成任务清单。
- 任务分为 `extract` 和 `analyze` 两类。
- `extract` 只提取事实，不做判断。
- `analyze` 基于上游 extract 结果判断风险、缺口或不一致。
- 任务带 `depends_on`，系统按依赖图执行，而不是顺序硬编码。
- 多个无依赖任务可并发执行。
- 多依赖任务需要等待所有依赖完成后再执行。

示例中的动态执行思想可以迁移，但 API 形式不能直接迁移：

| 示例机制 | Investory 对应落点 | 迁移方式 |
|---|---|---|
| `TriggerFlow` 主流程 | `LangGraph StateGraph` | 保留 Investory 现有 flow 风格 |
| `Agently.create_agent().output(...)` | `RequestRunner.run(messages, PydanticModel)` | 继续使用项目统一模型调用层 |
| `Literal["extract", "analyze"]` | `str, Enum` | 按仓库规则使用枚举和常量 |
| `validate_plan(plan)` | `validate_todo_plan()` / `ensure_valid_todo_plan()` | 复用现有 todo validator |
| `emit + when` 依赖触发 | `TodoExecutionRunner` 分层执行 | 不在 LangGraph 内动态画子图 |
| `review_framework.yaml` | `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE` 或后续 YAML 配置 | 第一版继续用 Python 常量，避免配置迁移扩大范围 |

## 3. 当前项目中的具体可行性

### 3.1 流程层可行

现有 `InvestmentDocumentReviewFlow` 的主线是：

```text
evaluate_policy_gate
  -> classify_document_type
  -> build_review_framework
  -> run_single_pass_review
  -> build_final_result
```

v1 只需要替换中后段：

```text
evaluate_policy_gate
  -> classify_document_type
  -> build_review_framework
  -> generate_review_todo_plan
  -> execute_review_todo_plan
  -> synthesize_review_result
  -> build_final_result
```

前半段的缺失字段检查、投资建议拒绝、实时行情拒绝、文档分类都应该保留。这样可以避免 v1 任务拆解阶段生成越界任务。

### 3.2 合约层可行

现有 `TodoExecutionPlan` 已包含：

```python
tasks: list[TodoTaskSpec]
summary: str
failure_policy: TodoFailurePolicy
```

现有 `TodoTaskSpec` 已包含：

```python
id: str
kind: TodoTaskKind
title: str
description: str
payload: dict[str, Any]
depends_on: list[str]
completion_criteria: list[str]
```

这比参考示例的 plan 更完整，因为已经包含 `completion_criteria` 和 `failure_policy`。v1 迁移时应使用现有合约，不新增一套相似模型。

需要补充的是投资文档审查专用 task kind，例如：

```text
investment_document_extract
investment_document_analyze
investment_document_synthesize
```

这些应按仓库规则放入 `TodoTaskKind(str, Enum)` 和模块级常量，而不是散落字符串。

### 3.3 执行层可行

现有 `TodoExecutionRunner` 已经支持：

- 按依赖层执行。
- 同一层并发执行。
- `DEFAULT_TODO_CONCURRENCY = 3`。
- `RETRY_THEN_FAIL`、`FAIL_FAST`、`BEST_EFFORT`。
- 依赖失败时跳过下游任务。
- executor 异常包装为结构化失败结果。

这正好对应参考示例里的依赖图执行器。区别是参考示例在运行期动态编译 TriggerFlow，Investory 不需要这样做；用 `build_dependency_layers()` 已经足够稳定，也更容易测试。

### 3.4 API 层可行

现有 gateway 已有：

```text
POST /investment-document-review
InvestmentDocumentReviewRequest
TaskResponse
```

v1 不需要新增 endpoint。建议保持接口不变，只改变成功响应中的 `result.review` 结构，使其包含 plan、task results 和 synthesis 后的最终审查结果。

为了兼容现有测试和调用方，第一版可保持：

```json
{
  "action": "complete",
  "document_type": "...",
  "route_reason": "...",
  "route_confidence": 0.91,
  "review": {
    "document_type": "...",
    "extracted_facts": [],
    "risk_findings": [],
    "information_gaps": [],
    "boundary_notes": [],
    "summary": "...",
    "learning_next_steps": []
  }
}
```

并在 `review` 内或旁路字段中增加：

```json
{
  "todo_plan": {},
  "todo_results": []
}
```

若担心兼容性，建议先把执行明细放在 `review.execution_trace`，最终对外字段仍保持 `InvestmentDocumentReviewResult` 的主结构。

## 4. 适用性边界

### 4.1 适合引入 v1 的场景

v1 适合这些投资文档审查任务：

- ETF factsheet：费用、指数、持仓、历史表现、风险披露可分开提取，再汇总分析。
- Fund prospectus：费用、赎回、限制、风险因素之间存在明显依赖关系。
- Product brochure：收益描述、适用条件、风险披露、营销措辞可以分项审查。
- Earnings report：收入利润、现金流、管理层评论、风险披露可以并行提取，再做一致性判断。
- Learning material：概念、机制、例子可以分开提取，再判断学习重点和内部一致性。

这些场景有共同特点：文档较长、信息分散、审查角度多、先事实后判断更可靠。

### 4.2 不适合引入 v1 的场景

以下场景不适合走完整 To-Do 执行：

- 文档很短，single-pass 足够稳定。
- 用户只是问一个单点解释问题。
- 输入缺少 `document_text`。
- 文档类型无法可靠识别。
- 用户要求买入、卖出、持有、仓位、择时或收益预测。
- 用户要求实时行情、最新价格、今日收益，但当前 flow 不支持实时数据。

这些情况应继续由 policy gate、missing input result 或 refusal result 提前结束。

### 4.3 为什么不能把 To-Do 放在最前面

To-Do plan generation 需要文档类型和审查框架，否则模型会生成泛化、越界或不可执行的任务。正确顺序是：

```text
先 route，再 plan；先 policy gate，再 task decomposition。
```

这也符合当前 Investory 的安全边界：先判断是否能处理，再决定如何拆解。

## 5. 推荐目标架构

### 5.1 新增或调整的合约

建议在 `src/investory/agent_core/contracts/todo_execution.py` 增加投资文档审查任务类型常量和枚举值：

```python
INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND = "investment_document_extract"
INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND = "investment_document_analyze"
INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND = "investment_document_synthesize"
```

并加入：

```python
class TodoTaskKind(str, Enum):
    ...
    INVESTMENT_DOCUMENT_EXTRACT = INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND
    INVESTMENT_DOCUMENT_ANALYZE = INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND
    INVESTMENT_DOCUMENT_SYNTHESIZE = INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND
```

也可以单独新增投资文档 plan 输出模型，例如放在：

```text
src/investory/agent_core/task_models/investment_document_review_todo.py
```

但第一版建议优先复用 `TodoExecutionPlan`，减少模型数量。

### 5.2 新增任务模型与 prompts

建议新增三个 LLM task：

```text
investment_document_review_plan
investment_document_extract
investment_document_analyze
investment_document_synthesize
```

对应文件：

```text
src/investory/agent_core/task_models/investment_document_review_plan.py
src/investory/agent_core/task_models/investment_document_review_todo_tasks.py

src/investory/agent_core/prompts/tasks/investment_document_review_plan.md
src/investory/agent_core/prompts/tasks/investment_document_extract.md
src/investory/agent_core/prompts/tasks/investment_document_analyze.md
src/investory/agent_core/prompts/tasks/investment_document_synthesize.md
```

任务职责：

| Task | 职责 | 输出 |
|---|---|---|
| plan | 根据 document type、framework、review goal 生成 To-Do plan | `TodoExecutionPlan` |
| extract | 只提取事实，不判断 | facts / citations / summary |
| analyze | 基于上游 facts 判断风险、缺口、一致性 | findings / severity / boundary notes |
| synthesize | 汇总所有 task results 为最终审查结果 | `InvestmentDocumentReviewResult` |

### 5.3 Flow 节点调整

建议把现有节点：

```text
RUN_SINGLE_PASS_REVIEW
```

替换为：

```text
GENERATE_REVIEW_TODO_PLAN
EXECUTE_REVIEW_TODO_PLAN
SYNTHESIZE_REVIEW_RESULT
```

对应枚举值应放在 `InvestmentDocumentReviewNode(str, Enum)`，不要使用散落字符串。

新的 state 字段建议加入 `InvestmentDocumentReviewState`：

```python
todo_plan: TodoExecutionPlan | None = None
todo_results: list[TodoTaskResult] = Field(default_factory=list)
review_synthesis_payload: dict[str, Any] | None = None
```

如果担心 Pydantic state 复杂度，也可以先用 `dict[str, Any]`，但最终建议使用已定义的 Pydantic 合约，方便测试和错误定位。

## 6. 分阶段实施计划

> 补充说明：下面各阶段最初是实施计划。结合 `docs/2-2/worklog/09-investment_document_review_v1_execution_worklog.md` 的实际落地情况，这里补充“当前实现说明”，帮助把“为什么这么设计”与“代码现在做到哪一步”对应起来。

### 当前实现状态概览

截至当前 worklog，阶段 1 到阶段 5 的核心能力已经按计划拆分落地，重点不是一次性推倒现有 flow，而是沿着“合约 -> plan 生成 -> runner 接入 -> resume -> synthesis 聚合”这条链逐段替换 single-pass。

可以把当前实现理解成两层：

- LangGraph flow 负责主流程编排：`policy gate -> route -> build framework -> generate plan -> execute plan -> synthesize`。
- `TodoExecutionRunner` 负责 plan 内部调度：`validate -> dependency layers -> bounded concurrency -> retry/skip/fail -> ordered results`。

这样做的好处是职责边界清楚：

- flow 层知道什么时候该规划、什么时候该执行、什么时候该汇总。
- runner 层知道任务之间的依赖、重试、跳过与顺序返回。
- 两层之间用 `TodoExecutionPlan`、`TodoTaskResult`、`TodoExecutionResumeState` 这些明确合约传递，而不是共享临时运行时对象。

### 阶段 1：补齐任务类型和模型合约

目标：让投资文档审查可以表达 plan、extract、analyze、synthesize 四类动作。

Step:

1. 先整理现有 `TodoExecution` 合约和 `InvestmentDocumentReview` 任务模型，确认哪些字段可以直接复用。
2. 增加投资文档审查专用 `TodoTaskKind` 常量和枚举值。
3. 补齐 plan / extract / analyze / synthesize 的输入输出模型。
4. 更新 `tasks.py` 的 TaskSpec 注册。
5. 把对应 prompts 的文件名和职责一并固定下来。
6. 先用最小样例验证这些模型可以在 Pydantic 层通过校验。

实施项：

- 在 `todo_execution.py` 增加投资文档相关 `TodoTaskKind` 枚举值和常量。
- 新增 plan generation 的输入/输出模型，或明确复用 `TodoExecutionPlan`。
- 新增 extract / analyze / synthesize 的输入输出模型。
- 更新 `tasks.py` 注册新 TaskSpec。
- 新增 prompts，要求模型遵守非投资建议边界。

验收：

- 新增模型可通过 Pydantic 校验。
- `tasks.py` 中新任务可被 `resolve_task_spec()` 找到。
- 单元测试覆盖新增 task names 和 task kind 枚举。

当前实现说明：

- 这一阶段最终没有新造一套 plan 合约，而是明确复用了已有 `TodoExecutionPlan`、`TodoTaskSpec`、`TodoTaskResult`。这样后续 runner、validator、resume 都能直接接上，不需要再做一层模型翻译。
- `TodoTaskKind` 已补齐投资文档审查专用常量和枚举值，分别覆盖 `extract`、`analyze`、`synthesize`。这一步很关键，因为后面的 task 分发、测试断言、prompt 绑定都依赖这些稳定常量，不能散落 raw string。
- task model 层已经拆成两块：一块是 plan 输入；另一块是 extract / analyze / synthesize 的任务输入输出。这里的设计重点是让 analyze 显式接收上游 `TodoTaskResult`，而不是偷读 flow state 或模型原始输出。
- `tasks.py` 已注册 `investment_document_review_plan`、`investment_document_extract`、`investment_document_analyze`、`investment_document_synthesize` 四个内部 TaskSpec。这样 flow 在运行时可以按 task name 找到对应 prompt 和输出模型。
- prompt 文件也已经按 TaskSpec 的 `prompt_name` 固定下来。这里不是单纯“多几个 markdown 文件”，而是把“plan 做什么、extract 做什么、analyze 做什么、synthesize 做什么”固定成稳定边界，避免职责在后续迭代中漂移。
- 这一阶段还补了一个最小 Pydantic 验证样例，串起 `plan -> extract -> analyze -> synthesize -> final result` 整条模型链路。它的价值在于，后面 flow 或 runner 出问题时，可以先排除是不是模型契约本身不自洽。

### 阶段 2：生成投资文档审查 To-Do Plan

目标：在 `build_review_framework` 之后生成结构化 plan。

Step:

1. 先把 `generate_review_todo_plan` 作为独立节点设计出来，不直接塞进执行器。
2. 明确 plan 生成输入，至少包含 `document_text`、`document_type`、`extract_focus`、`analyze_focus`、`review_goal`。
3. 设计 prompt 约束，限定 extract 和 analyze 的职责边界。
4. 把 `depends_on`、`completion_criteria`、task id 规则写进输出要求。
5. 用 `ensure_valid_todo_plan()` 做模型输出的二次校验。
6. 先用一个或两个文档类型跑通 plan 生成，再扩大覆盖面。

实施项：

- 新增 `generate_review_todo_plan` flow 节点。
- 输入包含 `document_text`、`document_type`、`extract_focus`、`analyze_focus`、`review_goal`。
- prompt 强制输出：
  - extract 任务必须 `depends_on=[]`。
  - analyze 任务必须依赖至少一个 extract 任务。
  - 每个 task 必须有非空 `completion_criteria`。
  - task id 使用稳定短 id，例如 `extract_fees`、`analyze_fee_risk`。
  - 不允许生成投资建议、实时行情或个性化配置任务。
- 调用 `ensure_valid_todo_plan()` 校验模型输出。

验收：

- valid plan 进入下一节点。
- unknown dependency、self dependency、cycle、empty completion criteria 会失败并返回结构化错误。
- 计划生成不改变现有 missing/refusal 行为。

当前实现说明：

- `generate_review_todo_plan` 已经作为独立 flow 节点落地，而不是嵌进执行器内部。这样做的直接收益是：plan 生成失败和 task 执行失败可以被清楚区分，测试也能分别覆盖。
- plan 输入已经被显式化，不再依赖某个“隐含 state 恰好有这些字段”。目前输入围绕 `document_text`、`document_type`、`extract_focus`、`analyze_focus`、`review_goal` 组织，这和 single-pass 输入保持了一致性，迁移成本较低。
- prompt 约束已经明确把 extract / analyze 分开：extract 只抽事实、引用、缺口、边界；analyze 才负责基于上游结果做风险与一致性判断。这一步本质上是在削弱模型“边提取边脑补”的冲动。
- `depends_on`、`completion_criteria`、稳定 task id 规则都已经写进 plan 输出要求。原因不是为了“格式整齐”，而是为了让 validator 和 runner 真正能消费这些字段，而不是把它们当摆设。
- 计划生成后会先经过模型反序列化，再调用 `ensure_valid_todo_plan()` 做二次校验。也就是说，LLM 只是提议 plan，最终是否可执行由本地 validator 判定。
- 当前实现先从一个受控文档类型范围起步，再逐步扩展覆盖面，这比一开始追求“所有类型都能规划”更稳。因为 v1 真正难的不是生成任务列表，而是生成“能被现有执行器稳定消费的任务列表”。

### 阶段 3：接入 TodoExecutionRunner

目标：用现有 runner 按依赖分层并发执行投资文档子任务。

Step:

1. 先把 `TodoExecutionRunner` 当成唯一执行入口，而不是在 flow 里临时拼执行逻辑。
2. 设计 task.kind 到具体 TaskSpec 的分发规则。
3. 为 extract/analyze/synthesize 准备各自的 payload 结构。
4. 确认依赖结果如何传给 analyze 任务。
5. 让 runner 先只支持单次请求内执行，不引入 resume。
6. 用失败任务和依赖任务做边界测试，确认 skip 和 retry 的行为稳定。

实施项：

- 新增 `InvestmentDocumentTodoTaskExecutor` 或私有方法 `_execute_review_todo_task()`。
- 根据 `task.kind` 分发到 extract/analyze/synthesize 对应 TaskSpec。
- analyze 任务 payload 必须包含依赖任务结果。
- 使用 `TodoExecutionRunner`，默认并发先使用 `DEFAULT_TODO_CONCURRENCY`。
- 对失败策略先使用 `RETRY_THEN_FAIL`，避免单次模型波动导致整体失败。
- 先保持单次请求内执行，不在本阶段引入跨请求 resume。

验收：

- 无依赖 extract 任务在同一层执行。
- analyze 任务等待依赖结果。
- 依赖失败时下游任务被 skipped。
- executor 返回 id 不匹配时被 runner 识别为 failed。

当前实现说明：

- 当前 flow 并没有在内部拼一套临时并发逻辑，而是把 review To-Do 执行统一收口到 `TodoExecutionRunner`。这意味着依赖分层、失败策略、顺序返回这些语义都沿用了仓库已有实现。
- review task 的执行入口已经落到私有执行方法上，由它根据 `task.kind` 分发到 extract / analyze / synthesize 对应 TaskSpec。这里的设计重点是“按 kind 分发”，不是“按 task id 写死分支”，所以后续 plan 增减任务时不需要改 executor 主结构。
- payload 组装也已经分别做了边界控制：extract 拿文档和 focus；analyze 除自身 payload 外，还会拿到上游依赖任务的 `TodoTaskResult`；synthesize 则接 plan、完成结果和聚合摘要。这样每类任务只读自己该读的数据。
- analyze 依赖结果是在运行时按 `depends_on` 收集并注入的，而不是在 plan 生成时把上游结果预填进去。原因很简单：plan 生成阶段还没有结果，真正可用的依赖结果只能发生在 executor 运行中。
- 阶段 3 的实现刻意只做“单次请求内的 To-Do 执行”，没有立刻把 resume 混进来。这是个很实用的拆分：先让 plan 和 DAG 执行稳定，再处理跨请求恢复，否则问题会纠缠在一起。
- 失败与依赖边界测试也在这阶段补齐了，重点验证的是：同层 extract 可以并发、analyze 会等待依赖、依赖失败会产出 `skipped`、executor 返回非法结果会被 runner 识别为失败。这些都是后面 resume 和 synthesis 能站住的前提。

### 阶段 4：补充 resume_state / previous_results 断点续跑

目标：让 To-Do 执行支持中断后继续，避免重复执行已经成功的子任务。

Step:

1. 先定义 resume 的数据边界，只保存恢复所需信息，不保存整个运行对象。
2. 设计 `TodoExecutionResumeState`，固定 `results_by_id` 和 `attempts_by_id` 的结构。
3. 给 `TodoExecutionRunner.run()` 增加 `resume_state` 参数。
4. 实现已完成任务跳过逻辑，确保 succeeded 任务不会重复调用 executor。
5. 实现恢复时的依赖重建和重新分层。
6. 在 flow 层留出 load / save 持久化的插槽。
7. 用部分成功、部分失败、依赖失败三种场景验证恢复行为。

实施项：

- 新增 `TodoExecutionResumeState` 合约，表达已持久化的执行状态。
- `TodoExecutionResumeState` 至少包含：
  - `run_id` 或 `session_id`
  - `plan`
  - `results_by_id`
  - `attempts_by_id`
  - `updated_at`
- 扩展 `TodoExecutionRunner.run()`，支持类似参数：

```python
async def run(
    self,
    plan: TodoExecutionPlan,
    *,
    resume_state: TodoExecutionResumeState | None = None,
) -> list[TodoTaskResult]:
    ...
```

- 恢复时跳过 `status=succeeded` 的任务。
- 对 `failed`、`skipped`、`running` 或缺失结果的任务，按 `failure_policy` 和依赖状态决定是否重跑。
- 如果依赖任务已成功，允许下游未完成任务继续执行。
- 如果依赖任务失败且无法恢复，下游继续返回 `skipped`。
- 在 flow 层预留加载和保存状态的位置：

```text
load persisted resume_state
-> runner.run(plan, resume_state=resume_state)
-> persist new task results
-> synthesize
```

- 第一版可以先把持久化接口抽象出来，不强行绑定数据库；后续再决定使用文件、SQLite、Postgres 或 LangGraph checkpointer。
- 当前 Phase 4 Step 6 的实现只预留 `todo_resume_store` 接口插槽：如果 flow 没有注入 store，`load` 返回 `None` 且不会执行真实 `save`；如果注入 store，则由该 store 的实现决定从哪里读取、保存到哪里。测试中的 `RecordingTodoResumeStore` 只是内存记录调用顺序，用于验证插槽位置，不代表已经落地真实持久化。

验收：

- 已成功任务不会再次调用 executor。
- 未完成任务可以在依赖满足后继续执行。
- 依赖失败的任务仍按现有 skipped 语义处理。
- retry 次数不会因为 resume 被错误重置。
- 返回结果仍按原始 plan 顺序排列。
- 新增测试覆盖：
  - partial success resume
  - failed dependency resume
  - running task treated as retry candidate
  - attempts_by_id preserved
  - completed task executor not called again

当前实现说明：

- `TodoExecutionResumeState` 已作为独立合约落地，保存的是“恢复执行所需信息”，不是运行时对象快照。它至少围绕 plan、`results_by_id`、`attempts_by_id`、时间戳这些恢复必需数据组织。
- resume 结构不是随便收个 dict 就结束了，而是有显式校验规则。`results_by_id` 必须和 plan 中的 task id 对齐，`attempts_by_id` 也必须是可验证的恢复信息，避免持久化层写进一堆 runner 根本无法消费的脏状态。
- `TodoExecutionRunner.run()` 现在已支持 `resume_state` 参数，并且会先校验 resume 里的 plan 是否与当前 plan 一致。这一步很重要，因为“错误地复用另一个 plan 的历史结果”会比“完全不恢复”更危险。
- 已成功的任务会直接从 `resume_state.results_by_id` 重建，不再重新调用 executor；`failed`、`skipped`、`running` 则不会一概当作完成，而是根据剩余重试次数和依赖状态继续处理。
- 恢复执行时，不是简单“从中断点往后接着跑”，而是基于当前 plan 重新构建依赖层，并把已成功、已耗尽失败、待重试任务一并放回同一个依赖语义里。这能保证下游任务的跳过/继续规则仍然和首次执行一致。
- `attempts_by_id` 会被真正用于恢复剩余 retry 预算，而不是 resume 后把次数清零重来。否则系统会在断点恢复后悄悄改变失败策略，测试很难发现，线上成本也会失控。
- flow 层目前只预留了 `todo_resume_store` 插槽，用来加载和保存 resume 状态，但还没有绑定到真实数据库或文件存储。这是有意为之：先把 runner 语义做稳，再决定持久化技术选型，能避免过早耦合。
- 这阶段的测试已经覆盖部分成功恢复、运行中任务视为可重试、失败依赖导致下游继续 skipped、已成功任务不再调 executor、结果仍按 plan 顺序输出等关键场景。也就是说，resume 现在已经不是“概念支持”，而是有完整语义约束的能力。

### 阶段 5：最终汇总

目标：把多个子任务结果汇总为现有 `InvestmentDocumentReviewResult`。

Step:

1. 先明确 synthesize 的输入只来自已完成任务结果，不直接读模型原始输出。
2. 设计 `todo_plan`、`todo_results` 和 review summary 的汇总方式。
3. 确认 route reason、route confidence、document type 如何进入最终结果。
4. 让 summary 对 failed 或 skipped 任务给出明确的 information gaps 或 boundary notes。
5. 验证 resume 场景下不会把已完成结果重复计算。

实施项：

- 新增 `synthesize_review_result` 节点。
- 输入包含：
  - `document_type`
  - `route_reason`
  - `route_confidence`
  - `todo_plan`
  - `todo_results`
  - `review_goal`
- 输出继续使用 `InvestmentDocumentReviewResult`，保持对外主结构稳定。
- 可选增加 `execution_trace`，记录 task id、status、summary、error。

验收：

- 最终 `TaskResult.task_name` 仍为 `investment_document_review`。
- 成功响应仍包含 `action=document_review.complete` 对应值，即当前 `complete`。
- `review.extracted_facts`、`risk_findings`、`information_gaps`、`boundary_notes` 有稳定来源。
- 失败或 skipped 子任务不会导致最终结果伪装成完整审查；必须进入 `information_gaps` 或 `boundary_notes`。
- resume 后的最终汇总不得重复计算已完成任务的结果。

当前实现说明：

- synthesis 输入现在只吃“完成态的 `TodoTaskResult`”，不会直接回看模型原始输出。这一步把最终结果和中间执行状态隔开了，减少了“哪个节点偷偷塞了额外字段”这种隐式耦合。
- flow 层已经增加“完成结果过滤”逻辑，只有终态结果会进入 synthesize；`PENDING`、`RUNNING` 之类中间态不会混进最终汇总。这保证了最终报告反映的是一次明确完成的审查视图，而不是半成品执行快照。
- 除了 `todo_plan` 和 `todo_results`，实现里还补了结构化的 `review_summary` 聚合契约。它会提前整理计划摘要、完成统计、成功/失败/跳过任务 id，以及从各任务抽取的 facts、findings、gaps、boundary notes。
- 这个 `review_summary` 的作用不是取代 `todo_results`，而是给 synthesize 一个更稳定、更低噪音的聚合输入；`todo_results` 继续保留为可追踪的任务级证据源。可以理解成：summary 负责归纳，results 负责追溯。
- 汇总顺序也做了确定性处理：优先按 plan 顺序聚合完成结果，若出现计划外的额外完成结果，再放到后面。这能保证相同 plan 下最终结果尽量稳定，减少测试和调试时的“偶发顺序抖动”。
- 对 failed / skipped 子任务，汇总逻辑会把“为什么这里不完整”显式转译成 `information_gaps` 或 `boundary_notes`，而不是默默忽略。这样最终 review 不会伪装成一份无缺口的完整审查报告。
- 在 resume 场景下，synthesis 继续复用恢复后的完成结果与聚合摘要，不重新计算已完成任务。这使得“断点续跑”不只是执行层节省成本，也能在结果层避免重复聚合和重复表述。

#### 阶段 5 最终汇总到底做了什么

阶段 5 的核心不是“再调用一次模型写总结”，而是把前面动态 To-Do 执行出来的多份子任务结果，收敛成 Investory 对外已经稳定的 `InvestmentDocumentReviewResult`。这一层承担的是结果边界控制：哪些结果可以进入最终审查、以什么顺序进入、失败或跳过如何表达、路由元数据如何保留，以及 resume 后如何避免重复计算。

落地后可以把最终汇总理解成四层输入：

1. `todo_plan`：告诉 synthesize 这次审查原本计划覆盖哪些任务、任务之间是什么顺序和依赖。
2. `todo_results`：保留完成态任务的原始结构化结果，作为可追踪证据源。
3. `review_summary`：flow 层先做一轮确定性聚合，把 facts、risk findings、information gaps、boundary notes、任务状态和任务摘要整理成低噪音输入。
4. route metadata：`document_type`、`route_reason`、`route_confidence` 继续进入 synthesize 输入和最终 `TaskResult` 外层，保证“为什么按这个文档类型审查”不会在汇总阶段丢失。

这里刻意把“执行细节”和“最终报告”分开。`todo_results` 负责追溯，`review_summary` 负责给最终模型一个稳定摘要，`InvestmentDocumentReviewResult` 负责保持公开响应结构稳定。这样做可以避免最终结果直接依赖某个子任务模型的临时输出形状，也能避免因为执行顺序或 resume 状态不同而产生不必要的结果抖动。

阶段 5 还补了三个关键安全边界：

- 只允许 `SUCCEEDED`、`FAILED`、`SKIPPED` 这类完成态结果进入 synthesize；`PENDING`、`RUNNING` 不会进入最终汇总。
- `FAILED` 会显式进入 `information_gaps`，`SKIPPED` 会显式进入 `boundary_notes`，让最终审查承认不完整性。
- resume 恢复出来的已成功结果会先注入 flow 的执行结果 state，再进入 synthesize；runner 不会重复调用这些已完成任务，summary 也不会重复聚合它们。

对应的代码关系是：

```text
execute_review_todo_plan
  -> load resume_state
  -> _build_todo_execution_runner(state, resume_state=...)
  -> runner.run(plan, resume_state=...)
  -> _build_review_todo_synthesize_payload
  -> _build_completed_todo_results
  -> _build_review_todo_summary
  -> investment_document_synthesize
  -> build_final_result
```

因此，阶段 5 的结果可以概括为：把 To-Do DAG 的执行产物，变成一个稳定、可追踪、承认缺口、兼容 resume 的最终审查结果。

新增可视化流程图：

```text
docs/2-2/flowcharts/investment_document_review_synthesis_flowchart.html
```

### 阶段 6：网关与兼容性测试

目标：不破坏 `/investment-document-review` 的公开入口。

Step:

1. 先补 flow 层单测，再补 gateway 层单测。
2. 验证 policy gate、missing input、refusal 和 unknown document type 的原有行为。
3. 验证 plan 生成、执行、汇总的正向路径。
4. 验证 resume 相关场景。
5. 最后跑全量测试，确认公开 API 返回结构没有变化。

实施项：

- 更新 `test_investment_document_review_flow.py`。
- 更新 `test_investment_document_review_gateway_api.py`。
- 新增 plan generation、todo execution、synthesis 的单元测试。
- 保留旧 single-pass 测试所覆盖的 policy gate、missing input、refusal、unknown document type 行为。

验收：

- 使用仓库 `.venv` 运行：

```powershell
.venv\Scripts\python -m pytest tests
```

- 所有现有测试通过。
- 新增 tests 覆盖：
  - plan valid path
  - invalid dependency
  - dependency failure skip
  - resume skips completed task
  - resume preserves attempts
  - task result synthesis
  - gateway response shape

当前实现说明：

- 目前 worklog 已经覆盖了大量 flow、runner、resume、prompt、task model 相关测试，说明 v1 核心链路已经具备较强的局部验证。
- 但“阶段 6 完全完成”仍然应该谨慎表述。原因是当前记录里重点是增量测试集和关键链路测试，并不等于已经完成一次完整的公开接口兼容性清扫。
- 换句话说，当前状态更准确的表述是：内部执行能力基本落地并经过针对性验证；网关层面的全量兼容确认，仍应作为单独收口步骤处理。
- 这也解释了为什么前面几个阶段都强调“保持对外 `InvestmentDocumentReviewResult` 主结构稳定”。因为只有先控制住对外结构不扩散，阶段 6 的兼容性测试才会真正可收敛。

## 7. 推荐文件变更清单

建议第一轮改动控制在以下文件内：

```text
src/investory/agent_core/contracts/todo_execution.py
src/investory/agent_core/contracts/investment_document_review_state.py
src/investory/agent_core/task_models/investment_document_review.py
src/investory/agent_core/tasks.py
src/investory/agent_core/runtime/todo_core/runner.py
src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py
src/investory/agent_core/prompts/tasks/investment_document_review_plan.md
src/investory/agent_core/prompts/tasks/investment_document_extract.md
src/investory/agent_core/prompts/tasks/investment_document_analyze.md
src/investory/agent_core/prompts/tasks/investment_document_synthesize.md
tests/test_investment_document_review_flow.py
tests/test_investment_document_review_gateway_api.py
tests/test_investment_document_review_todo_plan.py
tests/test_investment_document_review_todo_execution.py
tests/test_todo_execution_resume.py
```

如果第一版就落实断点续跑，还建议新增或扩展：

```text
src/investory/agent_core/contracts/todo_execution.py
  - TodoExecutionResumeState
  - attempts_by_id / results_by_id 合约字段

src/investory/agent_core/runtime/todo_core/runner.py
  - run(..., resume_state=None)
  - completed task skip 逻辑
  - attempts 保留逻辑

src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py
  - load persisted resume_state 的插入点
  - persist updated todo_results 的插入点

tests/test_todo_execution_resume.py
  - resume skips succeeded tasks
  - resume retries incomplete tasks
  - resume preserves attempts
  - resume keeps result order
```

不建议第一轮改动：

- 不新增 Agently 依赖。
- 不新增 TriggerFlow 风格执行器。
- 不重写 gateway schema。
- 不把 review framework 立刻迁移到 YAML。
- 不把 To-Do runner 放到所有任务入口前面。

## 8. 风险与控制

| 风险 | 影响 | 控制方式 |
|---|---|---|
| 模型生成非法依赖 | 执行顺序错误或死循环 | `ensure_valid_todo_plan()` 前置校验 |
| analyze 任务没有事实依据 | 产生幻觉判断 | analyze payload 必须包含上游 result |
| 子任务过多 | 成本和延迟上升 | plan prompt 限制任务数量，例如 4-8 个 |
| 并发过高 | API 限流或成本失控 | 使用 `DEFAULT_TODO_CONCURRENCY=3`，后续配置化 |
| 输出结构不兼容 | gateway 调用方破坏 | 保持 `InvestmentDocumentReviewResult` 主结构 |
| 投资建议越界 | 安全风险 | policy gate 前置，prompt 和 synthesis 双重约束 |
| 实时数据误用 | 给出过期或虚构价格 | 当前继续拒绝 realtime request |
| resume 重复执行已完成任务 | 成本上升、结果重复 | `resume_state.results_by_id` 中 `succeeded` 任务必须跳过 |
| resume 丢失 retry 次数 | 重试超限或无限重试 | 持久化 `attempts_by_id`，恢复时继续累计 |
| resume 后依赖状态不一致 | 下游过早执行或错误 skipped | 恢复前重新跑 `ensure_valid_todo_plan()` 并按依赖状态重建 layers |
| 持久化层过早绑定数据库 | 实现范围膨胀 | 第一版先抽象 load/save 位置，数据库选择后置 |

## 9. 建议优先级

推荐按以下顺序推进：

1. 先保留现有 v0 flow，新增 v1 节点但不删除 single-pass task。
2. 用 fake runner / fake executor 写完 flow 单元测试。
3. 先接入 `TodoExecutionRunner` 的单次请求执行。
4. 再补 `resume_state / previous_results`，让已完成任务不重复执行。
5. 接入真实 prompts 和 TaskSpec。
6. 用 `.venv` 跑全量测试。
7. 如果 v1 稳定，再决定是否移除或降级 single-pass 为 fallback。

第一版最务实的目标不是“让每个文档都自动拆得很复杂”，而是让长文档审查具备可验证的事实提取、依赖分析和汇总链路，同时不破坏 Investory 当前的投资边界和 API 契约。

## 10. 补充问答与设计决策

### 10.1 能不能在 LangGraph 内动态画子图？

可以，但第一版不建议把它作为 Investory 的主实现方式。

LangGraph 中“动态画子图”通常有三种理解：

```text
1. 预定义节点 + 条件边
   add_conditional_edges(...)

2. 动态 fan-out
   Send(...)

3. 节点内部根据当前 plan 临时构建 StateGraph，compile 后 invoke
```

第 1 种适合 policy gate、文档类型路由、是否拒绝或继续审查这类稳定分支。第 2 种适合根据任务清单把多个同类任务分发到同一个执行节点。第 3 种最接近参考示例里按 plan 动态编译依赖执行图，但会把 LangGraph 节点、依赖调度、失败处理和测试复杂度都集中到一个运行时子图里。

对当前 Investory，更合适的第一版架构是：

```text
LangGraph 负责主流程：
policy gate -> route -> build framework -> generate plan -> execute plan -> synthesize

TodoExecutionRunner 负责 plan 内部动态依赖：
validate -> dependency layers -> bounded concurrency -> retries -> skipped/failed results
```

原因是项目已经有 `TodoExecutionRunner`、`build_dependency_layers()` 和 `ensure_valid_todo_plan()`，这些能力已经覆盖动态依赖执行，并且更容易写单元测试、控制失败策略和保持 API 行为稳定。

如果后续需要 LangGraph 原生 checkpoint、streaming trace、或者在调试 UI 中可视化每个子任务节点，再考虑把 plan execution 改成 `Send` 或运行时子图。

### 10.2 当前 TodoExecutionRunner 和 LangGraph Send 的区别是什么？

当前 `TodoExecutionRunner` 是业务级任务调度器；LangGraph `Send` 更像图内 fan-out 分发机制。两者不是同一层能力。

当前 executor 已经负责：

```text
1. 校验 plan 是否合法
   duplicate id / unknown dependency / self dependency / cycle / empty criteria

2. 把 DAG 转成执行层
   第一层无依赖任务并发跑
   第二层等第一层依赖成功后再跑
   依此类推

3. 控制并发
   DEFAULT_TODO_CONCURRENCY = 3

4. 管失败策略
   fail_fast / best_effort / retry_then_fail

5. 管 retry
   DEFAULT_TODO_MAX_RETRIES = 2

6. 管 dependency failure
   上游失败，下游自动 skipped

7. 管 executor 结果合法性
   result.id 必须等于 task.id
   status 只能是 succeeded / failed / skipped

8. 最后按原始 plan 顺序返回结果
```

`Send` 本身不直接负责这些。它的核心职责是：

```text
这里有 N 个 payload
请把它们分别发给某个节点执行
```

因此两者的区别可以这样看：

| 能力 | 当前 TodoExecutionRunner | LangGraph Send |
|---|---|---|
| 运行时任务数量动态 | 支持 | 支持 |
| 同构任务 fan-out | 支持，通过 `asyncio.gather` | 支持，图原生 |
| 复杂 `depends_on` DAG | 支持，分层拓扑 | 不内置，需要自行设计 |
| plan 合法性校验 | 已有 | 不内置 |
| retry 策略 | 已有 | 需要节点或 graph 另配 |
| dependency failed -> skipped | 已有 | 需要自行实现 |
| fail_fast / best_effort | 已有 | 需要自行实现 |
| LangGraph trace / checkpoint | 不细到每个子任务 | 更适合 |
| 用户可见实时进度 | 需要额外实现 | 更自然 |

放到 Investory 当前场景，`TodoExecutionRunner` 更像：

```text
plan -> validate -> dependency layers -> bounded concurrency -> retry/skip/fail -> ordered results
```

`Send` 更像：

```text
state -> generate many payloads -> call same node many times -> merge results
```

所以第一版 v1 更适合继续使用现有 executor。当前核心需求是可靠执行 To-Do 依赖计划，而不是让 LangGraph trace 展示每个子任务节点。

后续可以考虑 `Send` 的情况：

```text
1. 希望 LangGraph trace 里看到每个 extract / analyze 子任务
2. 需要 checkpoint / resume 到子任务级别
3. 要 streaming 展示每个子任务进度
4. 任务依赖比较简单，主要是大量同类并发
5. 愿意把 retry、skip、fail_fast 等策略重新搬进 LangGraph 设计
```

一句话：当前 executor 是调度器，`Send` 是分发语法。现在的问题用调度器更合适。

### 10.3 如果中断后不想重复执行已完成任务，哪种方式合适？

这种需求本质是 checkpoint / resume：执行到一半中断后，下次从已完成结果继续，而不是重新跑全部任务。

判断标准是：

```text
需要子任务级断点续跑 -> 更适合 LangGraph checkpoint 或给 TodoExecutionRunner 增加持久化 resume
只是一次请求内跑完 -> 当前 TodoExecutionRunner 更合适
```

对当前 Investory，建议第一阶段继续用 `TodoExecutionRunner`，但增加持久化恢复能力。需要保存的状态包括：

```text
run_id / session_id
todo_plan
todo_results_by_id
task status: succeeded / failed / skipped / running
task output
task error
updated_at
```

恢复时的执行逻辑：

```text
1. 读取已有 todo_plan 和 todo_results_by_id
2. 跳过 status=succeeded 的任务
3. 对 failed / skipped / running 任务按 failure_policy 决定是否重跑
4. 只执行依赖已满足且未完成的任务
5. 所有必要任务完成后继续 synthesize
```

这条路线更贴合当前代码，因为现有 runner 已经负责依赖、retry、skip、顺序返回和失败策略。需要扩展的是 runner 的输入与状态层，例如支持：

```python
runner.run(plan, resume_state=previous_results)
```

或在 flow 层包装：

```text
load persisted results
-> call runner with completed task ids
-> persist new task results
-> synthesize
```

另一条路线是 LangGraph checkpoint + `Send`。它适合希望 LangGraph 原生记录每个子任务节点状态，并支持中断恢复、streaming 和 trace 的场景：

```text
generate_plan
-> Send 多个 extract / analyze 子任务
-> checkpoint 每个节点结果
-> 中断后从 graph checkpoint 恢复
```

但这会要求把当前 runner 已经处理好的策略搬到 LangGraph 设计中：

```text
- 依赖失败后的 skipped 结果
- fail_fast / best_effort / retry_then_fail
- retry 次数
- result.id 和 status 合法性校验
- 最终按 plan 顺序聚合结果
```

所以本项目的推荐顺序是：

```text
第一阶段：
  扩展 TodoExecutionRunner，支持 resume_state / previous_results。

第二阶段：
  如果需要子任务级 LangGraph trace、checkpoint、streaming 进度 UI，再考虑 Send + checkpoint。
```

也就是说，核心问题不是 fan-out，而是“已完成任务不要重复执行”。这个能力可以先在当前调度器里解决。

### 10.4 拓扑图具体执行顺序是否需要展示给用户？

通常不需要。拓扑图的主要价值是内部执行质量控制，不是用户侧主要内容。

用户真正需要看到的是：

```text
1. 系统审查了哪些方面
2. 哪些结论来自文档原文事实
3. 哪些是风险、缺口或不一致
4. 哪些材料不足导致结论有限
5. 最终摘要和可继续补充的材料
```

拓扑图更适合内部使用：

```text
- 保证先提取事实，再做分析判断
- 控制哪些任务可以并发
- 处理依赖失败后的 skipped 结果
- 支持测试、排错和审计
- 为后续 tracing / debug 模式提供依据
```

因此产品层建议区分三层输出：

| 层级 | 建议输出 |
|---|---|
| 用户响应 | 审查维度、事实、风险、信息缺口、边界说明、摘要 |
| 调试追踪 | `todo_plan`、`todo_results`、task status、depends_on、耗时、错误 |
| API 默认行为 | 默认不暴露完整拓扑，必要时通过 `debug=true` 或 internal trace 返回 |

也就是说，v1 的 To-Do 依赖图应定位为内部 orchestration trace。它提升执行可靠性，但不应成为普通用户的主要展示内容。
